"""Pulizia DXF: rimuove cartiglio/quote/note/viste secondarie mantenendo
solo la geometria del pezzo (contorno + fori interni).

Uso tipico: dopo che il detector v3 ha identificato il pezzo (bbox + polygon),
`save_cleaned_dxf` crea un nuovo file `<name>_cleaned.dxf` che contiene SOLO
le entità geometricamente dentro il bounding box del pezzo. Il commerciale
vede il thumbnail pulito, Mirko riceve un file DXF già pronto per il nesting
Lantek senza cartiglio.

Regole di filtro (per bounding box, NON per layer perché i layer sono
variabili tra fornitori):

- LINE:             entrambi gli endpoint dentro bbox (con tolleranza)
- CIRCLE:           centro dentro bbox (raggio tipicamente piccolo → forature)
- ARC:              centro dentro bbox
- LWPOLYLINE:       tutti i vertici dentro bbox
- POLYLINE:         tutti i vertici dentro bbox
- SPLINE:           tutti i control points dentro bbox
- ELLIPSE:          centro dentro bbox
- TEXT/MTEXT:       SKIP (sono quote o note, non geometria)
- DIMENSION/LEADER: SKIP (linee di quota, sono metadati)
- INSERT:           SKIP (block reference: cartiglio, logo, decorazioni)
- HATCH:            SKIP (tratteggi, non tagliano)

Tolleranza: max(1 mm, 2% del lato bbox più corto). Serve perché alcuni
fornitori mettono forature al bordo del pezzo che escono per micron.

Sanity check post-cleanup:
- Se il file pulito è vuoto (0 entità) → errore, si mantiene originale
- Se il file pulito ha <5% delle entità originali → warning, sospetto
"""
from __future__ import annotations

import logging
import os
from typing import Iterable, Sequence

import ezdxf

logger = logging.getLogger(__name__)

# Tipi entità sempre esclusi dal cleanup (sono metadati, non geometria del pezzo)
_SKIP_TYPES = frozenset({
    'TEXT', 'MTEXT', 'ATTDEF', 'ATTRIB',
    'DIMENSION', 'LEADER', 'MULTILEADER', 'ARC_DIMENSION',
    'INSERT',            # block reference (cartiglio spesso è un block)
    'HATCH',             # tratteggi
    'IMAGE', 'WIPEOUT',  # oggetti immagine/mascheratura
})


def _tolerance_for_bbox(bbox: Sequence[float]) -> float:
    """Tolleranza (mm) per contenimento in bbox. max(1mm, 2% lato corto)."""
    minx, miny, maxx, maxy = bbox
    side = min(maxx - minx, maxy - miny)
    return max(1.0, side * 0.02)


def _point_in_bbox(x: float, y: float, bbox: Sequence[float], tol: float) -> bool:
    minx, miny, maxx, maxy = bbox
    return (minx - tol) <= x <= (maxx + tol) and (miny - tol) <= y <= (maxy + tol)


def _entity_in_bbox(entity, bbox: Sequence[float], tol: float) -> bool:
    """Ritorna True se l'entità è (in tutto o in parte) dentro il bbox.

    Regola permissiva: se ALMENO UN punto dell'entità è dentro il bbox
    con la tolleranza, la copio. Preferisco "troppo generoso" a "troppo
    stretto": Mirko poi vede il DXF pulito e capisce, mentre "0 entità"
    è UX rotta. La tolleranza aggiuntiva serve per bordi al mm.
    """
    et = entity.dxftype()
    try:
        if et == 'LINE':
            s, ee = entity.dxf.start, entity.dxf.end
            return (_point_in_bbox(s[0], s[1], bbox, tol) or
                    _point_in_bbox(ee[0], ee[1], bbox, tol))
        if et == 'CIRCLE':
            c = entity.dxf.center
            return _point_in_bbox(c[0], c[1], bbox, tol)
        if et == 'ARC':
            c = entity.dxf.center
            return _point_in_bbox(c[0], c[1], bbox, tol)
        if et == 'ELLIPSE':
            c = entity.dxf.center
            return _point_in_bbox(c[0], c[1], bbox, tol)
        if et == 'LWPOLYLINE':
            pts = list(entity.get_points('xy'))
            return any(_point_in_bbox(p[0], p[1], bbox, tol) for p in pts)
        if et == 'POLYLINE':
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
            return any(_point_in_bbox(p[0], p[1], bbox, tol) for p in pts)
        if et == 'SPLINE':
            ctrl = list(entity.control_points or [])
            if ctrl:
                return any(_point_in_bbox(p[0], p[1], bbox, tol) for p in ctrl)
            fit = list(entity.fit_points or [])
            if fit:
                return any(_point_in_bbox(p[0], p[1], bbox, tol) for p in fit)
            return False
        if et in ('POINT', 'SOLID'):
            loc = getattr(entity.dxf, 'location', None) or getattr(entity.dxf, 'vtx0', None)
            if loc is None:
                return False
            return _point_in_bbox(loc[0], loc[1], bbox, tol)
    except Exception as e:
        logger.debug('entity_in_bbox %s failed: %s', et, e)
        return False
    return False


def save_cleaned_dxf(
    source_path: str,
    cleaned_path: str,
    bbox: Sequence[float],
    min_entities: int = 1,
) -> dict:
    """Scrive `cleaned_path` con solo le entità dentro bbox del pezzo.

    Args:
        source_path: DXF originale (input)
        cleaned_path: dove scrivere il DXF pulito (output)
        bbox: [minx, miny, maxx, maxy] del pezzo scelto (dal detector v3)
        min_entities: soglia minima entità da copiare (sotto = fail)

    Returns:
        {'success': bool, 'entities_copied': int, 'entities_source': int,
         'entities_skipped_meta': int, 'entities_out_of_bbox': int,
         'tolerance_mm': float, 'error': str|None, 'warnings': [str]}

    Non solleva su errori di parsing entità singole (li logga a DEBUG),
    solleva solo se il DXF non è leggibile o il pulito è vuoto.
    """
    result = {
        'success': False,
        'entities_copied': 0,
        'entities_source': 0,
        'entities_skipped_meta': 0,
        'entities_out_of_bbox': 0,
        'tolerance_mm': 0.0,
        'error': None,
        'warnings': [],
    }

    try:
        src = ezdxf.readfile(source_path)
    except Exception as e:
        result['error'] = f'DXF non leggibile: {e}'
        return result

    tol = _tolerance_for_bbox(bbox)
    result['tolerance_mm'] = tol

    # Nuovo documento vuoto con stessa DXF version dell'originale
    try:
        dst = ezdxf.new(dxfversion=src.dxfversion, setup=False)
    except Exception:
        # Fallback: version di default
        dst = ezdxf.new(setup=False)

    # Copia i layer usati (mantiene i colori originali). Solo quelli.
    src_layers = {l.dxf.name for l in src.layers}
    for lname in src_layers:
        if lname in dst.layers:
            continue
        try:
            src_layer = src.layers.get(lname)
            new_layer = dst.layers.add(lname)
            try:
                new_layer.dxf.color = src_layer.dxf.color
            except Exception:
                pass
        except Exception as e:
            logger.debug('layer %s copy failed: %s', lname, e)

    src_ms = src.modelspace()
    dst_ms = dst.modelspace()

    for e in src_ms:
        result['entities_source'] += 1
        et = e.dxftype()
        if et in _SKIP_TYPES:
            result['entities_skipped_meta'] += 1
            continue
        if not _entity_in_bbox(e, bbox, tol):
            result['entities_out_of_bbox'] += 1
            continue
        # Copia l'entità nel modelspace destinazione
        try:
            new_e = e.copy()
            dst_ms.add_entity(new_e)
            result['entities_copied'] += 1
        except Exception as ex:
            logger.debug('entity copy failed %s: %s', et, ex)

    if result['entities_copied'] < min_entities:
        result['error'] = (
            f'Nessuna geometria trovata nel rettangolo selezionato. '
            f'Prova a ridisegnare il rettangolo un po\' più grande, '
            f'assicurandoti di includere tutto il contorno del pezzo (esterno + fori).'
        )
        return result

    # Ratio warning: se abbiamo copiato meno del 5% dell'originale, sospetto
    src_geom = result['entities_source'] - result['entities_skipped_meta']
    if src_geom > 0:
        ratio = result['entities_copied'] / src_geom
        if ratio < 0.05:
            result['warnings'].append(
                f'Solo {result["entities_copied"]}/{src_geom} entità geom. copiate '
                f'({ratio*100:.1f}%): verifica bbox pezzo.'
            )

    try:
        os.makedirs(os.path.dirname(cleaned_path), exist_ok=True)
        dst.saveas(cleaned_path)
    except Exception as e:
        result['error'] = f'Scrittura fallita: {e}'
        return result

    result['success'] = True
    return result


def should_cleanup(detector_result: dict) -> tuple[bool, str]:
    """Decide se il file va auto-pulito in base al risultato del detector v3.

    Returns:
        (yes_no, reason): yes_no=True se procedere con cleanup automatico.

    Regole:
    - confidence >= 0.7          → SI (alta fiducia)
    - confidence 0.5-0.7         → SI (media, ma marker "needs_review")
    - confidence < 0.5           → NO (utente deve intervenire manualmente)
    - area_ratio > 0.9           → NO (sospetto = cartiglio incluso)
    - needs_manual_select=True   → NO
    """
    if not detector_result:
        return (False, 'no detector result')
    if detector_result.get('needs_manual_select'):
        return (False, 'needs_manual_select')
    conf = float(detector_result.get('confidence') or 0)
    if conf < 0.5:
        return (False, f'confidence bassa ({conf:.2f})')
    # Sanity: pezzo che occupa quasi tutto il foglio è sospetto (probabile
    # cartiglio incluso). Confronto area pezzo vs bbox foglio DXF.
    area_pezzo = float(detector_result.get('area_dm2') or 0)
    dxf_bbox = detector_result.get('dxf_bbox_mm') or []
    if len(dxf_bbox) == 4 and area_pezzo > 0:
        foglio_dm2 = (dxf_bbox[2] - dxf_bbox[0]) * (dxf_bbox[3] - dxf_bbox[1]) / 10000.0
        if foglio_dm2 > 0:
            ratio = area_pezzo / foglio_dm2
            if ratio > 0.9:
                return (False, f'area_ratio {ratio:.2f} > 0.9 (probabile cartiglio incluso)')
    return (True, f'confidence {conf:.2f}')


def get_pezzo_bbox(detector_result: dict) -> list | None:
    """Estrae il bbox del pezzo scelto dal detector v3.

    Il detector espone `candidates[selected_candidate_idx].bbox` con
    [minx, miny, maxx, maxy] in mm. Ritorna None se non disponibile.
    """
    if not detector_result:
        return None
    cands = detector_result.get('candidates') or []
    sel = detector_result.get('selected_candidate_idx')
    if not cands:
        return None
    # selected_candidate_idx può essere l'idx globale (non del vettore cands)
    for c in cands:
        if c.get('is_selected') or c.get('idx') == sel:
            b = c.get('bbox')
            if b and len(b) == 4:
                return list(b)
    # fallback: primo candidato (score più alto)
    b = cands[0].get('bbox')
    return list(b) if b and len(b) == 4 else None

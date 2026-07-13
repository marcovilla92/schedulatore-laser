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
import re
import shutil
from typing import Iterable, Sequence

import ezdxf

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Export automatico DXF puliti in <root>/<cliente>/<numero_ordine>/
# Chiamato dopo ogni save-cleaned-by-click. Best-effort: se il path
# non è configurato o la scrittura fallisce, log warning e continua
# (il file DXF pulito resta comunque in uploads/preventivi_tmp/).
# ═══════════════════════════════════════════════════════════════════

_PATH_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]')


def _sanitize_path_part(name: str, fallback: str = 'unknown') -> str:
    """Rende un nome sicuro per uso come parte di path filesystem.
    Rimuove caratteri invalidi Windows (<>:"/\\|?*) + spazi iniziali/finali."""
    if not name:
        return fallback
    clean = _PATH_INVALID_CHARS.sub('_', str(name)).strip().strip('.')
    if not clean:
        return fallback
    # Limita a 100 char per evitare path troppo lunghi
    return clean[:100]


def export_cleaned_dxf_to_client_folder(
    cleaned_source_path: str,
    cliente: str,
    numero_ordine: str,
    original_filename: str,
    export_root: str,
) -> dict:
    """Copia il DXF pulito nella cartella <export_root>/<cliente>/<numero_ordine>/.

    Args:
        cleaned_source_path: path assoluto del file cleaned in preventivi_tmp
        cliente: nome cliente (sanitizzato per path)
        numero_ordine: numero ordine cliente OPPURE fallback PREV-YYYY-NNNN
        original_filename: nome originale del DXF (senza _cleaned)
        export_root: root dell'export configurato dall'admin

    Returns:
        {'success': bool, 'exported_path': str|None, 'error': str|None}
    """
    result = {'success': False, 'exported_path': None, 'error': None}

    if not export_root or not export_root.strip():
        result['error'] = 'export_root non configurato (Impostazioni → Cartella disegni per Mirko)'
        return result

    if not os.path.exists(cleaned_source_path):
        result['error'] = f'source non trovato: {cleaned_source_path}'
        return result

    try:
        cliente_dir = _sanitize_path_part(cliente, 'cliente_sconosciuto')
        ordine_dir = _sanitize_path_part(numero_ordine, 'ordine_sconosciuto')
        # Nome file finale: usa l'originale (es: 20PA00693-00.dxf), non il "_cleaned"
        # perché a Mirko interessa il codice pezzo, non il flag di pulizia.
        target_name = _sanitize_path_part(os.path.basename(original_filename), 'pezzo.dxf')
        if not target_name.lower().endswith(('.dxf', '.dwg')):
            target_name += '.dxf'

        target_dir = os.path.join(export_root.strip(), cliente_dir, ordine_dir)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, target_name)

        # Copia (overwrite se esiste — l'utente può aver rifatto il cleanup)
        shutil.copy2(cleaned_source_path, target_path)
        result['success'] = True
        result['exported_path'] = target_path
        logger.info('DXF esportato: %s → %s', os.path.basename(cleaned_source_path), target_path)
    except PermissionError as e:
        result['error'] = f'permessi negati sulla cartella {export_root}: {e}'
        logger.warning('export DXF fallito (permessi): %s', e)
    except OSError as e:
        result['error'] = f'errore filesystem: {e}'
        logger.warning('export DXF fallito (OS): %s', e)
    except Exception as e:
        result['error'] = f'errore: {e}'
        logger.warning('export DXF fallito: %s', e)
    return result

# Tipi entità sempre esclusi dal cleanup (sono metadati, non geometria del pezzo)
_SKIP_TYPES = frozenset({
    'TEXT', 'MTEXT', 'ATTDEF', 'ATTRIB',
    'DIMENSION', 'LEADER', 'MULTILEADER', 'ARC_DIMENSION',
    'INSERT',            # block reference (cartiglio spesso è un block)
    'HATCH',             # tratteggi
    'IMAGE', 'WIPEOUT',  # oggetti immagine/mascheratura
})


def _tolerance_for_bbox(bbox: Sequence[float]) -> float:
    """Tolleranza (mm) per contenimento in bbox.

    Il drag rettangolare umano è impreciso: l'utente traccia una selezione
    "grosso modo" attorno al pezzo, a volte 1-3mm troppo stretta su un lato.
    Se la tolerance è troppo piccola (es. 1mm), un pezzo 410×30mm dove
    l'utente ha selezionato fino a Y=281 invece di Y=283 perde le entità
    del bordo superiore (linea che chiude + smussi ai raccordi) e il bbox
    risultante è 410×28 invece di 410×30.

    Formula: `max(5mm, 8% del lato corto del bbox)`.
    Il connected-components filter downstream elimina comunque i cluster
    di cartiglio isolati, quindi una tolerance generosa non re-introduce
    falsi positivi.
    """
    minx, miny, maxx, maxy = bbox
    side = min(maxx - minx, maxy - miny)
    return max(5.0, side * 0.08)


def _point_in_bbox(x: float, y: float, bbox: Sequence[float], tol: float) -> bool:
    minx, miny, maxx, maxy = bbox
    return (minx - tol) <= x <= (maxx + tol) and (miny - tol) <= y <= (maxy + tol)


def _entity_bbox(entity) -> tuple[float, float, float, float] | None:
    """Bbox (minx, miny, maxx, maxy) di una singola entità, in mm.
    None se non calcolabile."""
    et = entity.dxftype()
    try:
        if et == 'LINE':
            s, ee = entity.dxf.start, entity.dxf.end
            return (min(s[0], ee[0]), min(s[1], ee[1]),
                    max(s[0], ee[0]), max(s[1], ee[1]))
        if et in ('CIRCLE', 'ARC'):
            c = entity.dxf.center
            r = float(getattr(entity.dxf, 'radius', 0) or 0)
            return (c[0] - r, c[1] - r, c[0] + r, c[1] + r)
        if et == 'ELLIPSE':
            c = entity.dxf.center
            return (c[0] - 1, c[1] - 1, c[0] + 1, c[1] + 1)  # approx
        if et == 'LWPOLYLINE':
            pts = list(entity.get_points('xy'))
            if not pts: return None
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            return (min(xs), min(ys), max(xs), max(ys))
        if et == 'POLYLINE':
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
            if not pts: return None
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            return (min(xs), min(ys), max(xs), max(ys))
        if et == 'SPLINE':
            ctrl = list(entity.control_points or []) or list(entity.fit_points or [])
            if not ctrl: return None
            xs = [p[0] for p in ctrl]; ys = [p[1] for p in ctrl]
            return (min(xs), min(ys), max(xs), max(ys))
        if et in ('POINT', 'SOLID'):
            loc = getattr(entity.dxf, 'location', None) or getattr(entity.dxf, 'vtx0', None)
            if loc is None: return None
            return (loc[0], loc[1], loc[0], loc[1])
    except Exception:
        return None
    return None


def _bboxes_overlap(a, b, gap: float) -> bool:
    """True se i due bbox si sovrappongono o distano <= gap (in mm)."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    if ax2 + gap < bx1 or bx2 + gap < ax1:
        return False
    if ay2 + gap < by1 or by2 + gap < ay1:
        return False
    return True


def _all_clusters(entities_with_bbox: list, gap: float) -> list[list[int]]:
    """Union-Find sulle entità in base a prossimità bbox (<=gap mm).
    Ritorna TUTTI i cluster come lista di liste di indici."""
    n = len(entities_with_bbox)
    if n == 0:
        return []
    if n == 1:
        return [[0]]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry: parent[rx] = ry

    for i in range(n):
        bi = entities_with_bbox[i][1]
        for j in range(i + 1, n):
            bj = entities_with_bbox[j][1]
            if _bboxes_overlap(bi, bj, gap):
                union(i, j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        r = find(i)
        groups.setdefault(r, []).append(i)
    return list(groups.values())


def _pick_best_cluster(entities_with_bbox: list, gap: float) -> list:
    """Union-Find sulle entità in base a prossimità bbox (<=gap mm), poi sceglie
    il cluster che ha maggiori probabilità di essere IL PEZZO.

    Metrica "pezzo-like":
      score = n_circles * 10           # i fori sono un forte segnale di pezzo laser
            + n_polylines * 5           # contorni chiusi sono tipici del pezzo
            + n_arcs * 2                # smussi/raccordi = pezzo
            + n_total * 0.1             # tiebreak: più entità = più probabile pezzo

    I cartigli tabellari sono fatti di LINE corte in griglia — score basso perché
    n_circles=0, n_polylines=0, n_arcs=0. I pezzi laser hanno tipicamente ≥1 foro
    o ≥1 polyline chiusa (contorno esterno).

    Ritorna la lista di indici del cluster vincente.
    """
    n = len(entities_with_bbox)
    if n <= 1:
        return list(range(n))
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry: parent[rx] = ry

    for i in range(n):
        bi = entities_with_bbox[i][1]
        for j in range(i + 1, n):
            bj = entities_with_bbox[j][1]
            if _bboxes_overlap(bi, bj, gap):
                union(i, j)
    # Raggruppa per root
    groups: dict[int, list[int]] = {}
    for i in range(n):
        r = find(i)
        groups.setdefault(r, []).append(i)

    def cluster_score(idxs: list[int]) -> float:
        n_c = n_p = n_a = 0
        for i in idxs:
            et = entities_with_bbox[i][0].dxftype()
            if et == 'CIRCLE': n_c += 1
            elif et in ('LWPOLYLINE', 'POLYLINE'): n_p += 1
            elif et == 'ARC': n_a += 1
        return n_c * 10 + n_p * 5 + n_a * 2 + len(idxs) * 0.1

    return max(groups.values(), key=cluster_score)


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

    # ═══════════════════════════════════════════════════════════════════
    # STRATEGIA "a prova di stupido":
    #
    # Il bbox utente indica UN PUNTO NELLO SPAZIO ("il pezzo è qui"),
    # NON un ritaglio esatto. La geometria del pezzo viene poi ricostruita
    # per intero seguendo la CONNETTIVITÀ, senza mai tagliare al bbox.
    #
    # Passi:
    # 1. Raccogli TUTTE le entità geometriche del DXF (skip solo metadata:
    #    testo, quote, cartiglio-INSERT, hatch).
    # 2. Costruisci cluster di entità spazialmente connesse (bbox overlap
    #    con gap ~2mm). Ogni cluster è un "oggetto disegnato".
    # 3. Per ogni cluster, calcola quanto INTERSECA il bbox utente.
    # 4. Scarta cluster che non toccano affatto il bbox utente (cartiglio,
    #    viste secondarie, note tecniche).
    # 5. Fra i cluster rimasti, scegli quello più "pezzo-like" (score che
    #    premia CIRCLE/POLYLINE/ARC — indicatori di geometria di taglio).
    # 6. Copia TUTTE le entità del cluster vincente, ANCHE se qualcuna
    #    sta 2-3mm oltre il bbox utente (il bordo superiore del pezzo,
    #    uno smusso, ecc.) — la connettività garantisce che appartengano
    #    allo stesso oggetto.
    #
    # Vantaggi vs il vecchio approccio "filtra per bbox":
    # - Utente traccia rettangolo un pelo stretto → NON PERDE bordi
    # - Utente traccia rettangolo un pelo largo → NON PRENDE cartiglio
    # - Utente clicca dentro il pezzo con rettangolino minuscolo → OK
    # ═══════════════════════════════════════════════════════════════════

    # FASE 1: raccogli tutte le entità geometriche (con bbox individuale)
    all_geom: list[tuple[object, tuple[float, float, float, float]]] = []
    for e in src_ms:
        result['entities_source'] += 1
        et = e.dxftype()
        if et in _SKIP_TYPES:
            result['entities_skipped_meta'] += 1
            continue
        eb = _entity_bbox(e)
        if eb is None:
            # Entità senza bbox: skip (non possiamo clusterizzarla)
            result['entities_skipped_meta'] += 1
            continue
        all_geom.append((e, eb))

    if not all_geom:
        result['error'] = 'DXF senza entità geometriche riconoscibili.'
        return result

    # FASE 2: cluster spaziale su TUTTE le entità (gap 2mm)
    merge_gap = 2.0
    clusters = _all_clusters(all_geom, merge_gap)

    # FASE 3+4: seleziona cluster che toccano bbox utente
    # Un cluster "tocca" il bbox utente se il suo bbox unione interseca
    # il bbox utente con una tolleranza generosa (10mm — il pezzo può
    # sporgere di 5-10mm dal drag utente in ogni direzione).
    touch_tol = 10.0
    touching_clusters: list[list[int]] = []
    for cluster_idxs in clusters:
        cx1 = min(all_geom[i][1][0] for i in cluster_idxs)
        cy1 = min(all_geom[i][1][1] for i in cluster_idxs)
        cx2 = max(all_geom[i][1][2] for i in cluster_idxs)
        cy2 = max(all_geom[i][1][3] for i in cluster_idxs)
        if _bboxes_overlap((cx1, cy1, cx2, cy2), tuple(bbox), touch_tol):
            touching_clusters.append(cluster_idxs)

    if not touching_clusters:
        # Fallback: nessun cluster tocca — usa il vecchio filtro bbox strict
        logger.warning('cleanup: nessun cluster tocca il bbox utente %s, uso fallback filtro strict', bbox)
        touching_clusters = [[i for i, (_e, eb) in enumerate(all_geom)
                              if _bboxes_overlap(eb, tuple(bbox), tol)]]

    # FASE 5: fra i cluster candidati, scegli il più "pezzo-like"
    def cluster_score(idxs: list[int]) -> float:
        n_c = n_p = n_a = 0
        for i in idxs:
            et = all_geom[i][0].dxftype()
            if et == 'CIRCLE': n_c += 1
            elif et in ('LWPOLYLINE', 'POLYLINE'): n_p += 1
            elif et == 'ARC': n_a += 1
        return n_c * 10 + n_p * 5 + n_a * 2 + len(idxs) * 0.1

    winner = max(touching_clusters, key=cluster_score)
    winner_set = set(winner)

    # FASE 5b: ASSORBIMENTO fori interni.
    # I fori del pezzo sono spesso entità isolate (CIRCLE piccoli, ARC di svasature,
    # slot di forature ovali) che NON toccano il contorno esterno — quindi
    # il clustering le mette in cluster separati. Ma sono geometricamente
    # DENTRO il bbox del contorno → appartengono al pezzo.
    # Regola: assorbi qualsiasi entità il cui bbox è interamente contenuto
    # nel bbox unione del cluster vincente (con tolleranza 1mm ai bordi).
    wx1 = min(all_geom[i][1][0] for i in winner)
    wy1 = min(all_geom[i][1][1] for i in winner)
    wx2 = max(all_geom[i][1][2] for i in winner)
    wy2 = max(all_geom[i][1][3] for i in winner)
    absorb_tol = 1.0
    absorbed = 0
    for idx, (_e, eb) in enumerate(all_geom):
        if idx in winner_set:
            continue
        ex1, ey1, ex2, ey2 = eb
        # Bbox entità interamente dentro bbox cluster (con tolleranza)
        if (ex1 >= wx1 - absorb_tol and ex2 <= wx2 + absorb_tol and
            ey1 >= wy1 - absorb_tol and ey2 <= wy2 + absorb_tol):
            winner_set.add(idx)
            absorbed += 1
    if absorbed > 0:
        logger.info('cleanup: assorbite %d entità interne al bbox del pezzo (fori isolati)',
                    absorbed)

    dropped_by_cluster = len(all_geom) - len(winner_set)
    if dropped_by_cluster > 0:
        result['entities_dropped_component'] = dropped_by_cluster
        logger.info('cleanup: cluster vincente ha %d entità (di cui %d assorbite), scartate %d (cartiglio/note/viste)',
                    len(winner_set), absorbed, dropped_by_cluster)

    # FASE 6: copia TUTTE le entità del cluster vincente (anche fuori bbox utente)
    entities_out_of_bbox_count = 0
    for idx, (e, eb) in enumerate(all_geom):
        if idx not in winner_set:
            # Statistica: era fuori bbox o solo scartato dal cluster?
            if not _bboxes_overlap(eb, tuple(bbox), tol):
                entities_out_of_bbox_count += 1
            continue
        try:
            new_e = e.copy()
            dst_ms.add_entity(new_e)
            result['entities_copied'] += 1
        except Exception as ex:
            logger.debug('entity copy failed %s: %s', e.dxftype(), ex)
    result['entities_out_of_bbox'] = entities_out_of_bbox_count

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

    # Calcola bbox reale delle entità copiate (utile per dimensioni pezzo).
    # Iteriamo su dst_ms per prendere gli endpoint delle entità geometriche.
    try:
        xs, ys = [], []
        for e in dst_ms:
            et = e.dxftype()
            if et == 'LINE':
                s, ee = e.dxf.start, e.dxf.end
                xs.extend([s[0], ee[0]]); ys.extend([s[1], ee[1]])
            elif et in ('CIRCLE', 'ARC'):
                c = e.dxf.center
                r = float(getattr(e.dxf, 'radius', 0) or 0)
                xs.extend([c[0] - r, c[0] + r]); ys.extend([c[1] - r, c[1] + r])
            elif et == 'ELLIPSE':
                c = e.dxf.center
                xs.append(c[0]); ys.append(c[1])
            elif et == 'LWPOLYLINE':
                pts = list(e.get_points('xy'))
                for p in pts: xs.append(p[0]); ys.append(p[1])
            elif et == 'POLYLINE':
                for v in e.vertices:
                    xs.append(v.dxf.location.x); ys.append(v.dxf.location.y)
        if xs and ys:
            result['bbox_mm'] = [min(xs), min(ys), max(xs), max(ys)]
    except Exception as be:
        logger.debug('bbox calc failed: %s', be)

    result['success'] = True
    return result


def _distance_point_to_bbox(x: float, y: float, bbox: Sequence[float]) -> float:
    """Distanza euclidea approssimata da (x,y) al bbox (minx,miny,maxx,maxy)."""
    minx, miny, maxx, maxy = bbox
    dx = max(minx - x, 0, x - maxx)
    dy = max(miny - y, 0, y - maxy)
    return (dx * dx + dy * dy) ** 0.5


def save_cleaned_dxf_by_click(
    source_path: str,
    cleaned_path: str,
    click_x: float,
    click_y: float,
    max_pick_distance_mm: float = 15.0,  # deprecato: ora fallback su cluster-contains-point
) -> dict:
    """Pulizia DXF a partire da un CLICK su un'entità del pezzo.

    Approccio "a prova di stupido": l'utente non deve tracciare un rettangolo
    (fragile), ma cliccare direttamente su UNA linea/arco/cerchio del pezzo.
    Il sistema:
    1. Trova l'entità geometrica più vicina al punto cliccato.
    2. Identifica il cluster spazialmente connesso di quell'entità.
    3. Assorbe eventuali entità isolate contenute nel bbox del cluster (fori).
    4. Salva il DXF pulito con quel cluster + fori.

    Args:
        source_path: DXF originale
        cleaned_path: destinazione
        click_x, click_y: coordinate del click in mm (DXF)
        max_pick_distance_mm: distanza massima per considerare un'entità "cliccata"

    Returns:
        {'success', 'entities_copied', 'entities_source', 'entities_skipped_meta',
         'bbox_mm', 'clicked_entity_type', 'error', 'warnings'}
    """
    result = {
        'success': False,
        'entities_copied': 0,
        'entities_source': 0,
        'entities_skipped_meta': 0,
        'clicked_entity_type': None,
        'clicked_entity_distance_mm': None,
        'bbox_mm': None,
        'error': None,
        'warnings': [],
    }

    try:
        src = ezdxf.readfile(source_path)
    except Exception as e:
        result['error'] = f'DXF non leggibile: {e}'
        return result

    # Crea documento destinazione
    try:
        dst = ezdxf.new(dxfversion=src.dxfversion, setup=False)
    except Exception:
        dst = ezdxf.new(setup=False)
    for lname in {l.dxf.name for l in src.layers}:
        if lname in dst.layers:
            continue
        try:
            src_layer = src.layers.get(lname)
            new_layer = dst.layers.add(lname)
            try:
                new_layer.dxf.color = src_layer.dxf.color
            except Exception:
                pass
        except Exception:
            pass

    src_ms = src.modelspace()
    dst_ms = dst.modelspace()

    # FASE 1: raccogli tutte le entità geometriche con bbox
    all_geom: list[tuple[object, tuple[float, float, float, float]]] = []
    for e in src_ms:
        result['entities_source'] += 1
        et = e.dxftype()
        if et in _SKIP_TYPES:
            result['entities_skipped_meta'] += 1
            continue
        eb = _entity_bbox(e)
        if eb is None:
            result['entities_skipped_meta'] += 1
            continue
        all_geom.append((e, eb))

    if not all_geom:
        result['error'] = 'DXF senza entità geometriche riconoscibili.'
        return result

    # FASE 2: trova l'entità più vicina al click (per riferimento — non più bloccante)
    best_idx = -1
    best_dist = float('inf')
    for i, (_e, eb) in enumerate(all_geom):
        d = _distance_point_to_bbox(click_x, click_y, eb)
        if d < best_dist:
            best_dist = d
            best_idx = i

    if best_idx < 0:
        result['error'] = 'Nessuna entità geometrica nel DXF.'
        return result

    clicked_ent = all_geom[best_idx][0]
    result['clicked_entity_type'] = clicked_ent.dxftype()
    result['clicked_entity_distance_mm'] = round(best_dist, 2)

    # FASE 3: cluster spaziale su TUTTE le entità
    clusters = _all_clusters(all_geom, gap=2.0)

    # FASE 4: seleziona il cluster.
    # STRATEGIA A PROVA DI STUPIDO:
    #
    # 1. Se il click è DIRETTAMENTE su un'entità (dist < 1mm):
    #    → usa il cluster che contiene quella entità. PUNTO.
    #    Ignora cartigli-frame che avvolgono tutto il foglio (loro bbox
    #    contiene il punto ma NON contiene la clicked entity — vince
    #    quello giusto).
    #
    # 2. Se il click è in area vuota (dist >= 1mm):
    #    → cerca cluster il cui bbox contiene il punto.
    #    → preferisci il PIÙ PICCOLO (per bbox area), non il più grande.
    #    Un cartiglio-frame ha bbox enorme, un pezzo piccolo ha bbox
    #    proporzionato → il pezzo vince.
    #    → tra cluster di area simile, usa lo score "pezzo-like".
    def cluster_score(idxs: list[int]) -> float:
        n_c = n_p = n_a = 0
        for i in idxs:
            et = all_geom[i][0].dxftype()
            if et == 'CIRCLE': n_c += 1
            elif et in ('LWPOLYLINE', 'POLYLINE'): n_p += 1
            elif et == 'ARC': n_a += 1
        return n_c * 10 + n_p * 5 + n_a * 2 + len(idxs) * 0.1

    def cluster_bbox_area(idxs: list[int]) -> float:
        cx1 = min(all_geom[i][1][0] for i in idxs)
        cy1 = min(all_geom[i][1][1] for i in idxs)
        cx2 = max(all_geom[i][1][2] for i in idxs)
        cy2 = max(all_geom[i][1][3] for i in idxs)
        return max(0.0, cx2 - cx1) * max(0.0, cy2 - cy1)

    if best_dist < 1.0:
        # Caso 1: click SU un'entità. Il cluster della clicked entity è LA verità.
        winner = None
        for cluster_idxs in clusters:
            if best_idx in cluster_idxs:
                winner = cluster_idxs
                break
        if winner is None:
            winner = [best_idx]
    else:
        # Caso 2: click in area vuota (dist >= 1mm).
        # Cerca cluster il cui bbox contiene il punto — preferisci il più
        # PICCOLO per area (evita cartigli-frame che avvolgono tutto).
        containing_clusters: list[list[int]] = []
        for cluster_idxs in clusters:
            cx1 = min(all_geom[i][1][0] for i in cluster_idxs)
            cy1 = min(all_geom[i][1][1] for i in cluster_idxs)
            cx2 = max(all_geom[i][1][2] for i in cluster_idxs)
            cy2 = max(all_geom[i][1][3] for i in cluster_idxs)
            if cx1 <= click_x <= cx2 and cy1 <= click_y <= cy2:
                containing_clusters.append(cluster_idxs)
        if containing_clusters:
            winner = min(containing_clusters, key=lambda c: (cluster_bbox_area(c), -cluster_score(c)))
        elif best_dist <= max_pick_distance_mm:
            # Nessun cluster contiene il punto → usa il cluster della clicked entity
            # (solo se abbastanza vicino, entro 15mm)
            winner = None
            for cluster_idxs in clusters:
                if best_idx in cluster_idxs:
                    winner = cluster_idxs
                    break
            if winner is None:
                winner = [best_idx]
        else:
            # Click completamente in area vuota, nessun bbox lo contiene
            # e nessuna entità vicina → errore chiaro
            result['error'] = (
                f'Click a {best_dist:.0f}mm dall\'entità più vicina e fuori da qualsiasi pezzo. '
                f'Click DENTRO il rettangolo (bbox) di uno dei pezzi disegnati oppure sul suo contorno.'
            )
            return result

    winner_set = set(winner)

    # FASE 5: assorbi entità isolate contenute nel bbox del cluster (fori)
    wx1 = min(all_geom[i][1][0] for i in winner)
    wy1 = min(all_geom[i][1][1] for i in winner)
    wx2 = max(all_geom[i][1][2] for i in winner)
    wy2 = max(all_geom[i][1][3] for i in winner)
    absorb_tol = 1.0
    for idx, (_e, eb) in enumerate(all_geom):
        if idx in winner_set:
            continue
        ex1, ey1, ex2, ey2 = eb
        if (ex1 >= wx1 - absorb_tol and ex2 <= wx2 + absorb_tol and
            ey1 >= wy1 - absorb_tol and ey2 <= wy2 + absorb_tol):
            winner_set.add(idx)

    # FASE 6: copia entità
    for idx, (e, _eb) in enumerate(all_geom):
        if idx not in winner_set:
            continue
        try:
            new_e = e.copy()
            dst_ms.add_entity(new_e)
            result['entities_copied'] += 1
        except Exception:
            pass

    if result['entities_copied'] < 1:
        result['error'] = 'Cluster vuoto — click non ha selezionato geometria valida.'
        return result

    # Scrivi
    try:
        os.makedirs(os.path.dirname(cleaned_path), exist_ok=True)
        dst.saveas(cleaned_path)
    except Exception as e:
        result['error'] = f'Scrittura fallita: {e}'
        return result

    # BBox finale
    try:
        xs, ys = [], []
        for e in dst_ms:
            et = e.dxftype()
            if et == 'LINE':
                s, ee = e.dxf.start, e.dxf.end
                xs += [s[0], ee[0]]; ys += [s[1], ee[1]]
            elif et in ('CIRCLE', 'ARC'):
                c = e.dxf.center
                r = float(getattr(e.dxf, 'radius', 0) or 0)
                xs += [c[0] - r, c[0] + r]; ys += [c[1] - r, c[1] + r]
            elif et == 'LWPOLYLINE':
                for pt in e.get_points('xy'):
                    xs.append(pt[0]); ys.append(pt[1])
            elif et == 'POLYLINE':
                for v in e.vertices:
                    xs.append(v.dxf.location.x); ys.append(v.dxf.location.y)
        if xs and ys:
            result['bbox_mm'] = [min(xs), min(ys), max(xs), max(ys)]
    except Exception:
        pass

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

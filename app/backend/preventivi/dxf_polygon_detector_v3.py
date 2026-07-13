"""DXF Polygon Detector v3 — Shapely-based con confidence + candidati per UI manuale.

Riscrittura completa che sostituisce l'algoritmo custom del v2 con Shapely
(libreria industriale per operazioni geometriche 2D). Vantaggi:

- Polygon.area / .length / .contains sono robusti e testati su 10+ anni di prod
- Nested holes detection via `.contains()` diretto invece di raycasting custom
- Difference / union / buffer disponibili se serve refinement
- Prepared geometries per performance su tante contains() queries

Output arricchito rispetto al v2:
- Lista completa candidati con score/rank
- Confidence globale (0-1) — se bassa, frontend chiede conferma manuale
- Per ogni candidato: bbox, area, n_holes, geometry_json (per rendering overlay)

API pubblica: `detect_pezzo_geometry_v3(path, config) -> dict`
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any

import ezdxf
from ezdxf.path import make_path

try:
    from shapely.geometry import Polygon, Point, MultiPolygon
    from shapely.geometry.polygon import orient
    from shapely.prepared import prep
    from shapely.validation import make_valid
    _HAS_SHAPELY = True
except ImportError:
    _HAS_SHAPELY = False

logger = logging.getLogger(__name__)


# Formati foglio ISO standard (mm) — larghezza x altezza (ordinato)
FORMATI_FOGLIO_ISO_MM = [
    (1189.0, 841.0), (841.0, 594.0), (594.0, 420.0),
    (420.0, 297.0), (297.0, 210.0),
]

# Layer che tipicamente contengono cartiglio / annotazioni (case insensitive)
LAYER_DA_ESCLUDERE_PATTERNS = (
    'dim', 'quote', 'quota', 'text', 'testo', 'annot',
    'hatch', 'tratteggio', 'cartiglio', 'frame', 'border',
    'cornice', 'logo', 'symb', 'mark', 'note', 'tit', 'format',
)

TIPI_ANNOTAZIONE = {
    'DIMENSION', 'MTEXT', 'TEXT', 'INSERT', 'ATTRIB', 'ATTDEF',
    'LEADER', 'MULTILEADER', 'HATCH', 'IMAGE', 'VIEWPORT',
}

# Tolleranze
# BUG FIX #5: TOL_ENDPOINT_MM ora ADATTIVO in base alla dimensione del DXF.
# Prima era fisso a 0.5mm → falliva su DXF con gap 0.6-1.5mm tipici di
# SolidWorks/AutoCAD (round-off doppia precisione + import/export tra formati).
# Alzarlo globalmente a 2mm però rompeva pezzi piccoli (chain spurie).
# Formula: `max(0.5, min_bbox_dim * 0.002)` — 0.2% del lato più corto, minimo 0.5mm.
# Per un pezzo 50×50mm → tol=0.5mm. Per un pezzo 1000×500mm → tol=1mm.
# Per un pezzo 2000×1500mm → tol=3mm.
TOL_ENDPOINT_MM = 0.5  # default (usato se DXF bbox non calcolabile)
TOL_CARTIGLIO_PCT = 0.05
FLATTEN_DISTANCE_MM = 0.2
MIN_VERTICI_CHAIN = 4
MIN_SEGMENTI_CHAIN = 3


def _adaptive_tol(dxf_min_dim_mm: float) -> float:
    """Ritorna tolleranza endpoint chain-walking scalata al DXF.
    Usa 0.2% del lato più corto del bbox globale, con floor 0.5mm e ceiling 3mm."""
    if dxf_min_dim_mm <= 0:
        return TOL_ENDPOINT_MM
    return max(0.5, min(3.0, dxf_min_dim_mm * 0.002))
MIN_AREA_MM2 = 1.0                   # sotto questa area = artefatto/rumore
RATIO_RETTANGOLO_PURO = 0.95         # ratio area/bbox_area ≥ questo = rettangolo
MAX_VERTICI_RETTANGOLO = 12
MIN_BBOX_CORNICE_MM = 200.0          # cornice = rett puro con bbox ≥ N mm entrambe dim
MIN_CONTENUTI_CORNICE = 6            # cornice "custom" = rett puro con ≥ N contenuti

# Confidence thresholds
CONF_ALTA = 0.85
CONF_MEDIA = 0.6
CONF_BASSA = 0.3


# ============================================================================
# Layer / entity filtering
# ============================================================================

def _layer_da_escludere(layer_name: str) -> bool:
    n = (layer_name or '').strip().lower()
    if not n:
        return False
    return any(p in n for p in LAYER_DA_ESCLUDERE_PATTERNS)


def _entity_color_excluded(entity, colori_esclusi: set[int]) -> bool:
    try:
        c = entity.dxf.color
        return c in colori_esclusi
    except AttributeError:
        return False


def _flatten_entity(entity, distance: float = FLATTEN_DISTANCE_MM) -> list[tuple[float, float]] | None:
    try:
        p = make_path(entity)
        if len(p) == 0:
            return None
        verts = [(v.x, v.y) for v in p.flattening(distance)]
        return verts if len(verts) >= 2 else None
    except Exception:
        return None


def _is_closed_geom(verts: list[tuple[float, float]], tol: float = TOL_ENDPOINT_MM) -> bool:
    if len(verts) < 3:
        return False
    return math.hypot(verts[-1][0] - verts[0][0], verts[-1][1] - verts[0][1]) <= tol


# ============================================================================
# Estrazione poligoni raw
# ============================================================================

def _extract_polygons(msp, colori_esclusi: set[int]) -> tuple[list, list]:
    """Restituisce (closed_polygons, open_segments) come liste di list[Vertex]."""
    closed = []
    opens = []

    for entity in msp:
        et = entity.dxftype()
        if et in TIPI_ANNOTAZIONE:
            continue
        try:
            if _layer_da_escludere(entity.dxf.layer):
                continue
        except AttributeError:
            pass
        if _entity_color_excluded(entity, colori_esclusi):
            continue

        if et == 'CIRCLE':
            verts = _flatten_entity(entity)
            if verts and len(verts) >= 3:
                closed.append(verts)
            continue
        if et == 'ELLIPSE':
            verts = _flatten_entity(entity)
            if verts and _is_closed_geom(verts):
                closed.append(verts)
            continue
        if et in ('LWPOLYLINE', 'POLYLINE'):
            verts = _flatten_entity(entity)
            if verts is None:
                continue
            try:
                closed_flag = bool(entity.closed) if et == 'LWPOLYLINE' else bool(getattr(entity, 'is_closed', False))
            except Exception:
                closed_flag = False
            if closed_flag or _is_closed_geom(verts):
                closed.append(verts)
            else:
                opens.append((verts[0], verts[-1], verts))
            continue
        if et == 'SPLINE':
            verts = _flatten_entity(entity)
            if verts is None:
                continue
            if _is_closed_geom(verts):
                closed.append(verts)
            else:
                opens.append((verts[0], verts[-1], verts))
            continue
        if et == 'ARC':
            verts = _flatten_entity(entity)
            if verts is None:
                continue
            try:
                sweep = (entity.dxf.end_angle - entity.dxf.start_angle) % 360.0
            except Exception:
                sweep = 0.0
            if sweep >= 359.9 or _is_closed_geom(verts):
                closed.append(verts)
            else:
                opens.append((verts[0], verts[-1], verts))
            continue
        if et == 'LINE':
            try:
                s = (entity.dxf.start.x, entity.dxf.start.y)
                e = (entity.dxf.end.x, entity.dxf.end.y)
                opens.append((s, e, [s, e]))
            except AttributeError:
                continue

    return closed, opens


def _chain_polygons(opens: list, tol: float = TOL_ENDPOINT_MM) -> list[list[tuple[float, float]]]:
    """Assembla open segments in poligoni chiusi via walk endpoint."""
    if not opens:
        return []

    def _key(pt):
        return (int(round(pt[0] / tol)), int(round(pt[1] / tol)))

    idx: dict = {}
    for i, (s, e, _v) in enumerate(opens):
        idx.setdefault(_key(s), []).append((i, 'start'))
        idx.setdefault(_key(e), []).append((i, 'end'))

    visited = set()
    polys = []

    for seed in range(len(opens)):
        if seed in visited:
            continue
        chain = []
        cur = seed
        orient_dir = 'forward'
        start_pt = opens[seed][0]
        last_pt = start_pt
        local = set()

        for _ in range(len(opens) + 5):
            if cur in local:
                break
            local.add(cur)
            s, e, v = opens[cur]
            if orient_dir == 'forward':
                chain.extend(v if not chain else v[1:])
                nxt_pt = e
            else:
                rev = list(reversed(v))
                chain.extend(rev if not chain else rev[1:])
                nxt_pt = s
            last_pt = nxt_pt

            if len(chain) >= MIN_VERTICI_CHAIN and math.hypot(last_pt[0] - start_pt[0], last_pt[1] - start_pt[1]) <= tol:
                if len(local) >= MIN_SEGMENTI_CHAIN:
                    visited.update(local)
                    polys.append(chain)
                break

            candidates = idx.get(_key(last_pt), [])
            nxt_idx = None
            nxt_ori = 'forward'
            for ci, ct in candidates:
                if ci in local or ci in visited:
                    continue
                nxt_idx = ci
                nxt_ori = 'forward' if ct == 'start' else 'backward'
                break
            if nxt_idx is None:
                break
            cur = nxt_idx
            orient_dir = nxt_ori

    return polys


# ============================================================================
# Shapely wrapping
# ============================================================================

def _to_shapely(verts: list[tuple[float, float]]):
    """Costruisce Polygon Shapely; se non valido, tenta make_valid."""
    if len(verts) < 3:
        return None
    try:
        poly = Polygon(verts)
        if not poly.is_valid:
            poly = make_valid(poly)
            if hasattr(poly, 'geoms'):
                # MultiPolygon → prendi il più grande
                polys = [g for g in poly.geoms if hasattr(g, 'area')]
                if not polys:
                    return None
                poly = max(polys, key=lambda g: g.area)
        if poly.area < MIN_AREA_MM2:
            return None
        return poly
    except Exception as e:
        logger.debug("shapely polygon creation failed: %s", e)
        return None


def _is_iso_format(poly) -> bool:
    """True se bbox del poligono coincide con formato foglio ISO."""
    minx, miny, maxx, maxy = poly.bounds
    w = maxx - minx
    h = maxy - miny
    w_max = max(w, h)
    h_min = min(w, h)
    for ws, hs in FORMATI_FOGLIO_ISO_MM:
        if (abs(w_max - ws) / ws <= TOL_CARTIGLIO_PCT and
                abs(h_min - hs) / hs <= TOL_CARTIGLIO_PCT):
            return True
    return False


def _is_rectangle_like(poly, ratio_min: float = RATIO_RETTANGOLO_PURO) -> bool:
    """True se area/bbox_area ≥ ratio_min (forma quasi rettangolare)."""
    minx, miny, maxx, maxy = poly.bounds
    bbox_area = (maxx - minx) * (maxy - miny)
    if bbox_area <= 0:
        return False
    return (poly.area / bbox_area) >= ratio_min


def _is_cornice_cartiglio(poly, all_polys: list, min_bbox_mm: float = MIN_BBOX_CORNICE_MM,
                          min_contenuti: int = MIN_CONTENUTI_CORNICE) -> bool:
    """Cornice = rettangolo puro grande che CONTIENE altri poligoni (cartiglio+pezzo).
    Una piastra rettangolare NUDA (senza fori/dettagli) NON è cornice.

    BUG FIX #6: prima marcava come cornice ogni rettangolo ≥200mm indipendentemente
    dal contenuto → piastre lisce 300×200mm venivano scartate → detector cadeva sui
    contenuti del cartiglio → dimensioni sbagliate. Ora richiedo sempre che la
    "cornice" contenga almeno N altri poligoni (cioè sia effettivamente una cornice
    esterna del disegno tecnico, non un pezzo rettangolare puro).
    """
    if not _is_rectangle_like(poly):
        return False
    minx, miny, maxx, maxy = poly.bounds
    bw = maxx - minx
    bh = maxy - miny
    prep_poly = prep(poly)
    n_contained = sum(1 for other in all_polys if other is not poly and prep_poly.contains(other.representative_point()))
    # a) cornice GRANDE (≥200mm) e con almeno 3 poligoni contenuti (cartiglio+pezzo+dettagli)
    if bw >= min_bbox_mm and bh >= min_bbox_mm and n_contained >= 3:
        return True
    # b) cornice "strana" (lunga-stretta) con molti contenuti
    return n_contained >= min_contenuti


# ============================================================================
# Confidence scoring
# ============================================================================

def _score_candidate(poly, all_polys: list, circles_centri: list) -> dict:
    """Calcola score/features di un candidato pezzo.

    Score composto da:
    - n_circles: n° CIRCLE contenuti (fori del pezzo) — segnale forte
    - n_inner: n° altri poligoni contenuti (fori/dettagli)
    - area_rel: area relativa (rispetto al max)
    - is_rectangle: penalità se rettangolo puro (potrebbe essere cornice)
    """
    prep_poly = prep(poly)
    n_circles = sum(1 for cx, cy in circles_centri if prep_poly.contains(Point(cx, cy)))
    n_inner = sum(1 for other in all_polys if other is not poly and prep_poly.contains(other.representative_point()))
    return {
        'n_circles': n_circles,
        'n_inner': n_inner,
        'area': poly.area,
        'is_rectangle': _is_rectangle_like(poly),
        'bbox': poly.bounds,
        'perimeter': poly.length,
    }


def _pick_outer_with_confidence(candidates: list, all_polys: list, circles_centri: list) -> tuple[int, float, list]:
    """Sceglie l'outer con score composito + confidence globale.

    Returns:
        (idx_best, confidence, all_scored)
    """
    if not candidates:
        return -1, 0.0, []

    max_area = max(c.area for c in candidates)
    scored = []
    for i, poly in enumerate(candidates):
        f = _score_candidate(poly, all_polys, circles_centri)
        # Score composito (higher = più probabile pezzo):
        # 1. Ogni CIRCLE contenuto = +10 (forte segnale pezzo con fori)
        # 2. Ogni sub-poligono contenuto = +2 (dettagli/asole)
        # 3. Area relativa = 0-5 punti
        # 4. Rettangolo puro = -5 (potrebbe essere cornice)
        area_rel = (f['area'] / max_area) if max_area > 0 else 0
        score = (
            f['n_circles'] * 10.0
            + f['n_inner'] * 2.0
            + area_rel * 5.0
            + (-5.0 if f['is_rectangle'] else 0.0)
        )
        scored.append({'idx': i, 'poly': poly, 'features': f, 'score': score})

    scored.sort(key=lambda x: x['score'], reverse=True)
    best = scored[0]
    best_idx = best['idx']

    # Confidence: distanza tra top-1 e top-2 (se score simili → bassa confidence)
    if len(scored) >= 2:
        gap = best['score'] - scored[1]['score']
        # gap grande (>10) → alta confidence
        # gap piccolo (<3) → bassa confidence
        confidence = min(1.0, max(0.1, gap / 15.0))
    else:
        confidence = 1.0 if best['score'] > 5 else 0.5

    # Boost/penalità finali
    if best['features']['n_circles'] >= 2:
        confidence = min(1.0, confidence + 0.2)  # ha fori → sicuramente un pezzo
    if best['features']['is_rectangle'] and best['features']['n_circles'] == 0:
        confidence = min(confidence, 0.5)  # rett puro senza fori → dubbio (potrebbe essere cornice)

    return best_idx, round(confidence, 3), scored


# ============================================================================
# API pubblica
# ============================================================================

def detect_pezzo_geometry_v3(path: str, config: dict | None = None) -> dict:
    """Estrae geometria pezzo da DXF con Shapely + confidence + candidati.

    Returns:
        {
            area_dm2, area_lorda_dm2, perimetro_taglio_m, n_pierce, n_inner,
            bbox_width_mm, bbox_height_mm,
            confidence: 0-1,
            confidence_label: 'alta' | 'media' | 'bassa' | 'nessuna',
            needs_manual_select: bool,
            candidates: [
                {idx, area_dm2, perimetro_m, bbox: [minx,miny,maxx,maxy],
                 n_circles, n_inner, score, geometry: [[x,y], ...]},
                ...
            ],
            selected_candidate_idx: int,
            warnings: [str],
        }
    """
    if not _HAS_SHAPELY:
        return _empty_result(['Shapely non installato — installalo con: pip install shapely'])

    cfg = config or {}
    colori_esclusi = set(cfg.get('dxf_colori_piega', [2])) | set(cfg.get('dxf_colori_saldatura', [1]))
    warnings: list[str] = []

    try:
        doc = ezdxf.readfile(path)
    except Exception as e:
        return _empty_result([f'DXF non leggibile: {e}'])

    msp = doc.modelspace()

    # ---- 1. Estrai poligoni + segmenti aperti
    closed_raw, opens = _extract_polygons(msp, colori_esclusi)

    # ---- 2. Chain walking: tolleranza adattiva basata sul bbox del DXF
    #        (BUG FIX #5 — piccoli pezzi 0.5mm, grandi pezzi fino 3mm)
    _dxf_min_dim = 0
    try:
        _all_verts = []
        for _v in closed_raw + opens:
            _all_verts.extend(_v)
        if _all_verts:
            _xs = [_v[0] for _v in _all_verts]
            _ys = [_v[1] for _v in _all_verts]
            _dxf_min_dim = min(max(_xs) - min(_xs), max(_ys) - min(_ys))
    except Exception:
        pass
    _tol = _adaptive_tol(_dxf_min_dim)
    chained_raw = _chain_polygons(opens, tol=_tol)
    all_raw = closed_raw + chained_raw

    if not all_raw:
        return _empty_result(['Nessun poligono chiuso rilevato'])

    # ---- 3. Converti a Shapely (filtra invalidi/troppo piccoli)
    all_polys = []
    for verts in all_raw:
        p = _to_shapely(verts)
        if p is not None:
            all_polys.append(p)

    if not all_polys:
        return _empty_result(['Poligoni non validi (area < 1 mm² o self-intersect)'])

    # ---- 4. Circles centri (per scoring)
    circles_centri = []
    for e in msp:
        if e.dxftype() != 'CIRCLE':
            continue
        try:
            if _layer_da_escludere(e.dxf.layer):
                continue
        except AttributeError:
            pass
        if _entity_color_excluded(e, colori_esclusi):
            continue
        try:
            circles_centri.append((float(e.dxf.center.x), float(e.dxf.center.y)))
        except AttributeError:
            continue

    # ---- 5. Filtra cartiglio (ISO + cornici custom)
    cartiglio_count = 0
    candidati = []
    for p in all_polys:
        if _is_iso_format(p):
            cartiglio_count += 1
            continue
        if _is_cornice_cartiglio(p, all_polys):
            cartiglio_count += 1
            continue
        candidati.append(p)

    if not candidati:
        return _empty_result([f'Solo {cartiglio_count} cornici/cartigli rilevati, nessun pezzo'])

    # ---- 6. Pick best outer + confidence
    best_idx, confidence, all_scored = _pick_outer_with_confidence(candidati, candidati, circles_centri)
    outer = candidati[best_idx]

    # ---- 7. Inner holes (contenuti nell'outer)
    prep_outer = prep(outer)
    inners = [p for i, p in enumerate(candidati) if i != best_idx and prep_outer.contains(p.representative_point())]

    # ---- 8. Calcoli finali
    area_outer_mm2 = outer.area
    area_inner_mm2 = sum(p.area for p in inners)
    area_netta_mm2 = max(0.0, area_outer_mm2 - area_inner_mm2)
    perim_outer_mm = outer.length
    perim_inner_mm = sum(p.length for p in inners)
    perim_totale_mm = perim_outer_mm + perim_inner_mm
    minx, miny, maxx, maxy = outer.bounds
    bbox_w_mm = maxx - minx
    bbox_h_mm = maxy - miny
    n_pierce = 1 + len(inners)

    # ---- 9. Confidence label
    if confidence >= CONF_ALTA:
        conf_label = 'alta'
        needs_manual = False
    elif confidence >= CONF_MEDIA:
        conf_label = 'media'
        needs_manual = False
    elif confidence >= CONF_BASSA:
        conf_label = 'bassa'
        needs_manual = True
        warnings.append(f'Confidence bassa ({confidence:.0%}) — verificare selezione pezzo')
    else:
        conf_label = 'nessuna'
        needs_manual = True
        warnings.append(f'Nessuna confidenza sul pezzo detectato — selezione manuale richiesta')

    # ---- 10. Costruisci lista candidati per UI (top N per score)
    candidates_out = []
    for c in all_scored[:20]:  # max 20 candidati (per non appesantire UI)
        p = c['poly']
        # Discretizza geometria per rendering overlay SVG (max 200 punti)
        coords = list(p.exterior.coords)
        if len(coords) > 200:
            step = len(coords) // 200
            coords = coords[::step]
        candidates_out.append({
            'idx': c['idx'],
            'area_dm2': round(p.area / 10000.0, 4),
            'perimetro_m': round(p.length / 1000.0, 4),
            'bbox': [round(v, 2) for v in p.bounds],
            'n_circles': c['features']['n_circles'],
            'n_inner': c['features']['n_inner'],
            'score': round(c['score'], 2),
            'is_rectangle': c['features']['is_rectangle'],
            'is_selected': c['idx'] == best_idx,
            'geometry': [[round(x, 2), round(y, 2)] for x, y in coords],
        })

    # Bbox globale DXF in mm — usato dal frontend per calcolare scale SVG unit → mm
    try:
        from ezdxf.bbox import extents
        bb = extents(msp)
        if bb.has_data:
            dxf_bbox_mm = [round(bb.extmin.x, 3), round(bb.extmin.y, 3),
                            round(bb.extmax.x, 3), round(bb.extmax.y, 3)]
        else:
            dxf_bbox_mm = None
    except Exception:
        dxf_bbox_mm = None

    return {
        'area_dm2': round(area_netta_mm2 / 10000.0, 4),
        'area_lorda_dm2': round(area_outer_mm2 / 10000.0, 4),
        'perimetro_taglio_m': round(perim_totale_mm / 1000.0, 4),
        'n_pierce': n_pierce,
        'n_forature': n_pierce,  # alias per compat v2/v1
        'n_inner': len(inners),
        'bbox_width_mm': round(bbox_w_mm, 2),
        'bbox_height_mm': round(bbox_h_mm, 2),
        'confidence': confidence,
        'confidence_label': conf_label,
        'needs_manual_select': needs_manual,
        'candidates': candidates_out,
        'selected_candidate_idx': best_idx,
        'poligoni_grezzi': len(all_raw),
        'poligoni_cartiglio_rimossi': cartiglio_count,
        'tipo_disegno': 'v3_shapely',
        'warnings': warnings,
        'dxf_bbox_mm': dxf_bbox_mm,  # [minx, miny, maxx, maxy] per scale SVG→mm
        '_engine': 'shapely-' + __import__('shapely').__version__,
    }


def _empty_result(warnings: list[str]) -> dict:
    return {
        'area_dm2': 0.0, 'area_lorda_dm2': 0.0, 'perimetro_taglio_m': 0.0,
        'n_pierce': 0, 'n_forature': 0, 'n_inner': 0,
        'bbox_width_mm': 0.0, 'bbox_height_mm': 0.0,
        'confidence': 0.0, 'confidence_label': 'nessuna',
        'needs_manual_select': True,
        'candidates': [], 'selected_candidate_idx': -1,
        'poligoni_grezzi': 0, 'poligoni_cartiglio_rimossi': 0,
        'tipo_disegno': 'vuoto', 'warnings': warnings,
    }


def compute_geometry_from_region(path: str, region_bbox: tuple[float, float, float, float],
                                  config: dict | None = None) -> dict:
    """Calcola area/perim/n_pierce prendendo tutti i poligoni chiusi la cui
    bbox interseca (o è contenuta) nella region_bbox utente.

    Il pattern d'uso è: l'utente disegna col mouse un rettangolo attorno al
    pezzo nella preview DXF. Il backend prende tutti i contorni chiusi dentro
    quella regione, identifica outer (area max) e inner (contenuti nell'outer),
    calcola area netta + perimetro + n_pierce.

    Args:
        path: percorso DXF
        region_bbox: (minx, miny, maxx, maxy) in coord DXF (mm)
        config: dict optional (colori esclusi)

    Returns:
        dict compat con `detect_pezzo_geometry_v3` (senza candidates).
    """
    if not _HAS_SHAPELY:
        return _empty_result(['Shapely non installato'])
    cfg = config or {}
    colori_esclusi = set(cfg.get('dxf_colori_piega', [2])) | set(cfg.get('dxf_colori_saldatura', [1]))

    try:
        doc = ezdxf.readfile(path)
    except Exception as e:
        return _empty_result([f'DXF non leggibile: {e}'])
    msp = doc.modelspace()

    # Region utente come Polygon
    minx, miny, maxx, maxy = region_bbox
    if minx == maxx or miny == maxy:
        return _empty_result(['Regione degenere (larghezza o altezza = 0)'])
    from shapely.geometry import box
    region = box(min(minx, maxx), min(miny, maxy), max(minx, maxx), max(miny, maxy))

    # Estrai poligoni + chain walking
    closed_raw, opens = _extract_polygons(msp, colori_esclusi)
    all_raw = closed_raw + _chain_polygons(opens)
    all_polys = [p for p in (_to_shapely(v) for v in all_raw) if p is not None]

    # Filtra poligoni la cui bbox interseca la region utente
    # (`intersects` è più tollerante di `within` per selezioni approssimative)
    in_region = [p for p in all_polys if p.intersects(region)]

    # Filtri cartiglio in selezione manuale:
    # 1. Formati ISO standard (A4/A3/...)
    # 2. Bbox molto più grande della region utente (soglia 2x per lato o 3x area)
    #    → cornice/cartiglio esterno alla vera intenzione dell'utente
    region_w = maxx - minx
    region_h = maxy - miny
    region_area = region.area
    MAX_BBOX_RATIO = 2.0    # bbox width/height max 2x region
    MAX_AREA_RATIO = 3.0    # area max 3x region
    def _too_big(p):
        minx_p, miny_p, maxx_p, maxy_p = p.bounds
        pw = maxx_p - minx_p
        ph = maxy_p - miny_p
        if pw > region_w * MAX_BBOX_RATIO or ph > region_h * MAX_BBOX_RATIO:
            return True
        if p.area > region_area * MAX_AREA_RATIO:
            return True
        return False
    in_region = [p for p in in_region if not _is_iso_format(p) and not _too_big(p)]

    if not in_region:
        return _empty_result(['Nessun contorno chiuso trovato nella regione selezionata. Prova a disegnare un\'area più ampia (o meno ampia se hai selezionato l\'intero disegno).'])

    # Raccogli centri CIRCLE nella region (per scoring)
    circles_centri_in_region = []
    for e in msp:
        if e.dxftype() != 'CIRCLE':
            continue
        try:
            if _layer_da_escludere(e.dxf.layer):
                continue
        except AttributeError:
            pass
        if _entity_color_excluded(e, colori_esclusi):
            continue
        try:
            cx, cy = float(e.dxf.center.x), float(e.dxf.center.y)
            if region.contains(Point(cx, cy)):
                circles_centri_in_region.append((cx, cy))
        except AttributeError:
            continue

    # Outer = poligono che contiene PIÙ CIRCLE (segnale forte pezzo con fori)
    # Tie-break su area (per casi senza fori)
    def _score(p):
        prep_p = prep(p)
        n_circ = sum(1 for cx, cy in circles_centri_in_region if prep_p.contains(Point(cx, cy)))
        return (n_circ, p.area)
    outer = max(in_region, key=_score)
    prep_outer = prep(outer)
    inners = [p for p in in_region if p is not outer and prep_outer.contains(p.representative_point())]

    area_outer_mm2 = outer.area
    area_inner_mm2 = sum(p.area for p in inners)
    area_netta_mm2 = max(0.0, area_outer_mm2 - area_inner_mm2)
    perim_outer_mm = outer.length
    perim_inner_mm = sum(p.length for p in inners)
    perim_totale_mm = perim_outer_mm + perim_inner_mm
    minx_p, miny_p, maxx_p, maxy_p = outer.bounds
    bbox_w_mm = maxx_p - minx_p
    bbox_h_mm = maxy_p - miny_p
    n_pierce = 1 + len(inners)

    return {
        'area_dm2': round(area_netta_mm2 / 10000.0, 4),
        'area_lorda_dm2': round(area_outer_mm2 / 10000.0, 4),
        'perimetro_taglio_m': round(perim_totale_mm / 1000.0, 4),
        'n_pierce': n_pierce,
        'n_forature': n_pierce,
        'n_inner': len(inners),
        'bbox_width_mm': round(bbox_w_mm, 2),
        'bbox_height_mm': round(bbox_h_mm, 2),
        'confidence': 1.0,
        'confidence_label': 'manuale',
        'needs_manual_select': False,
        'candidates': [],
        'selected_candidate_idx': -1,
        'poligoni_grezzi': len(all_raw),
        'poligoni_cartiglio_rimossi': 0,
        'tipo_disegno': 'v3_region_manual',
        'warnings': [f'Regione manuale utente: {len(in_region)} contorni trovati (1 outer + {len(inners)} interni)'],
        '_engine': 'shapely-region',
    }


def compute_geometry_from_point(path: str, x_mm: float, y_mm: float,
                                config: dict | None = None) -> dict:
    """Pattern 'Detect Part' Lantek-style: click su un ELEMENTO del contorno
    esterno del pezzo → sistema chain-walka il perimetro completo + trova
    tutta la geometria interna.

    A differenza di 'contains(point)', qui l'utente clicca SU UNA LINEA (bordo
    visibile), non nel vuoto interno del pezzo. Vantaggi:
    - Non serve trovare un punto interno (in pezzi con molti fori è difficile)
    - Funziona anche se il chain walking non chiude perfettamente il contorno
      (basta essere abbastanza vicini a un edge conosciuto)
    - Gesto naturale (sottolineare un bordo col mouse)

    Args:
        path: percorso DXF
        x_mm, y_mm: punto cliccato in coord DXF (mm)
        config: dict optional colori esclusi

    Strategia:
    1. Estrae tutti i poligoni chiusi (native + chain walking)
    2. Per ogni poligono (skip cartigli ISO), calcola la distanza minima tra
       il click point e l'exterior boundary
    3. Filtra quelli con distanza <= TOL_EDGE_MM (click abbastanza vicino a un bordo)
    4. Sort: (distanza in bucket da 2mm asc, area asc)
       → il più vicino, tie-break sul più piccolo (evita cartiglio esterno)
    5. Se nessuno entro tolleranza, fallback a "contains" per compat
    6. Trova gli inner: poligoni contenuti nell'outer scelto

    Returns: dict compat con detect_pezzo_geometry_v3
    """
    if not _HAS_SHAPELY:
        return _empty_result(['Shapely non installato'])
    cfg = config or {}
    colori_esclusi = set(cfg.get('dxf_colori_piega', [2])) | set(cfg.get('dxf_colori_saldatura', [1]))

    try:
        doc = ezdxf.readfile(path)
    except Exception as e:
        return _empty_result([f'DXF non leggibile: {e}'])
    msp = doc.modelspace()

    from shapely.geometry import Point
    click_pt = Point(x_mm, y_mm)

    # Estrai poligoni + chain walking
    closed_raw, opens = _extract_polygons(msp, colori_esclusi)
    all_raw = closed_raw + _chain_polygons(opens)
    all_polys = [p for p in (_to_shapely(v) for v in all_raw) if p is not None]
    # Escludi cartigli ISO standard (A4/A3/...)
    non_cartiglio = [p for p in all_polys if not _is_iso_format(p)]

    if not non_cartiglio:
        return _empty_result([
            f'Nessun contorno rilevato (solo cartigli). '
            f'Verifica che il DXF contenga geometria di taglio valida.'
        ])

    # ---- Strategia PRIMARIA: click SU un edge del bordo esterno ----
    # Tolleranza adattiva: 2% della dimensione minima del DXF globale, clamp [5, 30] mm
    try:
        from ezdxf.bbox import extents
        bb = extents(msp)
        if bb.has_data:
            dxf_w = bb.extmax.x - bb.extmin.x
            dxf_h = bb.extmax.y - bb.extmin.y
            min_dim = min(dxf_w, dxf_h)
        else:
            min_dim = 200.0
    except Exception:
        min_dim = 200.0
    TOL_EDGE_MM = max(5.0, min(30.0, min_dim * 0.02))

    candidates_with_dist = []
    for p in non_cartiglio:
        d = p.exterior.distance(click_pt)
        if d <= TOL_EDGE_MM:
            candidates_with_dist.append((d, p))

    if candidates_with_dist:
        # Bucket distanza da 2mm — poi tie-break su area (più piccolo = pezzo, non cartiglio)
        candidates_with_dist.sort(key=lambda item: (int(item[0] / 2.0), item[1].area))
        outer = candidates_with_dist[0][1]
        strategia = f'edge-click (dist={candidates_with_dist[0][0]:.1f}mm, tol={TOL_EDGE_MM:.1f}mm)'
    else:
        # ---- Fallback: click DENTRO il pezzo (contains) ----
        contengono_click = [p for p in non_cartiglio if p.contains(click_pt) or p.touches(click_pt)]
        if not contengono_click:
            return _empty_result([
                f'Nessun contorno vicino a ({x_mm:.1f}, {y_mm:.1f}) — tolleranza {TOL_EDGE_MM:.1f}mm. '
                f'Clicca SU una linea del bordo esterno del pezzo.'
            ])
        outer = min(contengono_click, key=lambda p: p.area)
        strategia = 'contains-fallback'

    prep_outer = prep(outer)

    # Inner: tutti i poligoni contenuti nell'outer (fori, dettagli, sub-contorni)
    inners = [p for p in all_polys if p is not outer and prep_outer.contains(p.representative_point())]

    area_outer_mm2 = outer.area
    area_inner_mm2 = sum(p.area for p in inners)
    area_netta_mm2 = max(0.0, area_outer_mm2 - area_inner_mm2)
    perim_outer_mm = outer.length
    perim_inner_mm = sum(p.length for p in inners)
    perim_totale_mm = perim_outer_mm + perim_inner_mm
    minx_p, miny_p, maxx_p, maxy_p = outer.bounds
    n_pierce = 1 + len(inners)

    # dxf_bbox_mm per compat con frontend scale factor
    try:
        from ezdxf.bbox import extents
        bb = extents(msp)
        dxf_bbox_mm = [round(bb.extmin.x, 3), round(bb.extmin.y, 3),
                        round(bb.extmax.x, 3), round(bb.extmax.y, 3)] if bb.has_data else None
    except Exception:
        dxf_bbox_mm = None

    return {
        'area_dm2': round(area_netta_mm2 / 10000.0, 4),
        'area_lorda_dm2': round(area_outer_mm2 / 10000.0, 4),
        'perimetro_taglio_m': round(perim_totale_mm / 1000.0, 4),
        'n_pierce': n_pierce,
        'n_forature': n_pierce,
        'n_inner': len(inners),
        'bbox_width_mm': round(maxx_p - minx_p, 2),
        'bbox_height_mm': round(maxy_p - miny_p, 2),
        'confidence': 1.0,
        'confidence_label': 'manuale',
        'needs_manual_select': False,
        'candidates': [],
        'selected_candidate_idx': -1,
        'poligoni_grezzi': len(all_raw),
        'poligoni_cartiglio_rimossi': 0,
        'tipo_disegno': 'v3_point_click',
        'warnings': [f'Trova pezzo ({strategia}): {len(inners)} contorni interni trovati.'],
        'dxf_bbox_mm': dxf_bbox_mm,
        '_engine': 'shapely-point',
    }


def compute_geometry_from_candidate(path: str, candidate_idx: int,
                                    config: dict | None = None) -> dict:
    """Ricalcola area/perim/n_pierce assumendo che l'utente ha scelto candidate_idx
    come outer del pezzo (invece del top-scored automatico).

    Usato dall'endpoint POST /dxf/<file>/select-polygon.
    """
    r = detect_pezzo_geometry_v3(path, config)
    if not r.get('candidates') or candidate_idx < 0:
        return r
    # Cerca candidato per idx
    cand = next((c for c in r['candidates'] if c['idx'] == candidate_idx), None)
    if not cand:
        r['warnings'] = r.get('warnings', []) + [f'Candidato {candidate_idx} non trovato']
        return r
    # Ricostruisci Polygon shapely
    if not _HAS_SHAPELY:
        return r
    outer_poly = Polygon(cand['geometry'])
    if not outer_poly.is_valid:
        outer_poly = make_valid(outer_poly)
        if hasattr(outer_poly, 'geoms'):
            outer_poly = max(outer_poly.geoms, key=lambda g: g.area)
    # Re-estrai tutti gli altri poligoni per trovare inners
    cfg = config or {}
    colori_esclusi = set(cfg.get('dxf_colori_piega', [2])) | set(cfg.get('dxf_colori_saldatura', [1]))
    try:
        doc = ezdxf.readfile(path)
    except Exception:
        return r
    msp = doc.modelspace()
    closed_raw, opens = _extract_polygons(msp, colori_esclusi)
    all_raw = closed_raw + _chain_polygons(opens)
    all_polys = [p for p in (_to_shapely(v) for v in all_raw) if p is not None]
    all_polys = [p for p in all_polys if not _is_iso_format(p) and not _is_cornice_cartiglio(p, all_polys)]

    prep_outer = prep(outer_poly)
    # Trova inners: poligoni contenuti in outer che NON siano l'outer stesso
    inners = []
    for p in all_polys:
        if p.equals(outer_poly) or p.almost_equals(outer_poly, decimal=1):
            continue
        if prep_outer.contains(p.representative_point()):
            inners.append(p)

    area_netta = outer_poly.area - sum(p.area for p in inners)
    perim = outer_poly.length + sum(p.length for p in inners)
    minx, miny, maxx, maxy = outer_poly.bounds

    r_out = dict(r)
    r_out['area_dm2'] = round(max(0.0, area_netta) / 10000.0, 4)
    r_out['area_lorda_dm2'] = round(outer_poly.area / 10000.0, 4)
    r_out['perimetro_taglio_m'] = round(perim / 1000.0, 4)
    r_out['n_inner'] = len(inners)
    r_out['n_pierce'] = 1 + len(inners)
    r_out['n_forature'] = 1 + len(inners)
    r_out['bbox_width_mm'] = round(maxx - minx, 2)
    r_out['bbox_height_mm'] = round(maxy - miny, 2)
    r_out['selected_candidate_idx'] = candidate_idx
    r_out['confidence'] = 1.0
    r_out['confidence_label'] = 'manuale'
    r_out['needs_manual_select'] = False
    r_out['warnings'] = r_out.get('warnings', []) + [f'Selezione manuale utente: candidato #{candidate_idx}']
    return r_out

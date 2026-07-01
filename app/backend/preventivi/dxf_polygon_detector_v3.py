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
TOL_ENDPOINT_MM = 0.5
TOL_CARTIGLIO_PCT = 0.05
FLATTEN_DISTANCE_MM = 0.2
MIN_VERTICI_CHAIN = 4
MIN_SEGMENTI_CHAIN = 3
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
    """Cornice = rettangolo puro grande OR rettangolo che contiene molti altri."""
    if not _is_rectangle_like(poly):
        return False
    minx, miny, maxx, maxy = poly.bounds
    bw = maxx - minx
    bh = maxy - miny
    # a) cornice grande
    if bw >= min_bbox_mm and bh >= min_bbox_mm:
        return True
    # b) cornice "strana" (lunga-stretta) che contiene molte cose
    prep_poly = prep(poly)
    n_contained = sum(1 for other in all_polys if other is not poly and prep_poly.contains(other.representative_point()))
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

    # ---- 2. Chain walking su segmenti aperti
    chained_raw = _chain_polygons(opens)
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

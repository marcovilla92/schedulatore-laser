"""pick_part — geometria pezzo DETERMINISTICA via Shapely polygonize.

Sostituisce l'auto-detect euristico (`detect_pezzo_geometry_v3`, che sul pezzo
reale 20PA00693 sbagliava l'area di 13,6×) con la ricetta raccomandata dalla
ricerca tecnica (piano fail-safe, sezione 3):

    flatten entità → node (unary_union) → polygonize → faccia scelta dal click

Filosofia (piano fail-safe):
- NESSUNA euristica di scelta automatica del contorno. La faccia del pezzo è
  scelta dal CLICK dell'operatore sul bordo (modello Lantek "Detect Part").
- Una volta scelta la faccia, area/perimetro/fori sono MATEMATICA PURA
  (shoelace / Shapely .length / .contains). Zero stima, zero silenzioso.
- Se il click non seleziona nessuna faccia valida → il chiamante BLOCCA e
  chiede all'operatore (mai un numero inventato).

Differenza chiave vs il vecchio chain-walking O(n!):
- `unary_union` fa il NODING robusto (spezza ai veri incroci) invece del walk
  endpoint fragile con tolleranze arbitrarie.
- `polygonize` costruisce tutte le facce del planar arrangement in modo testato.

API pubblica:
    pick_part_from_click(path, click_x_mm, click_y_mm, config) -> dict
    polygonize_faces(path, config) -> list[dict]   # per probe/debug e per il viewer
"""
from __future__ import annotations

import logging
import math
import os
from typing import Any

import ezdxf
from ezdxf.path import make_path

try:
    from shapely.geometry import Polygon, Point, LineString, MultiLineString
    from shapely.ops import polygonize, unary_union
    from shapely.validation import make_valid
    _HAS_SHAPELY = True
except ImportError:
    _HAS_SHAPELY = False

logger = logging.getLogger(__name__)

# Riuso delle costanti/pattern dal detector esistente per coerenza di filtro
from .dxf_polygon_detector_v3 import (
    LAYER_DA_ESCLUDERE_PATTERNS,
    TIPI_ANNOTAZIONE,
    FORMATI_FOGLIO_ISO_MM,
    FLATTEN_DISTANCE_MM,
    MIN_AREA_MM2,
    TOL_CARTIGLIO_PCT,
    _layer_da_escludere,
    _entity_color_excluded,
)


# ── Estrazione segmenti ────────────────────────────────────────────────────

def _entity_segments(entity, distance: float = FLATTEN_DISTANCE_MM) -> list[tuple]:
    """Flatten una entità DXF in una lista di segmenti [(x1,y1,x2,y2), ...].

    Ritorna lista vuota se l'entità non è flattabile (es. TEXT).
    """
    try:
        p = make_path(entity)
        if len(p) == 0:
            return []
        pts = [(v.x, v.y) for v in p.flattening(distance)]
    except Exception:
        # LINE non ha make_path in alcune versioni: fallback manuale
        if entity.dxftype() == 'LINE':
            try:
                s = entity.dxf.start
                e = entity.dxf.end
                return [(s.x, s.y, e.x, e.y)]
            except Exception:
                return []
        return []
    segs = []
    for a, b in zip(pts, pts[1:]):
        if a != b:
            segs.append((a[0], a[1], b[0], b[1]))
    return segs


def _collect_segments(msp, colori_esclusi: set[int]) -> list[tuple]:
    """Raccoglie tutti i segmenti geometrici, escludendo annotazioni/cartiglio.

    Esclude: tipi annotazione (TEXT/DIMENSION/...), layer cartiglio/quote/note,
    entità di colore escluso (pieghe/saldature configurabili).
    """
    segs = []
    for entity in msp:
        if entity.dxftype() in TIPI_ANNOTAZIONE:
            continue
        try:
            if _layer_da_escludere(entity.dxf.layer):
                continue
        except AttributeError:
            pass
        if _entity_color_excluded(entity, colori_esclusi):
            continue
        segs.extend(_entity_segments(entity))
    return segs


def _is_iso_format_bounds(bounds) -> bool:
    """True se il bbox coincide con un formato foglio ISO (cartiglio)."""
    minx, miny, maxx, maxy = bounds
    w = maxx - minx
    h = maxy - miny
    w_max, h_min = max(w, h), min(w, h)
    for ws, hs in FORMATI_FOGLIO_ISO_MM:
        if (abs(w_max - ws) / ws <= TOL_CARTIGLIO_PCT and
                abs(h_min - hs) / hs <= TOL_CARTIGLIO_PCT):
            return True
    return False


# ── Pipeline polygonize ────────────────────────────────────────────────────

def _build_faces(path: str, colori_esclusi: set[int]) -> list:
    """flatten → node → polygonize. Ritorna lista di Polygon Shapely (facce).

    Solleva RuntimeError con messaggio esplicito se il DXF non è leggibile o
    Shapely non è installato (il chiamante deve BLOCCARE, non inventare).
    """
    if not _HAS_SHAPELY:
        raise RuntimeError('Shapely non installato')
    try:
        doc = ezdxf.readfile(path)
    except Exception as e:
        raise RuntimeError(f'DXF non leggibile: {e}')
    msp = doc.modelspace()

    segs = _collect_segments(msp, colori_esclusi)
    if not segs:
        return []

    lines = [LineString([(x1, y1), (x2, y2)]) for (x1, y1, x2, y2) in segs]
    # NODING: unary_union spezza i segmenti ai veri incroci (robusto, testato)
    noded = unary_union(MultiLineString(lines))
    faces = [f for f in polygonize(noded) if f.area >= MIN_AREA_MM2]
    # Ripara facce non valide
    fixed = []
    for f in faces:
        if not f.is_valid:
            f = make_valid(f)
            if hasattr(f, 'geoms'):
                cand = [g for g in f.geoms if getattr(g, 'area', 0) >= MIN_AREA_MM2
                        and g.geom_type == 'Polygon']
                if not cand:
                    continue
                f = max(cand, key=lambda g: g.area)
        if f.geom_type == 'Polygon' and f.area >= MIN_AREA_MM2:
            fixed.append(f)
    return fixed


def _geometry_from_outer(outer, all_faces: list) -> dict:
    """Dato il poligono outer scelto, calcola area netta/perimetro/fori.

    MATEMATICA PURA: nessuna euristica. I fori sono le facce strettamente
    contenute nell'outer. area netta = area outer − aree fori.
    """
    holes = []
    for f in all_faces:
        if f is outer:
            continue
        # Faccia contenuta nell'outer (usa representative_point per robustezza)
        if outer.contains(f.representative_point()) and f.area < outer.area:
            holes.append(f)

    area_lorda_mm2 = outer.area
    area_fori_mm2 = sum(h.area for h in holes)
    area_netta_mm2 = area_lorda_mm2 - area_fori_mm2

    perim_outer_mm = outer.exterior.length
    perim_fori_mm = sum(h.exterior.length for h in holes)
    perim_taglio_mm = perim_outer_mm + perim_fori_mm

    minx, miny, maxx, maxy = outer.bounds
    return {
        'success': True,
        'area_dm2': area_netta_mm2 / 10000.0,       # mm² → dm²
        'area_lorda_dm2': area_lorda_mm2 / 10000.0,
        'perimetro_taglio_m': perim_taglio_mm / 1000.0,  # mm → m
        'perimetro_outer_m': perim_outer_mm / 1000.0,
        'n_forature': len(holes),
        'bbox_width_mm': maxx - minx,
        'bbox_height_mm': maxy - miny,
        'source': 'manual-click-polygonize',
        'warnings': [],
    }


def pick_part_from_click(path: str, click_x_mm: float, click_y_mm: float,
                         config: dict | None = None) -> dict:
    """Seleziona il pezzo dal click sul bordo (modello Lantek 'Detect Part').

    Semantica: l'operatore clicca SUL contorno (o dentro il corpo) del pezzo.
    Tra tutte le facce del polygonize (esclusi i cartigli ISO), sceglie quella
    più pertinente al click:
      1. Se il click cade DENTRO una faccia → la più piccola che lo contiene
         (evita di prendere un frame che racchiude tutto).
      2. Altrimenti → la faccia il cui bordo è più vicino al click.

    Ritorna dict con area_dm2/perimetro_taglio_m/n_forature/bbox (matematica
    pura) oppure {success: False, error, warnings} se nessuna faccia valida
    (il chiamante DEVE bloccare e chiedere all'operatore).
    """
    cfg = config or {}
    colori_esclusi = set(cfg.get('dxf_colori_piega', [2])) | set(cfg.get('dxf_colori_saldatura', [1]))

    try:
        faces = _build_faces(path, colori_esclusi)
    except RuntimeError as e:
        return {'success': False, 'error': str(e), 'warnings': [str(e)]}

    if not faces:
        return {'success': False, 'error': 'Nessuna faccia chiusa trovata nel DXF',
                'warnings': ['polygonize non ha prodotto facce: contorno aperto o solo annotazioni']}

    # Escludi cartigli ISO
    candidate = [f for f in faces if not _is_iso_format_bounds(f.bounds)]
    if not candidate:
        candidate = faces  # tutti ISO? improbabile — non filtrare

    click = Point(click_x_mm, click_y_mm)

    # 1. Facce che contengono il click → la più PICCOLA (evita frame globale)
    containing = [f for f in candidate if f.contains(click)]
    if containing:
        outer = min(containing, key=lambda f: f.area)
    else:
        # 2. Faccia col bordo più vicino al click
        outer = min(candidate, key=lambda f: f.exterior.distance(click))
        # Guardia: se il click è lontanissimo dal bordo scelto, è sospetto
        d = outer.exterior.distance(click)
        diag = math.hypot(outer.bounds[2] - outer.bounds[0],
                          outer.bounds[3] - outer.bounds[1])
        if diag > 0 and d > 0.5 * diag:
            return {'success': False,
                    'error': f'Click troppo lontano da qualsiasi contorno (dist {d:.1f}mm)',
                    'warnings': ['il click non è vicino a nessun pezzo — riprova sul bordo']}

    return _geometry_from_outer(outer, faces)


def polygonize_faces(path: str, config: dict | None = None) -> list[dict]:
    """Ritorna TUTTE le facce polygonize con i loro dati (per probe/debug e viewer).

    Ogni faccia: {area_dm2, perim_m, bbox, is_iso, centroid, exterior_xy}.
    Utile per: (a) misurare vs Lantek quale faccia è il pezzo, (b) disegnare
    gli overlay cliccabili nel CAD interno.
    """
    cfg = config or {}
    colori_esclusi = set(cfg.get('dxf_colori_piega', [2])) | set(cfg.get('dxf_colori_saldatura', [1]))
    faces = _build_faces(path, colori_esclusi)
    out = []
    for f in faces:
        minx, miny, maxx, maxy = f.bounds
        c = f.representative_point()
        out.append({
            'area_dm2': f.area / 10000.0,
            'perim_m': f.exterior.length / 1000.0,
            'bbox': [minx, miny, maxx, maxy],
            'bbox_w_mm': maxx - minx,
            'bbox_h_mm': maxy - miny,
            'is_iso': _is_iso_format_bounds(f.bounds),
            'centroid': [c.x, c.y],
        })
    # Ordina per area decrescente (il pezzo è di solito tra i più grandi non-ISO)
    out.sort(key=lambda d: d['area_dm2'], reverse=True)
    return out

"""Modello di piega 3D: dal contorno piatto CONFERMATO + le pieghe del disegno
sviluppato, costruisce le FACCE (regioni separate dalle linee di piega) e il
grafo delle cerniere, pronto per essere piegato in 3D dal viewer three.js.

La geometria pesante (spaccare il poligono lungo le cerniere, capire quale
faccia confina con quale) la fa Shapely qui, in modo robusto e deterministico.
Il frontend riceve facce + cerniere + radice e si limita a ruotare/renderizzare.

Il 3D è un'ANTEPRIMA visiva: non entra nel calcolo del prezzo.
"""
from __future__ import annotations

import math

from shapely.geometry import LineString, Polygon, Point
from shapely.ops import split, unary_union

from .dxf_scanner import estrai_pieghe_3d


def _extend_line(x1, y1, x2, y2, amount):
    """Estende un segmento di `amount` mm oltre entrambi gli estremi (per
    garantire che tagli tutto il poligono anche se la linea di piega disegnata
    non arriva ai bordi)."""
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L == 0:
        return LineString([(x1, y1), (x2, y2)])
    ux, uy = dx / L, dy / L
    return LineString([(x1 - ux * amount, y1 - uy * amount),
                       (x2 + ux * amount, y2 + uy * amount)])


def _side_of(px, py, x1, y1, x2, y2):
    """Segno del lato del punto rispetto alla retta (per associare faccia↔cerniera)."""
    return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)


def build_fold_model(path: str, outline_xy: list, thickness_mm: float,
                     config: dict | None = None) -> dict:
    """Costruisce il modello di piega.

    Args:
        path: DXF (per leggere le pieghe con estrai_pieghe_3d)
        outline_xy: contorno esterno CONFERMATO [[x,y], ...] in mm
        thickness_mm: spessore lamiera
        config: config detection

    Returns dict:
        {
          success, thickness, faces:[{id, polygon:[[x,y]..], area}],
          hinges:[{a:[x,y], b:[x,y], faceA, faceB, verso, gradi, raggio}],
          root: <id faccia base>, n_pieghe_totali, warnings
        }
    """
    warnings = []
    if not outline_xy or len(outline_xy) < 3:
        return {'success': False, 'error': 'Contorno mancante o degenere'}
    try:
        poly = Polygon(outline_xy)
        if not poly.is_valid:
            poly = poly.buffer(0)
    except Exception as e:
        return {'success': False, 'error': f'Contorno non valido: {e}'}
    if poly.is_empty or poly.area <= 0:
        return {'success': False, 'error': 'Contorno ad area nulla'}

    pieghe = estrai_pieghe_3d(path, config)
    n_tot = len(pieghe)

    # Tieni solo le cerniere che intersecano davvero il pezzo, e deduplica quelle
    # coincidenti (spesso la stessa piega è annotata su due viste).
    minx, miny, maxx, maxy = poly.bounds
    diag = math.hypot(maxx - minx, maxy - miny)
    usable = []
    for b in pieghe:
        hx1, hy1, hx2, hy2 = b['hinge']
        seg = LineString([(hx1, hy1), (hx2, hy2)])
        if not seg.intersects(poly.buffer(1.0)):
            continue
        # dedup: stessa retta (punto medio vicino + direzione simile)
        mx, my = (hx1 + hx2) / 2, (hy1 + hy2) / 2
        ang = math.atan2(hy2 - hy1, hx2 - hx1) % math.pi
        dup = False
        for u in usable:
            umx, umy, uang = u['_mid']
            if math.hypot(mx - umx, my - umy) < 3.0 and abs(ang - uang) < 0.05:
                dup = True
                break
        if dup:
            continue
        b = dict(b)
        b['_mid'] = (mx, my, ang)
        usable.append(b)

    if len(usable) < n_tot:
        warnings.append(f'{n_tot - len(usable)} pieghe duplicate/fuori pezzo ignorate')

    # Spacca il poligono lungo ogni cerniera (estesa per tagliare tutto)
    pieces = [poly]
    for b in usable:
        hx1, hy1, hx2, hy2 = b['hinge']
        cutter = _extend_line(hx1, hy1, hx2, hy2, diag)
        new_pieces = []
        for pc in pieces:
            try:
                res = split(pc, cutter)
                new_pieces.extend(list(res.geoms))
            except Exception:
                new_pieces.append(pc)
        pieces = new_pieces

    # Filtra schegge minuscole
    pieces = [p for p in pieces if p.area > poly.area * 0.005]
    faces = []
    for i, pc in enumerate(pieces):
        ext = list(pc.exterior.coords)
        faces.append({'id': i, 'polygon': [[round(x, 3), round(y, 3)] for x, y in ext],
                      'area': round(pc.area, 2), '_geom': pc})

    # Associa ogni cerniera alle due facce che separa (una per lato della retta)
    hinges_out = []
    for b in usable:
        hx1, hy1, hx2, hy2 = b['hinge']
        # punto medio spostato di poco su ciascun lato normale
        dx, dy = hx2 - hx1, hy2 - hy1
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L  # normale
        mx, my = (hx1 + hx2) / 2, (hy1 + hy2) / 2
        eps = max(diag * 0.01, 1.0)
        pA = Point(mx + nx * eps, my + ny * eps)
        pB = Point(mx - nx * eps, my - ny * eps)
        fA = fB = None
        for f in faces:
            if f['_geom'].contains(pA) or f['_geom'].distance(pA) < eps * 0.5:
                fA = f['id']
            if f['_geom'].contains(pB) or f['_geom'].distance(pB) < eps * 0.5:
                fB = f['id']
        if fA is None or fB is None or fA == fB:
            warnings.append(f"Piega {b['verso']} {b['gradi']}° non separa due facce (ignorata)")
            continue
        hinges_out.append({
            'a': [round(hx1, 3), round(hy1, 3)], 'b': [round(hx2, 3), round(hy2, 3)],
            'faceA': fA, 'faceB': fB,
            'verso': b['verso'], 'gradi': b['gradi'], 'raggio': b['raggio'],
        })

    # Radice = faccia di area maggiore (la base che resta ferma)
    root = max(faces, key=lambda f: f['_geom'].area)['id'] if faces else None

    for f in faces:
        f.pop('_geom', None)

    return {
        'success': True,
        'thickness': thickness_mm,
        'faces': faces,
        'hinges': hinges_out,
        'root': root,
        'n_pieghe_totali': n_tot,
        'n_pieghe_usate': len(hinges_out),
        'warnings': warnings,
    }

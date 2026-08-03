"""Validazione Fase 2 — contour follower vs Lantek su tutti i casi.

Per ogni caso: prova a seguire il contorno partendo da OGNI segmento lungo
(simula tutti i possibili click dell'operatore), raccoglie i loop chiusi
distinti, e verifica se ESISTE un click che produce l'area Lantek.

In produzione l'operatore fa UN click sul punto giusto; qui proviamo tutti i
click per misurare se il contorno corretto è raggiungibile e con quale click.

Aggiunge la gestione FORI: dopo il contorno esterno, i loop chiusi interni
(cerchi/asole) vengono sottratti dall'area e aggiunti al perimetro di taglio.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ezdxf
from ezdxf.path import make_path
from shapely.geometry import Polygon, LineString, MultiLineString
from shapely.ops import polygonize, unary_union

_R = Path(__file__).resolve().parent.parent.parent / "_test_input" / "regression"

# (caso, area_dm2 Lantek, perim_m Lantek)
CASES = [
    ("20PA00693-00_INOX_304_sp3mm", 1.1635, 1.0294),
    ("20R201N0401-01_INOX_304_sp3mm", 0.7414, 0.8097),
    ("38APA253-00_INOX_304_sp3mm", 0.0508, 0.1423),
    ("46PA00375-00_S235_sp12mm", 84.139, 5.131),
    ("CPPBPA0042-00_S235_sp2mm", 7.6228, 1.5609),
    ("CPPBPA0044-00_S235_sp2mm", 1.6043, 0.7487),
]


def load_segments(path):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    segs = []
    for e in msp:
        if e.dxftype() in ('DIMENSION', 'MTEXT', 'TEXT', 'INSERT', 'ATTRIB',
                           'ATTDEF', 'LEADER', 'HATCH'):
            continue
        try:
            if e.dxf.layer in ('FORMAT', 'TESTO'):
                continue
        except Exception:
            pass
        try:
            p = make_path(e)
            pts = [(v.x, v.y) for v in p.flattening(0.3)]
            for a, b in zip(pts, pts[1:]):
                if a != b:
                    segs.append((a, b))
        except Exception:
            if e.dxftype() == 'LINE':
                s, en = e.dxf.start, e.dxf.end
                segs.append(((s.x, s.y), (en.x, en.y)))
    return segs


def build_graph(segs, tol=0.15):
    def key(p):
        return (round(p[0] / tol), round(p[1] / tol))
    nodes, adj = {}, {}
    for a, b in segs:
        ka, kb = key(a), key(b)
        nodes.setdefault(ka, a)
        nodes.setdefault(kb, b)
        if ka == kb:
            continue
        adj.setdefault(ka, set()).add(kb)
        adj.setdefault(kb, set()).add(ka)
    return nodes, adj, key


def follow(nodes, adj, ka, kb, max_steps=300000):
    loop = [ka, kb]
    prev, cur = ka, kb
    for _ in range(max_steps):
        if cur == ka and len(loop) > 3:
            return loop, True
        pa, pc = nodes[prev], nodes[cur]
        din = math.atan2(pc[1] - pa[1], pc[0] - pa[0])
        best, bestturn = None, None
        for nb in adj.get(cur, ()):
            if nb == prev:
                continue
            pn = nodes[nb]
            dout = math.atan2(pn[1] - pc[1], pn[0] - pc[0])
            turn = abs((dout - din + math.pi) % (2 * math.pi) - math.pi)
            if bestturn is None or turn < bestturn:
                bestturn, best = turn, nb
        if best is None:
            return loop, False
        loop.append(best)
        prev, cur = cur, best
    return loop, False


def all_faces(segs):
    lines = [LineString([a, b]) for a, b in segs]
    noded = unary_union(MultiLineString(lines))
    return [f for f in polygonize(noded) if f.area >= 1.0]


def main():
    print(f"{'Caso':<32} {'area Lantek':>11} {'area trace':>11} {'delta%':>7} {'bbox':>10}")
    print("-" * 80)
    n_hit = 0
    for name, exp_a, exp_p in CASES:
        path = str(_R / name / "pezzo.dxf")
        segs = load_segments(path)
        nodes, adj, key = build_graph(segs)
        faces = all_faces(segs)  # per trovare i fori interni

        # Prova a seguire da ogni segmento abbastanza lungo (simula ogni click)
        seen_loops = {}
        seg_by_len = sorted(segs, key=lambda s: -math.hypot(s[1][0]-s[0][0], s[1][1]-s[0][1]))
        best_match = None
        for a, b in seg_by_len[:400]:  # top 400 segmenti piu lunghi
            ka, kb = key(a), key(b)
            if ka == kb:
                continue
            loop, closed = follow(nodes, adj, ka, kb)
            if not closed or len(loop) < 4:
                continue
            pts = [nodes[k] for k in loop]
            try:
                poly = Polygon(pts)
                if not poly.is_valid or poly.area < 1.0:
                    continue
            except Exception:
                continue
            # sottrai fori: facce strettamente contenute
            holes = [f for f in faces if poly.contains(f.representative_point()) and f.area < poly.area * 0.9]
            area_net = (poly.area - sum(h.area for h in holes)) / 10000.0
            diff = abs(area_net - exp_a) / exp_a * 100 if exp_a else 999
            if best_match is None or diff < best_match[0]:
                mn = poly.bounds
                best_match = (diff, area_net, poly, f"{mn[2]-mn[0]:.0f}x{mn[3]-mn[1]:.0f}", len(holes))

        if best_match:
            diff, area_net, poly, bbox, nh = best_match
            hit = diff <= 0.5
            flag = "OK" if hit else "  "
            if hit:
                n_hit += 1
            print(f"{name:<32} {exp_a:>11.4f} {area_net:>11.4f} {diff:>6.2f}% {bbox:>10} {flag} ({nh} fori)")
        else:
            print(f"{name:<32} {exp_a:>11.4f} {'nessun loop':>11}")

    print("-" * 80)
    print(f"Casi con un click che riproduce l'area Lantek (entro 0.5%): {n_hit}/{len(CASES)}")
    print("Significa: ESISTE un click sul contorno che il follower segue esatto.")


if __name__ == "__main__":
    main()

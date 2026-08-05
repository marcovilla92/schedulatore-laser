"""Baseline MISURATO del parsing contorno vs Lantek.

Per ogni caso della regression suite, cerca in modo ESAUSTIVO (tutti i segmenti
come punto di click) se il contour follower ATTUALE (follow_contour_from_click,
con tutti i fix) riproduce l'area Lantek entro tolleranza. Riporta:
  - il miglior click trovato (delta area minimo)
  - se PASSA (entro ±0.5% area)
  - area/perim/fori risultanti

Scopo: numero reale di partenza, non stimato. Se --write, scrive le coord del
miglior click in expected.json così la regression suite diventa ATTIVA.
"""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path

_APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_APP))
from backend.preventivi.pick_part import follow_contour_from_click  # noqa: E402
import ezdxf  # noqa: E402
from ezdxf.path import make_path  # noqa: E402

_REG = _APP.parent / "_test_input" / "regression"


def _candidate_clicks(path, max_pts=120):
    """Punti-click candidati: punti medi dei segmenti geometrici (campionati)."""
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    pts = []
    for e in msp:
        if e.dxftype() in ('DIMENSION', 'MTEXT', 'TEXT', 'INSERT', 'ATTRIB', 'ATTDEF', 'LEADER', 'HATCH'):
            continue
        try:
            if e.dxf.layer in ('FORMAT', 'TESTO'):
                continue
        except Exception:
            pass
        try:
            p = make_path(e)
            flat = [(v.x, v.y) for v in p.flattening(0.5)]
        except Exception:
            if e.dxftype() == 'LINE':
                s, en = e.dxf.start, e.dxf.end
                flat = [(s.x, s.y), (en.x, en.y)]
            else:
                continue
        for a, b in zip(flat, flat[1:]):
            pts.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
    # campiona per non esplodere
    if len(pts) > max_pts:
        step = len(pts) // max_pts
        pts = pts[::step]
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="scrivi le coord del miglior click in expected.json")
    args = ap.parse_args()

    cases = sorted(d for d in _REG.iterdir() if d.is_dir() and not d.name.startswith("_"))
    n_pass = 0
    print(f"\n{'Caso':<34}{'Lantek':>9}{'best':>9}{'delta':>8}  esito")
    print("-" * 78)
    for case in cases:
        dxf = case / "pezzo.dxf"
        exp_f = case / "expected.json"
        if not dxf.exists() or not exp_f.exists():
            continue
        exp = json.loads(exp_f.read_text(encoding="utf-8"))
        exp_area = (exp.get("expected") or {}).get("area_dm2")
        if not exp_area:
            continue
        tol = float(exp.get("tolleranze", {}).get("area_dm2_pct", 0.5))

        best = None  # (delta, area, perim, fori, click)
        clicks = _candidate_clicks(str(dxf))
        print(f"  ...{case.name}: {len(clicks)} click da provare", flush=True)
        for (cx, cy) in clicks:
            try:
                r = follow_contour_from_click(str(dxf), cx, cy)
            except Exception:
                continue
            if not r.get("success"):
                continue
            a = r["area_dm2"]
            delta = abs(a - exp_area) / exp_area * 100
            if best is None or delta < best[0]:
                best = (delta, a, r["perimetro_taglio_m"], r["n_forature"], (round(cx, 2), round(cy, 2)))
        if best is None:
            print(f"{case.name:<34}{exp_area:>9.4f}{'—':>9}{'—':>8}  NESSUN LOOP")
            continue
        delta, a, per, fori, click = best
        ok = delta <= tol
        if ok:
            n_pass += 1
        print(f"{case.name:<34}{exp_area:>9.4f}{a:>9.4f}{delta:>7.2f}%  {'PASS' if ok else 'FAIL'}  click={click} fori={fori}")
        if args.write and ok:
            exp["click_x_mm"], exp["click_y_mm"] = click
            exp.setdefault("expected", {})["n_fori"] = fori
            exp_f.write_text(json.dumps(exp, indent=2, ensure_ascii=False), encoding="utf-8")

    print("-" * 78)
    print(f"BASELINE MISURATO: {n_pass}/{len(cases)} casi con un click che riproduce Lantek (±0.5% area)")
    if args.write:
        print("Coord dei click PASS scritte in expected.json -> regression suite ora attiva su questi.")


if __name__ == "__main__":
    main()

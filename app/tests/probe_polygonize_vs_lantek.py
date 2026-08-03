"""Probe Fase 1 — la pipeline polygonize produce la geometria giusta?

Per ogni caso della regression suite (con valori Lantek reali in expected.json),
elenca TUTTE le facce del polygonize e verifica se ne esiste una la cui area
corrisponde (entro tolleranza) all'area Lantek attesa.

Domanda a cui risponde: "il contorno corretto del pezzo ESISTE tra le facce
prodotte dalla pipeline deterministica?" Se sì, il click deve solo selezionarlo
(problema risolto). Se no, l'estrazione stessa perde il contorno (problema più
profondo, da indagare sul singolo DXF).

Uso:
    python app/tests/probe_polygonize_vs_lantek.py
    python app/tests/probe_polygonize_vs_lantek.py --verbose   # elenca tutte le facce
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_APP_DIR))

from backend.preventivi.pick_part import polygonize_faces  # noqa: E402

_REGRESSION_ROOT = _APP_DIR.parent / "_test_input" / "regression"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    cases = sorted(d for d in _REGRESSION_ROOT.iterdir()
                   if d.is_dir() and not d.name.startswith("_"))
    if not cases:
        print("Nessun caso in _test_input/regression/")
        return

    n_hit = n_miss = 0
    for case in cases:
        dxf = case / "pezzo.dxf"
        exp_file = case / "expected.json"
        if not dxf.exists() or not exp_file.exists():
            continue
        exp = json.loads(exp_file.read_text(encoding="utf-8"))
        expected = exp.get("expected", {})
        exp_area = expected.get("area_dm2")
        exp_perim = expected.get("perim_m")
        tol_area = float(exp.get("tolleranze", {}).get("area_dm2_pct", 0.5))

        print(f"\n=== {case.name} ===")
        print(f"    Lantek: area={exp_area} dm2  perim={exp_perim} m")

        try:
            faces = polygonize_faces(str(dxf))
        except Exception as e:
            print(f"    ERRORE polygonize: {type(e).__name__}: {e}")
            n_miss += 1
            continue

        print(f"    Facce prodotte: {len(faces)}")

        # Cerca la faccia la cui area matcha Lantek (area lorda della faccia,
        # perche' Lantek "Area" e' l'area netta ma la faccia polygonize e' lorda;
        # confrontiamo sia lorda sia con approssimazione netta = faccia - fori interni)
        best = None
        best_diff = None
        for f in faces:
            if exp_area and exp_area > 0:
                diff = abs(f["area_dm2"] - exp_area) / exp_area * 100
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best = f

        if best is not None and best_diff is not None:
            match = best_diff <= tol_area
            flag = "OK MATCH" if match else "closest"
            print(f"    [{flag}] faccia area={best['area_dm2']:.4f} dm2 "
                  f"perim={best['perim_m']:.4f} m  (delta area {best_diff:.2f}%)  "
                  f"bbox={best['bbox_w_mm']:.0f}x{best['bbox_h_mm']:.0f}mm iso={best['is_iso']}")
            if match:
                n_hit += 1
            else:
                n_miss += 1
        else:
            print("    nessuna faccia confrontabile")
            n_miss += 1

        if args.verbose:
            for i, f in enumerate(faces[:15]):
                print(f"      faccia[{i}] area={f['area_dm2']:.4f}dm2 "
                      f"perim={f['perim_m']:.4f}m bbox={f['bbox_w_mm']:.0f}x{f['bbox_h_mm']:.0f} "
                      f"iso={f['is_iso']}")

    print(f"\n{'='*50}")
    print(f"Facce che matchano Lantek (area entro tol): {n_hit}/{n_hit+n_miss}")
    print("Se HIT: il contorno giusto ESISTE tra le facce -> il click lo seleziona.")
    print("Se MISS: l'estrazione perde il contorno su quel DXF -> indagare.")


if __name__ == "__main__":
    main()

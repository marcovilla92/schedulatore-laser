"""Regression suite DXF — fondamenta preventivatore.

Uso:
    python app/tests/test_regression_dxf.py                    tutti i casi
    python app/tests/test_regression_dxf.py --only <caso>      un solo caso
    python app/tests/test_regression_dxf.py --verbose          dettagli su ogni output

Struttura attesa: _test_input/regression/<caso>/pezzo.dxf + expected.json

Il test chiama compute_geometry_from_point(dxf_path, click_x, click_y) — la stessa
funzione che il futuro endpoint /dxf/<file>/pick-part usera'. Confronta area_dm2,
perim_m, n_fori con i valori attesi, applicando tolleranze da expected.json.

Exit code:
    0 = tutti i casi PASS
    1 = almeno un caso FAIL
    2 = errore setup (import fallito, cartella mancante, JSON invalido)
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

# Aggiungi app/ al path per importare backend.preventivi.dxf_polygon_detector_v3
_APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_APP_DIR))

try:
    # Funzione REALE del prodotto (contour follower), non il vecchio detector v3.
    from backend.preventivi.pick_part import follow_contour_from_click as compute_geometry_from_point
except ImportError as e:
    print(f"ERRORE setup: import fallito: {e}", file=sys.stderr)
    print("Esegui dalla root del progetto: python app/tests/test_regression_dxf.py", file=sys.stderr)
    sys.exit(2)

_REGRESSION_ROOT = _APP_DIR.parent / "_test_input" / "regression"


@dataclass
class CaseResult:
    name: str
    status: str  # 'PASS' | 'FAIL' | 'SKIP' | 'ERROR'
    details: list[str]
    actual_area: float | None = None
    actual_perim: float | None = None
    actual_n_fori: int | None = None


def _load_case(case_dir: Path) -> tuple[Path, dict] | None:
    """Ritorna (dxf_path, expected_dict) o None se il caso e' invalido."""
    dxf = case_dir / "pezzo.dxf"
    exp_file = case_dir / "expected.json"
    if not dxf.exists() or not exp_file.exists():
        return None
    try:
        exp = json.loads(exp_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"expected.json non valido: {e}")
    return dxf, exp


def _run_case(case_dir: Path, verbose: bool) -> CaseResult:
    name = case_dir.name
    loaded = _load_case(case_dir)
    if loaded is None:
        return CaseResult(name, "SKIP", ["manca pezzo.dxf o expected.json"])
    dxf, exp = loaded

    # Skip il template se qualcuno lo esegue per errore
    if exp.get("click_x_mm", 0.0) == 0.0 and exp.get("click_y_mm", 0.0) == 0.0 \
            and exp.get("expected", {}).get("area_dm2", 0.0) == 0.0:
        return CaseResult(name, "SKIP", ["template non compilato (tutti 0)"])

    # Skip se click coords non compilate — accade quando il caso e' stato
    # generato dall'XLSX Lantek (che ha area/perim/mat/sp ma non click x/y).
    # Marco deve aprire il DXF in CAD, leggere un punto sul contorno e mettere
    # le coordinate qui prima che il test possa girare.
    if exp.get("click_x_mm") is None or exp.get("click_y_mm") is None:
        return CaseResult(name, "SKIP", [
            "click_x_mm/click_y_mm mancanti — apri il DXF, leggi un punto sul contorno esterno, compila expected.json"
        ])

    click_x = float(exp["click_x_mm"])
    click_y = float(exp["click_y_mm"])
    expected = exp["expected"]
    tolleranze = exp.get("tolleranze", {})
    tol_area_pct = float(tolleranze.get("area_dm2_pct", 0.5))
    tol_perim_pct = float(tolleranze.get("perim_m_pct", 0.5))
    tol_n_fori_abs = int(tolleranze.get("n_fori_abs", 0))

    try:
        result = compute_geometry_from_point(str(dxf), click_x, click_y)
    except Exception as e:
        return CaseResult(name, "ERROR", [f"compute_geometry_from_point ha sollevato: {type(e).__name__}: {e}"])

    if not result or result.get("area_dm2", 0) == 0:
        warns = result.get("warnings", []) if result else []
        return CaseResult(name, "FAIL", [
            f"nessun poligono selezionato dal click ({click_x}, {click_y})",
            *[f"warn: {w}" for w in warns[:3]],
        ])

    actual_area = float(result.get("area_dm2", 0))
    actual_perim = float(result.get("perimetro_taglio_m", 0))
    # n_forature = n_inner nel dict di detect_pezzo_geometry_v3
    actual_n_fori = int(result.get("n_forature", result.get("n_pierce", 1)) - (1 if "n_pierce" in result else 0))
    # n_pierce = 1 + n_inner. Se abbiamo n_pierce, sottraiamo l'outer.
    if "n_pierce" in result:
        actual_n_fori = max(0, int(result["n_pierce"]) - 1)

    exp_area = expected.get("area_dm2")
    exp_perim = expected.get("perim_m")
    exp_n_fori = expected.get("n_fori")

    fails = []

    # Area check (solo se presente in expected)
    if exp_area is not None and float(exp_area) > 0:
        exp_area = float(exp_area)
        diff_area_pct = abs(actual_area - exp_area) / exp_area * 100
        if diff_area_pct > tol_area_pct:
            fails.append(
                f"area_dm2: atteso {exp_area:.3f} +/- {tol_area_pct}%, "
                f"ottenuto {actual_area:.3f} (delta {diff_area_pct:.2f}%)"
            )

    # Perim check (solo se presente)
    if exp_perim is not None and float(exp_perim) > 0:
        exp_perim = float(exp_perim)
        diff_perim_pct = abs(actual_perim - exp_perim) / exp_perim * 100
        if diff_perim_pct > tol_perim_pct:
            fails.append(
                f"perim_m: atteso {exp_perim:.3f} +/- {tol_perim_pct}%, "
                f"ottenuto {actual_perim:.3f} (delta {diff_perim_pct:.2f}%)"
            )

    # N fori check (solo se presente — Lantek XLSX non lo esporta, va contato a mano)
    if exp_n_fori is not None:
        exp_n_fori = int(exp_n_fori)
        diff_n_fori = abs(actual_n_fori - exp_n_fori)
        if diff_n_fori > tol_n_fori_abs:
            fails.append(
                f"n_fori: atteso {exp_n_fori} +/- {tol_n_fori_abs}, "
                f"ottenuto {actual_n_fori} (delta {diff_n_fori})"
            )

    details = fails if fails else []
    if verbose:
        details.append(
            f"area={actual_area:.3f}dm2 perim={actual_perim:.3f}m n_fori={actual_n_fori}"
        )

    return CaseResult(
        name,
        "FAIL" if fails else "PASS",
        details,
        actual_area=actual_area,
        actual_perim=actual_perim,
        actual_n_fori=actual_n_fori,
    )


def main():
    parser = argparse.ArgumentParser(description="Regression suite DXF")
    parser.add_argument("--only", help="Esegui solo il caso con questo nome")
    parser.add_argument("--verbose", "-v", action="store_true", help="Dettagli su ogni output")
    args = parser.parse_args()

    if not _REGRESSION_ROOT.is_dir():
        print(f"ERRORE: cartella {_REGRESSION_ROOT} non esiste", file=sys.stderr)
        sys.exit(2)

    # Trova tutti i casi (sottocartelle, esclusa _TEMPLATE)
    cases = sorted(
        d for d in _REGRESSION_ROOT.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    )

    if args.only:
        cases = [c for c in cases if c.name == args.only]
        if not cases:
            print(f"ERRORE: nessun caso trovato con nome '{args.only}'", file=sys.stderr)
            sys.exit(2)

    if not cases:
        print("ATTENZIONE: nessun caso di test presente in _test_input/regression/")
        print("Aggiungine almeno uno copiando _TEMPLATE/ e compilando expected.json")
        print("Vedi _test_input/regression/README.md per istruzioni.")
        sys.exit(0)

    results: list[CaseResult] = []
    for case_dir in cases:
        r = _run_case(case_dir, args.verbose)
        results.append(r)

    # Report tabellare
    n_max = max(len(r.name) for r in results)
    print()
    print(f"{'Caso':<{n_max}}  {'Esito':<6}  Dettagli")
    print("-" * (n_max + 8 + 40))
    n_pass = n_fail = n_skip = n_err = 0
    for r in results:
        icon = {"PASS": "OK", "FAIL": "KO", "SKIP": "--", "ERROR": "!!"}[r.status]
        print(f"{r.name:<{n_max}}  {icon} {r.status:<4}")
        for d in r.details:
            print(f"{'':<{n_max}}  {'':<6}  {d}")
        {"PASS": lambda: None, "FAIL": lambda: None, "SKIP": lambda: None, "ERROR": lambda: None}[r.status]
        if r.status == "PASS":
            n_pass += 1
        elif r.status == "FAIL":
            n_fail += 1
        elif r.status == "SKIP":
            n_skip += 1
        elif r.status == "ERROR":
            n_err += 1

    total = len(results)
    print()
    print(f"Totale: {total}  PASS: {n_pass}  FAIL: {n_fail}  SKIP: {n_skip}  ERROR: {n_err}")

    # Exit code: fail se anche un FAIL o ERROR
    if n_fail > 0 or n_err > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

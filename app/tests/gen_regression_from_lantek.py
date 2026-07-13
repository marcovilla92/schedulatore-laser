"""Genera casi di regression suite DXF dall'export Lantek ORD.204.xlsx.

Per ogni articolo nell'XLSX con un DXF corrispondente in _test_input/204-26/,
crea una sottocartella in _test_input/regression/ con:
  - pezzo.dxf (copiato dall'originale)
  - expected.json (compilato con valori Lantek: area, perim, materiale, spessore, bbox)
  - NOTES.md (provenienza dati)

I campi `click_x_mm/click_y_mm` e `expected.n_fori` restano null perche':
- click coords: vanno lette aprendo il DXF in CAD (un punto sul contorno esterno)
- n_fori: Lantek XLSX non lo esporta, va contato a mano nel CAD

Il test skippa i casi con click coords null. Marco li compila uno alla volta
mano a mano che vuole abilitare il caso.

Uso:
    python app/tests/gen_regression_from_lantek.py
    python app/tests/gen_regression_from_lantek.py --force   sovrascrive esistenti
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("ERRORE: openpyxl non installato. Esegui: pip install openpyxl", file=sys.stderr)
    sys.exit(2)

_APP_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _APP_DIR.parent
_XLSX_PATH = _REPO_ROOT / "_test_input" / "ORD.204.xlsx"
_DXF_SOURCE = _REPO_ROOT / "_test_input" / "204-26" / "204-26"
_REGRESSION_ROOT = _REPO_ROOT / "_test_input" / "regression"


def _norm_materiale(raw: str) -> str:
    """Normalizza il materiale Lantek al set enum del sistema."""
    if not raw:
        return "S235"
    r = raw.upper().strip()
    if "INOX 316" in r or "AISI 316" in r or "1.4404" in r:
        return "INOX_316"
    if "INOX" in r or "AISI 304" in r or "1.4301" in r:
        return "INOX_304"
    if "ALU" in r or "5754" in r:
        return "ALU_5754"
    if "5083" in r:
        return "ALU_5083"
    if "ZINC" in r or "DX51" in r:
        return "ZINCATO"
    if "OTTON" in r or "CUZN" in r:
        return "OTTONE"
    if "S235" in r or "1.0037" in r or "FE" in r:
        return "S235"
    return "S235"  # default conservativo


def _sanitize(name: str) -> str:
    """Nome cartella filesystem-safe."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def _find_dxf(codice: str) -> Path | None:
    """Cerca il DXF corrispondente al codice, case-insensitive."""
    for p in _DXF_SOURCE.glob("*"):
        if p.suffix.lower() == ".dxf" and p.stem == codice:
            return p
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Sovrascrive casi esistenti")
    args = parser.parse_args()

    if not _XLSX_PATH.exists():
        print(f"ERRORE: XLSX non trovato: {_XLSX_PATH}", file=sys.stderr)
        sys.exit(2)
    if not _DXF_SOURCE.exists():
        print(f"ERRORE: cartella DXF non trovata: {_DXF_SOURCE}", file=sys.stderr)
        sys.exit(2)

    wb = openpyxl.load_workbook(_XLSX_PATH, data_only=True)
    ws = wb["Struttura"]
    headers = [c.value for c in ws[1]]

    def col(name: str) -> int:
        try:
            return headers.index(name)
        except ValueError:
            print(f"ERRORE: colonna '{name}' non trovata in Struttura", file=sys.stderr)
            sys.exit(2)

    col_codice = col("Codice")
    col_area = col("Area")               # m^2
    col_perim = col("Perimetro di taglio")  # m
    col_peso = col("Peso")               # kg
    col_mat = col("Materiale")
    col_sp = col("Spessore")             # mm
    col_len = col("Lunghezza")           # mm
    col_wid = col("Larghezza")           # mm

    n_created = n_skipped = n_no_dxf = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        codice = row[col_codice]
        if not codice:
            continue

        dxf_path = _find_dxf(str(codice))
        if not dxf_path:
            print(f"[NO-DXF] {codice} — nessun DXF corrispondente in {_DXF_SOURCE}")
            n_no_dxf += 1
            continue

        area_m2 = row[col_area]
        perim_m = row[col_perim]
        peso_kg = row[col_peso]
        materiale_raw = row[col_mat]
        spessore_mm = row[col_sp]
        len_mm = row[col_len]
        wid_mm = row[col_wid]

        materiale = _norm_materiale(str(materiale_raw or ""))
        # Area Lantek e' in m^2, il nostro standard e' dm^2 (1 m^2 = 100 dm^2)
        area_dm2 = float(area_m2) * 100 if area_m2 is not None else None

        case_name = f"{_sanitize(str(codice))}_{materiale}_sp{spessore_mm}mm"
        case_dir = _REGRESSION_ROOT / case_name

        if case_dir.exists() and not args.force:
            print(f"[SKIP-EXIST] {case_name} — gia' presente (usa --force per sovrascrivere)")
            n_skipped += 1
            continue

        case_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dxf_path, case_dir / "pezzo.dxf")

        expected_json = {
            "click_x_mm": None,
            "click_y_mm": None,
            "expected": {
                "area_dm2": round(area_dm2, 4) if area_dm2 is not None else None,
                "perim_m": round(float(perim_m), 4) if perim_m is not None else None,
                "n_fori": None,
                "materiale": materiale,
                "spessore_mm": float(spessore_mm) if spessore_mm is not None else None,
                "peso_kg": round(float(peso_kg), 4) if peso_kg is not None else None,
                "bbox_lunghezza_mm": float(len_mm) if len_mm is not None else None,
                "bbox_larghezza_mm": float(wid_mm) if wid_mm is not None else None,
            },
            "tolleranze": {
                "area_dm2_pct": 0.5,
                "perim_m_pct": 0.5,
                "n_fori_abs": 0
            },
            "misurato_con": f"Lantek — ORD.204.xlsx (sheet 'Struttura', pezzo {codice})",
            "descrizione": f"Articolo ordine 204-26 fornitore reale. Materiale Lantek raw: '{materiale_raw}' -> normalizzato '{materiale}'.",
            "TODO": "Aprire pezzo.dxf in Lantek/CAD, leggere le coord (x,y) di un punto sul contorno esterno, mettere in click_x_mm/click_y_mm. Contare i fori (esclusi svasature/filettature) e mettere in expected.n_fori. Poi il caso e' attivo per la suite."
        }

        (case_dir / "expected.json").write_text(
            json.dumps(expected_json, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        (case_dir / "NOTES.md").write_text(
            f"# {codice}\n\n"
            f"- **Fornitore/OEM**: articolo ordine 204-26 (dati Lantek reali)\n"
            f"- **Materiale**: {materiale_raw} (normalizzato: {materiale})\n"
            f"- **Spessore**: {spessore_mm} mm\n"
            f"- **Bbox**: {len_mm} × {wid_mm} mm\n"
            f"- **Peso Lantek**: {peso_kg} kg\n"
            f"- **Area Lantek**: {area_m2} m² ({area_dm2:.3f} dm²)\n"
            f"- **Perimetro Lantek**: {perim_m} m\n\n"
            f"## Come sono stati misurati i valori attesi\n\n"
            f"Estratti dall'export Lantek ORD.204.xlsx generato dal cliente. Sono i valori\n"
            f"che Lantek ha calcolato quando questo pezzo e' stato lavorato in produzione.\n\n"
            f"## TODO per attivare il caso\n\n"
            f"1. Aprire `pezzo.dxf` in Lantek (o vero CAD)\n"
            f"2. Leggere le coord (x,y) di un punto sul contorno esterno del pezzo\n"
            f"3. Compilare `click_x_mm` e `click_y_mm` in expected.json\n"
            f"4. Contare i fori di taglio (escludere svasature/filettature)\n"
            f"5. Compilare `expected.n_fori`\n"
            f"6. Rimuovere il campo TODO da expected.json\n\n"
            f"Finche' click_x/y sono null, il test skippa questo caso.\n",
            encoding="utf-8"
        )

        print(f"[OK] {case_name}  area={area_dm2:.3f}dm2 perim={perim_m:.3f}m {materiale} sp{spessore_mm}mm")
        n_created += 1

    print()
    print(f"Creati: {n_created}  Saltati (esistenti): {n_skipped}  Senza DXF: {n_no_dxf}")
    print()
    print("Ora apri ogni pezzo.dxf in Lantek per leggere le coord del click sul contorno")
    print("e compilare click_x_mm/click_y_mm + n_fori in ogni expected.json.")
    print("Poi esegui: python app/tests/test_regression_dxf.py")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
test_universal_extractor.py — Validazione universal_extractor vs baseline Phase 4

Esegue extract_universal() su tutti i PDF della cartella ORDINI e confronta
i risultati con la baseline Phase 4 (audit_parsers.py).

Uso:
    cd app
    python test_universal_extractor.py [--dir <percorso_directory>] [--debug]

Argomenti:
    --dir <path>   Directory contenente i PDF (default: C:\\Users\\39334\\Documents\\ORDINI)
    --debug        Stampa il testo Docling intermedio su stderr per ogni PDF

Output:
    Report testuale con:
    - RISULTATI PER CAMPO: tabella comparativa con baseline Phase 4
    - RISULTATI PER FILE: stato per ogni PDF con confidence
    - ANALISI CONFIDENCE: campi con confidence bassa
    - CONFRONTO BASELINE: verdetto esplicito su ORDINE_LS e overall

Requisiti:
    - GEMINI_API_KEY configurata in app/.env
    - Docling installato (pip install docling==2.2.0)
    - google-genai installato (pip install google-genai)
"""

import sys
import os
import argparse
import json
from pathlib import Path
from datetime import datetime

# Fix encoding Windows: evita UnicodeEncodeError su stdout in console italiana
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Rende importabili i moduli backend da app/
sys.path.insert(0, str(Path(__file__).parent))

# Carica GEMINI_API_KEY da app/.env prima di importare universal_extractor
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Import del modulo da validare
from backend.universal_extractor import extract_universal, ExtractionError


# ---------------------------------------------------------------------------
# Baseline Phase 4 — da audit_parsers.py eseguito il 2026-02-19
# Fonte: app/audit_reports/audit_20260219_104135.txt
# ---------------------------------------------------------------------------

BASELINE_PHASE4 = {
    "cliente": 0.87,        # 28/32 PASS (87%)
    "numero_ordine": 1.00,  # 32/32 PASS (100%)
    "data_consegna": 0.81,  # 26/32 PASS (81%) — 6 FALLBACK
    "articoli": 1.00,       # 32/32 PASS (100%)
}

# Per formato ORDINE_LS la baseline era:
# cliente=50%, numero_ordine=100%, articoli=100%, data_consegna=50%
BASELINE_ORDINE_LS = {
    "cliente": 0.50,
    "data_consegna": 0.50,
}

# Data di oggi — usata per rilevare il fallback di data_consegna
_TODAY_PREFIX = datetime.now().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Funzioni di supporto
# ---------------------------------------------------------------------------

def _is_fallback_date(value: str) -> bool:
    """
    Ritorna True se data_consegna e il valore di fallback datetime.now().

    La logica in _to_parser_compatible_dict() usa `datetime.now().isoformat()`
    quando data_consegna e stringa vuota. Questa funzione rileva tale caso.
    """
    if not value:
        return True
    # Controlla se la data inizia con la data di oggi (YYYY-MM-DD)
    # Questo copre entrambi i casi: stringa vuota restituita da Gemini
    # oppure data che inizia con oggi (coincidenza rara ma possibile)
    return value.startswith(_TODAY_PREFIX)


def _detect_format(filename: str) -> str:
    """
    Inferisce il formato del PDF dal nome file (euristica semplice).
    Utile per la sezione CONFRONTO BASELINE ORDINE_LS.
    """
    name_upper = filename.upper()
    if "300000946" in name_upper:
        return "DIVISIONE"
    elif "FOR-ORDINE" in name_upper and "AZA" not in name_upper and "L S S R L" not in filename:
        return "FOR_ORDINE"
    elif "ORDINE FORNITORE" in filename and "L S S R L" in filename:
        return "FOR_ORDINE_AZA"
    elif "OAFA" in name_upper:
        return "OAFA"
    elif "ORDINE" in name_upper and ("LS" in name_upper or "N" in name_upper):
        return "ORDINE_LS"
    elif "PO_" in name_upper or "BEBITALIA" in name_upper:
        return "PO_BEBITALIA"
    elif "OF_" in name_upper:
        return "FOR_ORDINE"
    else:
        return "SCONOSCIUTO"


def _parse_args():
    """Analizza gli argomenti da riga di comando."""
    parser = argparse.ArgumentParser(
        description="Valida universal_extractor vs baseline Phase 4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dir",
        default=r"C:\Users\39334\Documents\ORDINI",
        help="Directory contenente i PDF da analizzare",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Stampa testo Docling intermedio su stderr",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Raccolta risultati
# ---------------------------------------------------------------------------

def _collect_results(pdf_dir: Path, debug: bool) -> list:
    """
    Esegue extract_universal() su tutti i PDF nella directory.

    Gestisce ExtractionError per singolo file senza interrompere il batch.
    Deduplicazione: ignora file con lo stesso nome (la cartella ha 32 file = 16 x 2).

    Returns:
        Lista di dict con risultati per file, ciascuno con:
            filename, format, status (ok/partial/error), error_msg,
            cliente, numero_ordine, data_consegna, articoli_count,
            cliente_confidence, numero_ordine_confidence,
            data_consegna_confidence, articoli_confidence,
            cliente_pass, data_pass, ordine_pass, articoli_pass
    """
    # Deduplicazione: usa set dei nomi file senza directory
    seen_names = set()
    unique_pdfs = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf")) + sorted(pdf_dir.glob("*.PDF")):
        name = pdf_path.name
        if name not in seen_names:
            seen_names.add(name)
            unique_pdfs.append(pdf_path)

    print(f"\nDirectory: {pdf_dir}", flush=True)
    print(f"PDF trovati (deduplicati): {len(unique_pdfs)}", flush=True)
    print(f"Inizio elaborazione... (1-3 minuti per {len(unique_pdfs)} PDF)\n", flush=True)

    results = []

    for i, pdf_path in enumerate(unique_pdfs, 1):
        filename = pdf_path.name
        formato = _detect_format(filename)
        print(f"[{i:2d}/{len(unique_pdfs)}] {filename[:60]:<60} ", end="", flush=True)

        try:
            result = extract_universal(str(pdf_path), debug=debug)

            # Valutazione campi
            cliente_val = result.get("cliente", "")
            ordine_val = result.get("numero_ordine", "")
            data_val = result.get("data_consegna", "")
            articoli_val = result.get("articoli", [])

            cliente_pass = bool(cliente_val and cliente_val.strip())
            ordine_pass = bool(ordine_val and ordine_val.strip())
            data_pass = bool(data_val) and not _is_fallback_date(data_val)
            articoli_pass = bool(articoli_val)

            all_pass = cliente_pass and ordine_pass and data_pass and articoli_pass
            status = "ok" if all_pass else "partial"

            print(
                f"{'OK' if status == 'ok' else 'PARTIAL'} | "
                f"cli:{'+' if cliente_pass else '-'} "
                f"ord:{'+' if ordine_pass else '-'} "
                f"dat:{'+' if data_pass else '-'} "
                f"art:{'+' if articoli_pass else '-'} | "
                f"conf:{result.get('cliente_confidence','?')[0].upper()}"
                f"{result.get('data_consegna_confidence','?')[0].upper()}",
                flush=True,
            )

            results.append({
                "filename": filename,
                "format": formato,
                "status": status,
                "error_msg": None,
                "cliente": cliente_val,
                "numero_ordine": ordine_val,
                "data_consegna": data_val,
                "articoli_count": len(articoli_val),
                "cliente_confidence": result.get("cliente_confidence", "bassa"),
                "numero_ordine_confidence": result.get("numero_ordine_confidence", "bassa"),
                "data_consegna_confidence": result.get("data_consegna_confidence", "bassa"),
                "articoli_confidence": result.get("articoli_confidence", "bassa"),
                "cliente_pass": cliente_pass,
                "ordine_pass": ordine_pass,
                "data_pass": data_pass,
                "articoli_pass": articoli_pass,
            })

        except ExtractionError as exc:
            print(f"ERRORE: {str(exc)[:80]}", flush=True)
            results.append({
                "filename": filename,
                "format": formato,
                "status": "error",
                "error_msg": str(exc),
                "cliente": "",
                "numero_ordine": "",
                "data_consegna": "",
                "articoli_count": 0,
                "cliente_confidence": "bassa",
                "numero_ordine_confidence": "bassa",
                "data_consegna_confidence": "bassa",
                "articoli_confidence": "bassa",
                "cliente_pass": False,
                "ordine_pass": False,
                "data_pass": False,
                "articoli_pass": False,
            })

    return results


# ---------------------------------------------------------------------------
# Calcolo metriche aggregate
# ---------------------------------------------------------------------------

def _compute_metrics(results: list) -> dict:
    """Calcola success rate per campo su tutti i PDF processati."""
    total = len(results)
    if total == 0:
        return {}

    cliente_pass = sum(1 for r in results if r["cliente_pass"])
    ordine_pass = sum(1 for r in results if r["ordine_pass"])
    data_pass = sum(1 for r in results if r["data_pass"])
    articoli_pass = sum(1 for r in results if r["articoli_pass"])
    errors = sum(1 for r in results if r["status"] == "error")
    ok_count = sum(1 for r in results if r["status"] == "ok")
    partial_count = sum(1 for r in results if r["status"] == "partial")

    return {
        "total": total,
        "errors": errors,
        "ok": ok_count,
        "partial": partial_count,
        "cliente_rate": cliente_pass / total,
        "ordine_rate": ordine_pass / total,
        "data_rate": data_pass / total,
        "articoli_rate": articoli_pass / total,
        "cliente_pass": cliente_pass,
        "ordine_pass": ordine_pass,
        "data_pass": data_pass,
        "articoli_pass": articoli_pass,
    }


def _compute_ordine_ls_metrics(results: list) -> dict:
    """Calcola success rate solo per i file ORDINE_LS."""
    ls_results = [r for r in results if r["format"] == "ORDINE_LS"]
    if not ls_results:
        return {"total": 0}
    return {
        "total": len(ls_results),
        "cliente_rate": sum(1 for r in ls_results if r["cliente_pass"]) / len(ls_results),
        "data_rate": sum(1 for r in ls_results if r["data_pass"]) / len(ls_results),
    }


# ---------------------------------------------------------------------------
# Stampa report
# ---------------------------------------------------------------------------

def _print_report(results: list, metrics: dict, ls_metrics: dict) -> bool:
    """
    Stampa il report completo e restituisce True se SUCCESS.

    Sections:
    1. RISULTATI PER CAMPO
    2. RISULTATI PER FILE
    3. ANALISI CONFIDENCE
    4. CONFRONTO BASELINE
    5. VERDETTO FINALE
    """
    SEP = "=" * 72
    sep = "-" * 72

    print(f"\n{SEP}")
    print("REPORT VALIDAZIONE — universal_extractor vs baseline Phase 4")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP)

    # -----------------------------------------------------------------------
    # Sezione 1: RISULTATI PER CAMPO
    # -----------------------------------------------------------------------
    print("\n" + sep)
    print("SEZIONE 1 — RISULTATI PER CAMPO")
    print(sep)
    print(f"{'Campo':<20} {'Phase 4 Baseline':>18} {'Universal Extractor':>20} {'Delta':>8}")
    print(sep)

    fields = [
        ("cliente", "cliente_rate"),
        ("numero_ordine", "ordine_rate"),
        ("data_consegna", "data_rate"),
        ("articoli", "articoli_rate"),
    ]

    all_fields_pass = True
    for field_name, metric_key in fields:
        baseline = BASELINE_PHASE4[field_name]
        universal = metrics.get(metric_key, 0.0)
        delta = universal - baseline
        delta_str = f"+{delta:.0%}" if delta >= 0 else f"{delta:.0%}"
        status_icon = "OK" if universal >= baseline else "!!"

        print(
            f"  {field_name:<18} {baseline:>16.0%}   {universal:>18.0%}   {delta_str:>6}  [{status_icon}]"
        )
        if universal < baseline:
            all_fields_pass = False

    print(sep)
    print(f"  PDF analizzati : {metrics.get('total', 0)}")
    print(f"  OK completi    : {metrics.get('ok', 0)}")
    print(f"  PARTIAL        : {metrics.get('partial', 0)}")
    print(f"  ERRORI         : {metrics.get('errors', 0)}")

    # -----------------------------------------------------------------------
    # Sezione 2: RISULTATI PER FILE
    # -----------------------------------------------------------------------
    print("\n" + sep)
    print("SEZIONE 2 — RISULTATI PER FILE")
    print(sep)
    print(
        f"{'#':>3}  {'File':<45} {'Formato':<16} {'cli':>3} {'ord':>3} {'dat':>3} {'art':>3} | {'conf_cli':>8} {'conf_dat':>8}"
    )
    print(sep)

    for i, r in enumerate(results, 1):
        cli = "OK" if r["cliente_pass"] else "FAIL"
        ord_ = "OK" if r["ordine_pass"] else "FAIL"
        dat = "OK" if r["data_pass"] else "FAIL"
        art = "OK" if r["articoli_pass"] else "FAIL"

        if r["status"] == "error":
            print(
                f"  {i:>3}  {r['filename'][:45]:<45} {r['format']:<16} "
                f"{'ERRORE':>35} {r['error_msg'][:40]}"
            )
        else:
            print(
                f"  {i:>3}  {r['filename'][:45]:<45} {r['format']:<16} "
                f"{cli:>3} {ord_:>3} {dat:>3} {art:>3} | "
                f"{r['cliente_confidence']:>8} {r['data_consegna_confidence']:>8}"
            )

    # -----------------------------------------------------------------------
    # Sezione 3: ANALISI CONFIDENCE
    # -----------------------------------------------------------------------
    print("\n" + sep)
    print("SEZIONE 3 — ANALISI CONFIDENCE (campi con bassa certezza)")
    print(sep)

    low_confidence_items = []
    for r in results:
        if r["status"] == "error":
            continue
        for conf_field, label_field in [
            ("cliente_confidence", "cliente"),
            ("data_consegna_confidence", "data_consegna"),
            ("articoli_confidence", "articoli"),
        ]:
            if r[conf_field] == "bassa":
                low_confidence_items.append(
                    f"  {r['filename'][:45]:<45} campo={label_field:<15} valore={r.get(label_field, r.get('data_consegna', ''))[:30]}"
                )

    if low_confidence_items:
        for item in low_confidence_items:
            print(item)
    else:
        print("  Nessun campo con confidence 'bassa' rilevato.")

    # -----------------------------------------------------------------------
    # Sezione 4: CONFRONTO BASELINE ORDINE_LS
    # -----------------------------------------------------------------------
    print("\n" + sep)
    print("SEZIONE 4 — CONFRONTO BASELINE ORDINE_LS")
    print(sep)

    if ls_metrics.get("total", 0) == 0:
        print("  Nessun file ORDINE_LS trovato nella directory.")
        ls_improved = True  # Non applicabile
    else:
        ls_cliente_rate = ls_metrics["cliente_rate"]
        ls_data_rate = ls_metrics["data_rate"]
        ls_cliente_improved = ls_cliente_rate > BASELINE_ORDINE_LS["cliente"]
        ls_data_improved = ls_data_rate > BASELINE_ORDINE_LS["data_consegna"]

        print(f"  File ORDINE_LS analizzati : {ls_metrics['total']}")
        print(f"  {'Campo':<20} {'Baseline (Phase 4)':>20} {'Universal':>15} {'Migliorato':>12}")
        print(f"  {'-'*68}")
        print(
            f"  {'cliente':<20} {BASELINE_ORDINE_LS['cliente']:>20.0%} "
            f"{ls_cliente_rate:>15.0%} "
            f"{'SI' if ls_cliente_improved else 'NO':>12}"
        )
        print(
            f"  {'data_consegna':<20} {BASELINE_ORDINE_LS['data_consegna']:>20.0%} "
            f"{ls_data_rate:>15.0%} "
            f"{'SI' if ls_data_improved else 'NO':>12}"
        )

        ls_improved = ls_cliente_improved or ls_data_improved

    # -----------------------------------------------------------------------
    # Sezione 5: VERDETTO FINALE
    # -----------------------------------------------------------------------
    print("\n" + SEP)
    success = all_fields_pass and ls_improved

    if success:
        print("VERDETTO: SUCCESS")
        print()
        print("  universal_extractor supera o eguaglia la baseline Phase 4 su tutti i campi.")
        if ls_metrics.get("total", 0) > 0:
            print("  ORDINE_LS migliorato rispetto alla baseline (cliente 50%, data 50%).")
    else:
        print("VERDETTO: ATTENZIONE")
        print()
        print("  Campi che non raggiungono la baseline Phase 4:")
        for field_name, metric_key in fields:
            baseline = BASELINE_PHASE4[field_name]
            universal = metrics.get(metric_key, 0.0)
            if universal < baseline:
                print(
                    f"    - {field_name}: universal={universal:.0%} < baseline={baseline:.0%} "
                    f"(delta={universal - baseline:.0%})"
                )
        if not ls_improved and ls_metrics.get("total", 0) > 0:
            print("    - ORDINE_LS: nessun miglioramento rispetto alla baseline 50%")

    print(SEP)
    return success


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Punto di ingresso principale dello script."""
    args = _parse_args()
    pdf_dir = Path(args.dir)

    if not pdf_dir.exists():
        print(f"[ERRORE] Directory non trovata: {pdf_dir}", file=sys.stderr)
        sys.exit(1)

    # Raccolta risultati con gestione ExtractionError per singolo PDF
    results = _collect_results(pdf_dir, debug=args.debug)

    # Calcolo metriche
    metrics = _compute_metrics(results)
    ls_metrics = _compute_ordine_ls_metrics(results)

    # Stampa report e ottieni verdetto
    success = _print_report(results, metrics, ls_metrics)

    # Exit code: 0 se SUCCESS, 1 se ATTENZIONE
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

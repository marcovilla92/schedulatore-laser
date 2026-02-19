#!/usr/bin/env python3
"""
audit_parsers.py — Script di audit standalone per i parser PDF del Schedulatore Laser

Misura il success rate dei parser esistenti su tutti i PDF in una directory specificata,
producendo un report strutturato per campo (cliente, numero_ordine, articoli, quantita,
data_consegna) suddiviso per formato rilevato.

Utilizzo:
    cd app
    python audit_parsers.py --dir "C:/Users/39334/Documents/ORDINI"
"""
import sys
import io
import argparse
import time
from pathlib import Path
from datetime import datetime

# Fix Unicode su Windows PRIMA di qualsiasi print (encoding cp1252 non gestisce il simbolo gradi)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Import dal backend (stesso pattern di batch_test_ordini.py)
sys.path.insert(0, str(Path(__file__).parent))

from backend.pdf_parser import extract_pdf_content, detect_pdf_format
import PyPDF2


# ---------------------------------------------------------------------------
# Funzione 1: Rilevamento formato senza estrazione completa
# ---------------------------------------------------------------------------

def get_pdf_format(filepath):
    """
    Rileva il formato PDF senza passare attraverso l'estrazione completa.
    Apre il PDF con PyPDF2, estrae il testo, chiama detect_pdf_format().
    Gestisce eccezioni restituendo 'UNKNOWN'.
    Reindirizza stdout per sopprimere i print del dispatcher durante il rilevamento.
    """
    try:
        with open(str(filepath), 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ''.join(p.extract_text() or '' for p in reader.pages)

        # Sopprimi i print di FORMAT DETECTION del dispatcher
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            fmt = detect_pdf_format(text)
        finally:
            sys.stdout = old_stdout

        return fmt
    except Exception:
        return 'UNKNOWN'


# ---------------------------------------------------------------------------
# Funzione 2: Valutazione per campo
# ---------------------------------------------------------------------------

def evaluate_field(field_name, value, result):
    """
    Restituisce 'PASS', 'FAIL', 'EMPTY' o 'FALLBACK' per un singolo campo estratto.

    Criteri:
    - cliente: FAIL se il valore e' vuoto o un valore noto errato
    - numero_ordine: FAIL se la stringa e' vuota
    - articoli: PASS se len(articoli) > 0, altrimenti FAIL
    - quantita: PASS se quantita_totale > 0, altrimenti FAIL
    - data_consegna: FALLBACK se il valore inizia con la data odierna (datetime.now() come default)
    """
    if field_name == 'cliente':
        bad_values = {
            '',
            'spettabile',
            'l.s. srl',
            'l.s. s.r.l.',
            'ls srl',
            'cliente sconosciuto',
        }
        v = str(value).strip().lower()
        if not v:
            return 'EMPTY'
        return 'FAIL' if v in bad_values else 'PASS'

    elif field_name == 'numero_ordine':
        v = str(value).strip()
        if not v:
            return 'EMPTY'
        return 'PASS'

    elif field_name == 'articoli':
        count = len(result.get('articoli', []))
        return 'PASS' if count > 0 else 'FAIL'

    elif field_name == 'quantita':
        qty = result.get('quantita_totale', 0)
        return 'PASS' if qty and float(qty) > 0 else 'FAIL'

    elif field_name == 'data_consegna':
        # Se il parser non ha trovato una data reale, usa datetime.now() come default.
        # Rileviamo questo confrontando il prefisso del valore con la data odierna.
        today = datetime.now().strftime('%Y-%m-%d')
        v = str(value)
        return 'FALLBACK' if v.startswith(today) else 'PASS'

    return 'FAIL'


# ---------------------------------------------------------------------------
# Funzione 3: Audit di un singolo PDF
# ---------------------------------------------------------------------------

FIELDS = ['cliente', 'numero_ordine', 'articoli', 'quantita', 'data_consegna']


def audit_pdf(filepath):
    """
    Esegue l'estrazione di un PDF con stdout soppresso.
    Gestisce eccezioni per-PDF registrando CRASH con messaggio.

    Restituisce dict con chiavi:
        file    — nome file
        format  — formato rilevato
        result  — dict restituito da extract_pdf_content (o None su crash)
        fields  — dict {campo: stato} con PASS/FAIL/EMPTY/FALLBACK
        error   — messaggio di errore (None se tutto OK)
        article_count — numero di articoli estratti
    """
    filename = Path(filepath).name

    # Rileva formato separatamente (soppresso)
    pdf_format = get_pdf_format(filepath)

    # Esegui estrazione completa con stdout soppresso
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    result = None
    error = None
    try:
        result = extract_pdf_content(str(filepath))
        if result.get('error'):
            error = result['error']
    except Exception as e:
        error = str(e)
    finally:
        sys.stdout = old_stdout

    if error and result is None:
        # CRASH totale: nessun risultato
        return {
            'file': filename,
            'format': pdf_format,
            'result': None,
            'fields': {f: 'CRASH' for f in FIELDS},
            'error': error,
            'article_count': 0,
        }

    # Valuta ogni campo
    field_states = {}
    for field in FIELDS:
        if field == 'cliente':
            value = result.get('cliente', '')
        elif field == 'numero_ordine':
            value = result.get('numero_ordine', '')
        elif field == 'articoli':
            value = result.get('articoli', [])
        elif field == 'quantita':
            value = result.get('quantita_totale', 0)
        elif field == 'data_consegna':
            value = result.get('data_consegna', '')
        else:
            value = ''

        field_states[field] = evaluate_field(field, value, result)

    return {
        'file': filename,
        'format': pdf_format,
        'result': result,
        'fields': field_states,
        'error': error,
        'article_count': len(result.get('articoli', [])),
    }


# ---------------------------------------------------------------------------
# Funzione 4: Ricerca PDF nella directory
# ---------------------------------------------------------------------------

def find_pdfs(directory):
    """
    Trova tutti i file *.pdf e *.PDF nella directory specificata.
    Restituisce lista ordinata di Path.
    """
    d = Path(directory)
    pdfs = sorted(list(d.glob("*.pdf")) + list(d.glob("*.PDF")))
    return pdfs


# ---------------------------------------------------------------------------
# Funzione 5: Generazione report
# ---------------------------------------------------------------------------

def file_overall_status(entry):
    """
    Calcola lo stato complessivo per un file:
    - CRASH: exception durante estrazione
    - FAIL: 0 campi PASS o errore nel result
    - PARTIAL: almeno 1 PASS ma non tutti
    - OK: tutti e 5 i campi sono PASS
    """
    fields = entry['fields']

    if entry['error'] and entry['result'] is None:
        return 'CRASH'

    pass_count = sum(1 for s in fields.values() if s == 'PASS')
    total = len(FIELDS)

    if pass_count == 0:
        return 'FAIL'
    elif pass_count == total:
        return 'OK'
    else:
        return 'PARTIAL'


def generate_report(results, directory, elapsed):
    """
    Produce il testo del report come stringa.

    Struttura:
    - Intestazione con data/ora, directory, totale PDF, tempo
    - Nota Docling disabilitato
    - PER-FORMAT SUMMARY: tabella con success rate per campo per formato
    - PER-FILE DETAIL: una riga per PDF
    - BASELINE SUMMARY: overall aggregated success rates
    """
    lines = []
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # -----------------------------------------------------------------------
    # Intestazione
    # -----------------------------------------------------------------------
    lines.append("=" * 72)
    lines.append(f"AUDIT PARSER BASELINE — {now_str}")
    lines.append("=" * 72)
    lines.append(f"PDF Directory  : {directory}")
    lines.append(f"Totale PDF     : {len(results)}")
    lines.append(f"Tempo totale   : {elapsed:.1f}s")
    lines.append("")
    lines.append("Nota: Docling fallback disabilitato (DOCLING_AVAILABLE=False in pdf_parser.py)")
    lines.append("      La baseline riflette il comportamento attuale del sistema in produzione.")
    lines.append("      I campi 'quantita' sono mappati su 'quantita_totale' (somma qty articoli).")
    lines.append("")

    # -----------------------------------------------------------------------
    # PER-FORMAT SUMMARY
    # -----------------------------------------------------------------------
    lines.append("-" * 72)
    lines.append("PER-FORMAT SUMMARY")
    lines.append("-" * 72)

    # Raggruppa per formato
    from collections import defaultdict
    by_format = defaultdict(list)
    for entry in results:
        by_format[entry['format']].append(entry)

    # Intestazione tabella
    header = f"{'Formato':<22} {'PDFs':>4}  {'cliente':>8}  {'num_ordine':>10}  {'articoli':>8}  {'quantita':>8}  {'data':>12}"
    lines.append(header)
    lines.append("-" * len(header))

    # Ordina i formati per nome
    for fmt in sorted(by_format.keys()):
        entries = by_format[fmt]
        n = len(entries)

        def pct(field):
            if n == 0:
                return '—'
            pass_n = sum(1 for e in entries if e['fields'].get(field) == 'PASS')
            return f"{pass_n * 100 // n}%"

        row = (
            f"{fmt:<22} {n:>4}  "
            f"{pct('cliente'):>8}  "
            f"{pct('numero_ordine'):>10}  "
            f"{pct('articoli'):>8}  "
            f"{pct('quantita'):>8}  "
            f"{pct('data_consegna'):>12}"
        )
        lines.append(row)

        # Evidenzia campi sotto 100%
        below_100 = []
        for field in FIELDS:
            p = pct(field)
            if p != '—' and p != '100%':
                below_100.append(f"{field}={p}")
        if below_100:
            lines.append(f"  *** Campi non al 100%: {', '.join(below_100)}")

    lines.append("")

    # -----------------------------------------------------------------------
    # PER-FILE DETAIL
    # -----------------------------------------------------------------------
    lines.append("-" * 72)
    lines.append("PER-FILE DETAIL")
    lines.append("-" * 72)

    for entry in results:
        status = file_overall_status(entry)
        fields = entry['fields']

        status_tag = f"[{status:<7}]"
        fmt_tag = f"{entry['format']:<18}"
        filename_tag = f"{entry['file']:<45}"

        if status == 'CRASH':
            err_msg = str(entry['error'])[:60] if entry['error'] else 'unknown error'
            lines.append(f"{status_tag} {filename_tag} {fmt_tag} CRASH: {err_msg}")
        else:
            # Costruisci dettaglio campi
            field_detail = (
                f"cliente:{fields.get('cliente','?'):<8} "
                f"ordine:{fields.get('numero_ordine','?'):<8} "
                f"art:{entry['article_count']:>3}/{fields.get('articoli','?'):<5} "
                f"qty:{fields.get('quantita','?'):<8} "
                f"data:{fields.get('data_consegna','?')}"
            )
            lines.append(f"{status_tag} {filename_tag} {fmt_tag} {field_detail}")

    lines.append("")

    # -----------------------------------------------------------------------
    # BASELINE SUMMARY
    # -----------------------------------------------------------------------
    lines.append("-" * 72)
    lines.append("BASELINE SUMMARY (overall)")
    lines.append("-" * 72)

    total = len(results)
    non_crash = [e for e in results if e['result'] is not None]
    crash_count = total - len(non_crash)

    if total == 0:
        lines.append("Nessun PDF analizzato.")
    else:
        lines.append(f"PDF analizzati : {total}")
        lines.append(f"CRASH          : {crash_count} ({crash_count * 100 // total}%)")
        lines.append("")

        for field in FIELDS:
            pass_n = sum(1 for e in non_crash if e['fields'].get(field) == 'PASS')
            fail_n = sum(1 for e in non_crash if e['fields'].get(field) in ('FAIL', 'EMPTY'))
            fallback_n = sum(1 for e in non_crash if e['fields'].get(field) == 'FALLBACK')
            pct_pass = pass_n * 100 // len(non_crash) if non_crash else 0
            lines.append(
                f"  {field:<20}: {pass_n:>2}/{len(non_crash):>2} PASS ({pct_pass}%)"
                + (f" | {fallback_n} FALLBACK" if fallback_n else "")
                + (f" | {fail_n} FAIL" if fail_n else "")
            )

        lines.append("")

        # Overall OK/PARTIAL/FAIL/CRASH
        status_counts = {'OK': 0, 'PARTIAL': 0, 'FAIL': 0, 'CRASH': crash_count}
        for e in non_crash:
            s = file_overall_status(e)
            status_counts[s] = status_counts.get(s, 0) + 1

        lines.append("Stato complessivo per file:")
        for s in ['OK', 'PARTIAL', 'FAIL', 'CRASH']:
            n = status_counts.get(s, 0)
            pct = n * 100 // total if total else 0
            lines.append(f"  {s:<8}: {n:>2} ({pct}%)")

    lines.append("")
    lines.append("=" * 72)
    lines.append("FINE REPORT")
    lines.append("=" * 72)

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Audit dei parser PDF: misura il success rate per campo e per formato.'
    )
    parser.add_argument(
        '--dir',
        default='C:/Users/39334/Documents/ORDINI',
        help='Directory contenente i PDF da analizzare (default: C:/Users/39334/Documents/ORDINI)'
    )
    args = parser.parse_args()

    directory = args.dir
    dir_path = Path(directory)

    if not dir_path.exists():
        print(f"ERRORE: La directory non esiste: {directory}")
        sys.exit(1)

    if not dir_path.is_dir():
        print(f"ERRORE: Il path specificato non e' una directory: {directory}")
        sys.exit(1)

    # Crea directory per i report
    script_dir = Path(__file__).parent
    reports_dir = script_dir / 'audit_reports'
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Trova PDF
    pdfs = find_pdfs(directory)
    if not pdfs:
        print(f"Nessun PDF trovato in: {directory}")
        sys.exit(0)

    print(f"Trovati {len(pdfs)} PDF in: {directory}")
    print(f"Report directory: {reports_dir}")
    print()

    # Audit di ogni PDF
    results = []
    start_time = time.time()

    for i, pdf_path in enumerate(pdfs, 1):
        print(f"Auditing {i}/{len(pdfs)}: {pdf_path.name}...")
        sys.stdout.flush()

        entry = audit_pdf(pdf_path)
        results.append(entry)

        # Mostra stato rapido
        status = file_overall_status(entry)
        print(f"  -> [{status}] formato={entry['format']} articoli={entry['article_count']}")
        sys.stdout.flush()

    elapsed = time.time() - start_time

    # Avviso se il runtime supera 90 secondi (segnale che Docling potrebbe essere attivo)
    if elapsed > 90:
        print()
        print(f"ATTENZIONE: Il tempo di esecuzione e' {elapsed:.1f}s (>90s).")
        print("  Verificare che DOCLING_AVAILABLE=False in app/backend/pdf_parser.py.")
        print()

    # Genera il report
    print()
    report_text = generate_report(results, directory, elapsed)

    # Stampa su stdout
    print(report_text)

    # Salva su file timestampato
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f"audit_{timestamp}.txt"
    report_path = reports_dir / report_filename

    with open(str(report_path), 'w', encoding='utf-8') as f:
        f.write(report_text)

    print()
    print(f"Report salvato in: {report_path}")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Test batch per TUTTI i PDF in ORDINI"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.pdf_parser import extract_pdf_content

ORDINI = Path("C:/Users/39334/Documents/ORDINI")

pdfs = sorted(ORDINI.glob("*.pdf"))

print("=" * 130)
print("BATCH TEST - Tutti i PDF in ORDINI")
print("=" * 130)
print(f"Testando {len(pdfs)} PDF\n")

success_count = 0
fail_count = 0
results = []

for pdf_path in pdfs:
    try:
        result = extract_pdf_content(str(pdf_path))
        
        articoli = result.get('articoli', [])
        cliente = result.get('cliente', 'N/A')
        ordine = result.get('numero_ordine', 'N/A')
        errore = result.get('error')
        
        if errore or len(articoli) == 0:
            status = "FAIL"
            fail_count += 1
        else:
            status = "OK"
            success_count += 1
        
        results.append({
            'file': pdf_path.name,
            'status': status,
            'articoli': len(articoli),
            'cliente': cliente,
            'ordine': ordine,
            'errore': errore
        })
        
        print(f"[{status:4s}] {pdf_path.name:50s} | Articoli: {len(articoli):2d} | Cliente: {cliente:25s} | Ordine: {str(ordine)[:15]}")
        
    except Exception as e:
        fail_count += 1
        print(f"[FAIL] {pdf_path.name:50s} | EXCEPTION: {str(e)[:60]}")

print("\n" + "=" * 130)
print(f"RISULTATI: {success_count} OK / {fail_count} FAILED ({success_count*100//(success_count+fail_count)}% success rate)")
print("=" * 130)

# Mostra i failed
if fail_count > 0:
    print("\nFailed PDFs:")
    for r in results:
        if r['status'] == 'FAIL':
            print(f"  - {r['file']}")
            if r['errore']:
                print(f"    Error: {r['errore'][:100]}")

#!/usr/bin/env python3
"""Test batch FINALE - Tutti i 16 PDF con timeout e gestione errori"""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

from backend.pdf_parser import extract_pdf_content

ORDINI = Path("C:/Users/39334/Documents/ORDINI")

pdfs = sorted(ORDINI.glob("*.pdf"))

print("=" * 150)
print("BATCH TEST FINALE - TUTTI I 16 PDF")
print("=" * 150)
print(f"Testing {len(pdfs)} PDF - Target: 100% success rate\n")

success_count = 0
fail_count = 0
results = []

start_time = time.time()

for i, pdf_path in enumerate(pdfs, 1):
    pdf_start = time.time()
    
    try:
        result = extract_pdf_content(str(pdf_path))
        
        articoli = result.get('articoli', [])
        cliente = result.get('cliente', 'N/A')
        ordine = result.get('numero_ordine', 'N/A')
        errore = result.get('error')
        
        elapsed = time.time() - pdf_start
        
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
            'cliente': cliente if cliente else '(empty)',
            'ordine': ordine if ordine else '(empty)',
            'time': elapsed,
            'errore': errore
        })
        
        bar = "=" * (i * 150 // len(pdfs))
        progress = f"[{i:2d}/{len(pdfs)}]"
        print(f"{progress} {status:4s} {pdf_path.name:55s} | Art: {len(articoli):2d} | Cli: {str(cliente)[:20]:20s} | Time: {elapsed:6.2f}s")
        
    except Exception as e:
        fail_count += 1
        elapsed = time.time() - pdf_start
        print(f"[{i:2d}/{len(pdfs)}] FAIL {pdf_path.name:55s} | EXCEPTION: {str(e)[:40]}")
        results.append({
            'file': pdf_path.name,
            'status': 'FAIL',
            'articoli': 0,
            'cliente': 'ERROR',
            'ordine': 'ERROR',
            'time': elapsed,
            'errore': str(e)[:100]
        })

total_time = time.time() - start_time
success_rate = (success_count * 100 // (success_count + fail_count)) if (success_count + fail_count) > 0 else 0

print("\n" + "=" * 150)
print(f"RISULTATI FINALI: {success_count} OK / {fail_count} FAILED")
print(f"Success Rate: {success_rate}%")
print(f"Total Time: {total_time:.1f}s ({total_time/len(pdfs):.1f}s/PDF)")
print("=" * 150)

# Dettagli success
print("\nSOUCCESS:")
for r in results:
    if r['status'] == 'OK':
        print(f"  [OK] {r['file']:50s} | Art: {r['articoli']:2d} | Cli: {r['cliente']:20s} | Ord: {str(r['ordine'])[:15]:15s}")

# Dettagli failures
if fail_count > 0:
    print("\nFAILURES:")
    for r in results:
        if r['status'] == 'FAIL':
            print(f"  [FAIL] {r['file']:45s} | {r['errore'][:60] if r['errore'] else '(no error msg)'}")

print("\n" + "=" * 150)
if success_rate == 100:
    print("STATUS: 100% SUCCESS - READY FOR PRODUCTION")
else:
    print(f"STATUS: {success_rate}% - {fail_count} PDF NEED FIXING")
print("=" * 150)

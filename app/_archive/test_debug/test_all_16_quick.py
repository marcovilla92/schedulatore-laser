#!/usr/bin/env python
"""Full test of all 16 PDFs - quick version without Docling"""

from backend.pdf_parser import extract_pdf_content
import os

all_pdfs = [
    ('C:/Users/39334/Documents/ORDINI/300000946.pdf', 'DIVISIONE 300000946'),
    ('C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000173_00(50359).pdf', 'FOR-ORDINE 0000173'),
    ('C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000205_00(50359).pdf', 'FOR-ORDINE 0000205'),
    ('C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000445_00(50359)[2].pdf', 'FOR-ORDINE 0000445'),
    ('C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000537_00(50359).pdf', 'FOR-ORDINE 0000537'),
    ('C:/Users/39334/Documents/ORDINI/OAFA202600125.pdf', 'OAFA202600125'),
    ('C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf', 'OF_260100'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf', 'ORDINE FORNITORE 57-AC'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 83-AC del 09-02-2026  L S S R L.pdf', 'ORDINE FORNITORE 83-AC'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 85-AC del 10-02-2026  L S S R L.pdf', 'ORDINE FORNITORE 85-AC'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 826-AC del 13-10-2025  L S S R L.pdf', 'ORDINE FORNITORE 826-AC'),
    ('C:/Users/39334/Documents/ORDINI/Ordine LS N°172.pdf', 'Ordine LS N°172'),
    ('C:/Users/39334/Documents/ORDINI/Ordine LS N°217.pdf', 'Ordine LS N°217'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE LS.PDF', 'ORDINE LS'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE_D_ACQUISTO_21-28707_LS.pdf', 'ORDINE_ACQUISTO_LS'),
    ('C:/Users/39334/Documents/ORDINI/PO_20250006705-3.pdf', 'PO_BEBITALIA 20250006705-3'),
]

print("=" * 80)
print("TESTING ALL 16 PDFs")
print("=" * 80)

success_count = 0
fail_count = 0 
results = []

for filepath, name in all_pdfs:
    if not os.path.exists(filepath):
        print(f"\n[ERROR] File not found: {name}")
        fail_count += 1
        continue
    
    try:
        result = extract_pdf_content(filepath)
        cliente = result.get('cliente', '')
        ordine = result.get('numero_ordine', '')
        articoli = result.get('articoli', [])
        
        # Success criteria: cliente and ordine present, at least 1 article
        success = cliente and ordine and len(articoli) >= 1
        
        if success:
            print(f"[OK] {name:40s} | C: {cliente:20s} | O: {ordine:10s} | Art: {len(articoli)}")
            success_count += 1
            results.append(('OK', name, cliente, ordine, len(articoli)))
        else:
            print(f"[FAIL] {name:40s} | C: {cliente[:15] if cliente else 'EMPTY':15s} | O: {ordine if ordine else 'EMPTY':10s} | Art: {len(articoli)}")
            fail_count += 1
            results.append(('FAIL', name, cliente, ordine, len(articoli)))
            
    except Exception as e:
        print(f"[ERROR] {name:40s} | {type(e).__name__}: {str(e)[:50]}")
        fail_count += 1
        results.append(('ERROR', name, '', '', 0))

print("\n" + "=" * 80)
print(f"RESULTS: {success_count}/{len(all_pdfs)} SUCCESS ({int(100*success_count/len(all_pdfs))}%)")
print("=" * 80)

# Show failed PDFs for quick reference
if fail_count > 0:
    print("\nFAILED PDFs:")
    for status, name, cliente, ordine, art_count in results:
        if status != 'OK':
            print(f"  - {name} [{status}]")

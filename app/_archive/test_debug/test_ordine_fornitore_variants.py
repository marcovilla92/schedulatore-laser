#!/usr/bin/env python
"""Test ORDINE FORNITORE variants"""

from backend.pdf_parser import extract_pdf_content
import os

variant_pdfs = [
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf', '57-AC'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 83-AC del 09-02-2026  L S S R L.pdf', '83-AC'),
]

print("=" * 80)
print("Testing ORDINE FORNITORE variants")
print("=" * 80)

for filepath, code in variant_pdfs:
    if not os.path.exists(filepath):
        print(f"\n[ERROR] File not found: {filepath}")
        continue
        
    print(f"\nOrdine {code}:")
    try:
        result = extract_pdf_content(filepath)
        cliente = result.get('cliente', '')
        ordine = result.get('numero_ordine', '')
        articoli = result.get('articoli', [])
        
        print(f"  Cliente: '{cliente}'")
        print(f"  Ordine: '{ordine}'")
        print(f"  Articoli: {len(articoli)}")
        
        if articoli:
            for art in articoli[:2]:
                print(f"    - {art['code']}: {art['name'][:40]}... ({art['qty']} pz)")
        else:
            print(f"    [WARNING] No articles!")
            
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {str(e)[:100]}")
        
print("\n" + "=" * 80)

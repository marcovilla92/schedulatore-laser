#!/usr/bin/env python
"""Quick test of first 2 fixed PDFs"""

from backend.pdf_parser import extract_pdf_content
import sys

# Disable Docling to avoid long wait
import os
os.environ['DOCLING_DISABLED'] = '1'

test_pdfs = [
    ('C:/Users/39334/Documents/ORDINI/300000946.pdf', 'DIVISIONE (300000946)'),
    ('C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf', 'OF_260100'),
]

print("=" * 80)
print("TESTING FIXED PDFs (without Docling)")
print("=" * 80)

for filepath, name in test_pdfs:
    print(f"\n{name}:")
    try:
        result = extract_pdf_content(filepath)
        cliente = result.get('cliente', '')
        ordine = result.get('numero_ordine', '')
        articoli = result.get('articoli', [])
        
        print(f"  Cliente: '{cliente}'")
        print(f"  Ordine: '{ordine}'")
        print(f"  Articoli: {len(articoli)}")
        
        if articoli:
            print(f"    - {articoli[0]['code']}: {articoli[0]['name'][:50]} ({articoli[0]['qty']})")
        else:
            print(f"    [WARNING] No articles!")
            
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {str(e)[:100]}")
        
print("\n" + "=" * 80)

#!/usr/bin/env python
"""Test FOR-ORDINE 173 with improved parser"""

from backend.pdf_parser import extract_pdf_content

pdf_path = 'C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000173_00(50359).pdf'

result = extract_pdf_content(pdf_path)

print(f"\n=== RESULT ===")
print(f"Cliente: {result.get('cliente')}")
print(f"Ordine: {result.get('numero_ordine')}")
print(f"Articoli: {len(result.get('articoli', []))} found")
for art in result.get('articoli', [])[:3]:
    print(f"  - {art}")

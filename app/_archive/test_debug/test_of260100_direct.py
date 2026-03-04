#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test OF_260100 estrazione diretta"""

from backend.parsers_for_ordine import extract_for_ordine
import PyPDF2

pdf_path = 'C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf'

with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    text = reader.pages[0].extract_text()

print(f"Text length: {len(text)}")
print(f"\nFirst 500 chars:\n{text[:500]}\n")

result = extract_for_ordine(text, None, pdf_path)

print(f"\nEstrazione:")
print(f"Cliente: '{result.get('cliente', '')}'")
print(f"Ordine: '{result.get('numero_ordine', '')}'")
print(f"Articoli: {len(result.get('articoli', []))}")
for art in result.get('articoli', []):
    print(f"  - {art['code']}: {art['name']} x{art['qty']}")

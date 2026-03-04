#!/usr/bin/env python
"""Test fix for OF_260100"""

from backend.pdf_parser import extract_pdf_content

result = extract_pdf_content('C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf')
print('RISULTATO OF_260100 DOPO FIX:')
print(f'Cliente: "{result.get("cliente", "")}"')
print(f'Numero ordine: "{result.get("numero_ordine", "")}"')
print(f'Articoli: {len(result.get("articoli", []))}')
if result.get('articoli'):
    for i, art in enumerate(result["articoli"], 1):
        print(f'  {i}. {art["code"]}: {art["name"]} ({art["qty"]} pz)')

#!/usr/bin/env python
"""Test della fix DIVISIONE cliente"""

from backend.pdf_parser import extract_pdf_content

result = extract_pdf_content('C:/Users/39334/Documents/ORDINI/300000946.pdf')
print('RISULTATO DIVISIONE DOPO FIX:')
print(f'Cliente: "{result.get("cliente", "")}"')
print(f'Numero ordine: "{result.get("numero_ordine", "")}"')
print(f'Articoli: {len(result.get("articoli", []))}')
print(f'Data consegna: "{result.get("data_consegna", "")}"')
if result.get('articoli'):
    print(f'Primo articolo: {result["articoli"][0]}')
    print(f'Ultimo articolo: {result["articoli"][-1]}')

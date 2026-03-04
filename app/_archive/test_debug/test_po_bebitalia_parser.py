#!/usr/bin/env python
"""Test parser PO_BEBITALIA"""

import sys
import os
sys.path.insert(0, 'backend')

from parsers_po_bebitalia import extract_po_bebitalia
from PyPDF2 import PdfReader

pdf_path = 'uploads/pdfs/PO_20250006705-3.pdf'

# Estrai testo
reader = PdfReader(pdf_path)
text = ""
for page in reader.pages:
    text += page.extract_text()

# Testa il parser
result = extract_po_bebitalia(text)

print("=" * 70)
print("TEST PARSER PO_BEBITALIA")
print("=" * 70)
print(f"File: {os.path.basename(pdf_path)}")
print()
print(f"Cliente: {result.get('cliente', 'N/A')}")
print(f"Numero: {result.get('numero_ordine', 'N/A')}")
print(f"Data Consegna: {result.get('data_consegna', 'N/A')}")
print(f"Data Ricezione: {result.get('data_ricezione', 'N/A')}")
print(f"Articoli trovati: {len(result.get('articoli', []))}")
print()

if result.get('articoli'):
    qty_total = sum(a['qty'] for a in result['articoli'])
    print(f"Quantita totale: {qty_total}")
    print()
    print("Articoli estratti:")
    for i, art in enumerate(result['articoli'], 1):
        print(f"  {i}. {art['code']} - {art['name'][:50]} - Qty: {art['qty']}")
else:
    print("ERRORE: Nessun articolo trovato!")

print()
print("=" * 70)
if len(result.get('articoli', [])) == 2 and sum(a['qty'] for a in result.get('articoli', [])) == 20:
    print("TEST PASSATO: 2 articoli, 20 unita totali")
else:
    print(f"TEST FALLITO: Atteso 2 articoli e 20 unita, trovati {len(result.get('articoli', []))} articoli")
print("=" * 70)

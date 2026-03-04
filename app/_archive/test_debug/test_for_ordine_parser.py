#!/usr/bin/env python
"""Test parser FOR-ORDINE"""

import sys
import os
sys.path.insert(0, 'backend')

from parsers_for_ordine import extract_for_ordine
from PyPDF2 import PdfReader

pdf_path = 'uploads/pdfs/FOR-ORDINE_0000205_00(50359).pdf'

# Estrai testo
reader = PdfReader(pdf_path)
text = ""
for page in reader.pages:
    text += page.extract_text()

# Testa il parser
result = extract_for_ordine(text)

print("=" * 70)
print("TEST PARSER FOR-ORDINE")
print("=" * 70)
print(f"File: {os.path.basename(pdf_path)}")
print()
print(f"Numero: {result.get('numero_ordine', 'N/A')}")
print(f"Cliente: {result.get('cliente', 'N/A') or '(non estratto)'}")
print(f"Data Ricezione: {result.get('data_ricezione', 'N/A')}")
print(f"Data Consegna: {result.get('data_consegna', 'N/A')}")
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
expected_articles = 3
expected_qty = 12  # 2 + 5 + 5
actual_articles = len(result.get('articoli', []))
actual_qty = sum(a['qty'] for a in result.get('articoli', []))

if actual_articles == expected_articles and actual_qty == expected_qty:
    print(f"TEST PASSATO: {expected_articles} articoli, {expected_qty} unita totali")
else:
    print(f"TEST FALLITO: Atteso {expected_articles} articoli e {expected_qty} unita, trovati {actual_articles} articoli e {actual_qty} unita")
print("=" * 70)

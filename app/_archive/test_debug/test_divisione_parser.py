#!/usr/bin/env python
"""Test diretto del parser DIVISIONE"""

from PyPDF2 import PdfReader
from backend.parsers_divisione import extract_divisione

# Testa il parser con DIVISIONE PDF
pdf_path = 'uploads/pdfs/300000946.pdf'

# Estrai testo dal PDF
reader = PdfReader(pdf_path)
text = ""
for page in reader.pages:
    text += page.extract_text()

# Testa il parser
result = extract_divisione(text)

print("=" * 70)
print("TEST PARSER DIVISIONE")
print("=" * 70)
print(f"File: {pdf_path}")
print()
print(f"Numero Ordine: {result['numero_ordine']}")
print(f"Cliente: {result['cliente']}")
print(f"Data Consegna: {result['data_consegna']}")
print(f"Data Ricezione: {result['data_ricezione']}")
print(f"Articoli trovati: {len(result['articoli'])}")
print()

if result['articoli']:
    qty_total = sum(a['qty'] for a in result['articoli'])
    print(f"Quantita totale: {qty_total}")
    print()
    print("Articoli estratti:")
    for i, art in enumerate(result['articoli'], 1):
        print(f"  {i:2}. {art['code']:15} - {art['name'][:50]:50} - Qty: {art['qty']:4}")
else:
    print("ERRORE: Nessun articolo trovato!")

print()
print("=" * 70)
if len(result['articoli']) == 13 and sum(a['qty'] for a in result['articoli']) == 865:
    print("TEST PASSATO: 13 articoli, 865 unita totali")
else:
    print(f"TEST FALLITO: Atteso 13 articoli e 865 unita, trovati {len(result['articoli'])} articoli")
print("=" * 70)

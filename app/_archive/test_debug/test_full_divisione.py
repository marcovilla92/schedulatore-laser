#!/usr/bin/env python
"""Test completo - Estrazione PDF attraverso dispatcher"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backend.pdf_parser as pdf_parser
import json

# Testa estrazione con dispatcher
pdf_path = 'uploads/pdfs/300000946.pdf'

result = pdf_parser.extract_pdf_content(pdf_path)

print("=" * 70)
print("TEST COMPLETO - ESTRAZIONE ATTRAVERSO DISPATCHER")
print("=" * 70)
print(f"File: {os.path.basename(pdf_path)}")
print()
print(f"Numero Ordine: {result.get('numero_ordine', 'N/A')}")
print(f"Cliente: {result.get('cliente', 'N/A') or '(non estratto)'}")
print(f"Data Consegna: {result.get('data_consegna', 'N/A')}")
print(f"Data Ricezione: {result.get('data_ricezione', 'N/A')}")
print(f"Quantita totale: {result.get('quantita_totale', 0)}")
print(f"Articoli trovati: {len(result.get('articoli', []))}")
print()

if result.get('articoli'):
    print("Articoli (primi 5):")
    for i, art in enumerate(result['articoli'][:5], 1):
        print(f"  {i}. {art['code']} - {art['name'][:40]} - Qty: {art['qty']}")
    if len(result['articoli']) > 5:
        print(f"  ... e altri {len(result['articoli'])-5}")
    print()

# Validazioni
passed = True
errors = []

if result.get('numero_ordine') != '300000946':
    passed = False
    errors.append(f"Numero ordine errato: {result.get('numero_ordine')}")

if len(result.get('articoli', [])) != 13:
    passed = False
    errors.append(f"Articoli: atteso 13, trovati {len(result.get('articoli', []))}")

expected_qty = 865
actual_qty = result.get('quantita_totale', 0)
if actual_qty != expected_qty:
    passed = False
    errors.append(f"Quantita totale: atteso {expected_qty}, trovato {actual_qty}")

print("=" * 70)
if passed:
    print("TEST PASSATO: DIVISIONE parser completamente funzionante!")
else:
    print("TEST FALLITO:")
    for error in errors:
        print(f"  - {error}")
print("=" * 70)

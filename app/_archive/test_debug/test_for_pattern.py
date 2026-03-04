#!/usr/bin/env python3
"""Test FOR-ORDINE con nuovo pattern"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.pdf_parser import extract_pdf_content

pdf = "C:/Users/39334/Downloads/FOR-ORDINE_0000205_00(50359).pdf"

print("=" * 80)
print("Testing FOR-ORDINE_0000205_00(50359).pdf")
print("=" * 80)

result = extract_pdf_content(pdf)

print(f"\nCliente: {result.get('cliente', 'N/A')}")
print(f"Ordine: {result.get('numero_ordine', 'N/A')}")
print(f"Articoli: {len(result.get('articoli', []))}")

for art in result.get('articoli', []):
    print(f"  - {art.get('code'):15s} | {art.get('name')[:45]:45s} | Qty: {art.get('qty')}")

print("=" * 80)

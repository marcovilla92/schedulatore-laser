#!/usr/bin/env python
"""Test del dispatcher PDF per auto-rilevamento formato DIVISIONE"""

import sys
import os

# Aggiungi il backend al path come package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyPDF2 import PdfReader
import backend.pdf_parser as pdf_parser

# Testa il rilevamento formato
pdf_path = 'uploads/pdfs/300000946.pdf'

reader = PdfReader(pdf_path)
text = ""
for page in reader.pages:
    text += page.extract_text()

detected_format = pdf_parser.detect_pdf_format(text)

print("=" * 70)
print("TEST RILEVAMENTO FORMATO - DISPATCHER PDF")
print("=" * 70)
print(f"File: {os.path.basename(pdf_path)}")
print(f"Formato rilevato: {detected_format}")
print()
if detected_format == "DIVISIONE":
    print("[OK] TEST PASSATO: Formato DIVISIONE rilevato correttamente")
else:
    print(f"[FAIL] TEST FALLITO: Atteso DIVISIONE, trovato {detected_format}")
print("=" * 70)

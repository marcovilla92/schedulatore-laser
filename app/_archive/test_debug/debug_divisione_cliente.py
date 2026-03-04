#!/usr/bin/env python
"""Debug DIVISIONE 300000946 - Estrae cliente"""
from backend.pdf_parser import extract_pdf_content
import PyPDF2

pdf_file = r'C:\Users\39334\Documents\ORDINI\300000946.pdf'

print("ANALISI PDF: DIVISIONE 300000946")
print("=" * 80)

# Estrai testo
with open(pdf_file, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    text = ""
    for page in reader.pages:
        text += page.extract_text()

# Stampa il testo per analisi
print("TESTO COMPLETO:")
print(text)
print("\n" + "=" * 80)
print("\nCERCA DEL CLIENTE:")

# Cerca pattern comuni per cliente
lines = text.split('\n')
for i, line in enumerate(lines[:50]):  # Primi 50 caratteri
    print(f"{i:3d}: {line}")

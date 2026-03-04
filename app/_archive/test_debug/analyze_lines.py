#!/usr/bin/env python3
"""Analizza riga per riga il PDF FOR-ORDINE"""
import PyPDF2
import re

pdf = "C:/Users/39334/Downloads/FOR-ORDINE_0000205_00(50359).pdf"

with open(pdf, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted

print("=" * 100)
print("TESTO ESTRATTO - RIGA PER RIGA")
print("=" * 100)

lines = text.split('\n')
for i, line in enumerate(lines):
    if line.strip():  # Solo linee non vuote
        print(f"  {i:3d}: [{len(line):3d} chars] {line[:90]}")

print("\n" + "=" * 100)
print("RIGHE CHE CONTENGONO POSSIBILI CODICI ARTICOLI")
print("=" * 100)

# Cerca righe che iniziano con un codice (numero/lettera combinati)
for i, line in enumerate(lines):
    # Pattern per articoli: 6+ caratteri alphanumerici
    if re.match(r'^[\w0-9\-]{6,}', line.strip()):
        print(f"  {i:3d}: {line[:100]}")

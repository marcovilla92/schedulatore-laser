#!/usr/bin/env python
"""Analyze ORDINE FORNITORE variant 57-AC structure"""

import PyPDF2

filepath = 'C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf'

with open(filepath, 'rb') as f:
    pdf = PyPDF2.PdfReader(f)
    text = pdf.pages[0].extract_text()

print("ORDINE FORNITORE 57-AC - Text structure:")
print(f"Total lines: {len(text.split(chr(10)))}\n")

lines = text.split('\n')
for i, line in enumerate(lines):
    if line.strip():  # Only print non-empty lines
        print(f"{i:3d}: {line[:100]}")

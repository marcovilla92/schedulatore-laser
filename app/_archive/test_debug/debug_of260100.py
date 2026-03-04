#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug OF_260100"""

import PyPDF2

pdf_path = 'C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf'
with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    text = reader.pages[0].extract_text()

print("Text: ", repr(text[:1000]))
print("\nSearching for company keywords...")

# Cerca keywords aziendali
for kw in ['TECNOAPP', 'S.R.L', 'SRL', 'S.P.A', 'SPA', 'TRADING', 'OFFICINE']:
    if kw in text.upper():
        idx = text.upper().find(kw)
        print(f"Found {kw} at position {idx}: ...{text[max(0,idx-50):idx+50]}...")

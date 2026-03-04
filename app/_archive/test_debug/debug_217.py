#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug LS N°217 - see what's in the PDF"""

import PyPDF2

pdf_path = 'C:/Users/39334/Documents/ORDINI/Ordine LS N°217.pdf'
with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    text = ''
    for page in reader.pages:
        text += page.extract_text()

print("=" * 80)
print("FULL TEXT OF N°217:")
print("=" * 80)
print(repr(text[:1000]))
print("\n" + "=" * 80)
print("FORMATTED TEXT (first 500 chars):")
print("=" * 80)
print(text[:500])

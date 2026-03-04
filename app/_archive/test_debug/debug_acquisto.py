#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Debug ORDINE_D_ACQUISTO PDF"""

import PyPDF2

pdf_path = 'C:/Users/39334/Documents/ORDINI/ORDINE_D_ACQUISTO_21-28707_LS.pdf'
with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    text = ''
    for page in reader.pages:
        text += page.extract_text()

print("=" * 80)
print("FULL TEXT:")
print("=" * 80)
print(text[:800])

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analizza dove è il cliente nei PDFs problematici"""

import PyPDF2

pdfs = [
    ('C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000173_00(50359).pdf', 'FOR-ORDINE 173'),
    ('C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf', 'OF_260100'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE LS.PDF', 'ORDINE LS'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE_D_ACQUISTO_21-28707_LS.pdf', 'ORDINE_D_ACQUISTO'),
]

for pdf_path, name in pdfs:
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = reader.pages[0].extract_text()
        
        print(f"\n{'='*80}")
        print(f"{name}:")
        print(f"{'='*80}")
        print(text[:800])
    except Exception as e:
        print(f"{name}: ERROR - {e}")

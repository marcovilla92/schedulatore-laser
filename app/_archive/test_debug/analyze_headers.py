#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analizza le intestazioni per identificare il cliente vero"""

import PyPDF2

pdfs = [
    ('C:/Users/39334/Documents/ORDINI/300000946.pdf', 'DIVISIONE'),
    ('C:/Users/39334/Documents/ORDINI/OAFA202600125.pdf', 'DECA'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf', 'AZA'),
    ('C:/Users/39334/Documents/ORDINI/Ordine LS N°172.pdf', 'ABIEFFE'),
    ('C:/Users/39334/Documents/ORDINI/PO_20250006705-3.pdf', 'BEBITALIA'),
]

for pdf_path, name in pdfs:
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = reader.pages[0].extract_text()
        
        # Mostra prime 500 caratteri
        print(f"\n{'='*80}")
        print(f"{name}:")
        print(f"{'='*80}")
        print(text[:600])
    except Exception as e:
        print(f"{name}: ERROR - {e}")

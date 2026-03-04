#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test the 3 failing LS PDFs"""

import os
from backend.pdf_parser import extract_pdf_content

test_pdfs = [
    ('uploads/drawings/Ordine LS N°217.pdf', 'Ordine LS N°217'),
    ('uploads/drawings/ORDINE LS.PDF', 'ORDINE LS'),
    ('uploads/drawings/ORDINE_D_ACQUISTO_21-28707_LS.pdf', 'ORDINE_D_ACQUISTO_LS'),
]

for pdf_path, name in test_pdfs:
    if os.path.exists(pdf_path):
        result = extract_pdf_content(pdf_path)
        cliente = result.get('cliente', '?')
        ordine = result.get('numero_ordine', '?')
        num_art = len(result.get('articoli', []))
        status = "OK" if num_art > 0 else "FAIL"
        print(f'[{status}] {name}: cliente={cliente} | ordine={ordine} | articoli={num_art}')
    else:
        print(f'[MISSING] {name}: NOT FOUND')

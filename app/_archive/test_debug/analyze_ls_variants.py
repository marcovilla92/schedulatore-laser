#!/usr/bin/env python
"""Check all 4 failing LS variants to see if they have same format"""

import PyPDF2
import os

ls_pdfs = [
    'C:/Users/39334/Documents/ORDINI/Ordine LS N°172.pdf',
    'C:/Users/39334/Documents/ORDINI/Ordine LS N°217.pdf',
    'C:/Users/39334/Documents/ORDINI/ORDINE LS.PDF',
    'C:/Users/39334/Documents/ORDINI/ORDINE_D_ACQUISTO_21-28707_LS.pdf',
]

for filepath in ls_pdfs:
    if not os.path.exists(filepath):
        print(f"Not found: {filepath}")
        continue
        
    print(f"\n{'='*80}")
    print(f"File: {os.path.basename(filepath)}")
    print('='*80)
    
    with open(filepath, 'rb') as f:
        pdf = PyPDF2.PdfReader(f)
        text = pdf.pages[0].extract_text()
        
    print(f"Total lines: {len(text.split(chr(10)))}\n")
    
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if line.strip():
            print(f"{i:2d}: {line[:110]}")

#!/usr/bin/env python
"""Debug script - extract text from failing PDFs to understand structure"""

import PyPDF2
import os

failing_pdfs = [
    ('C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf', 'OF_260100'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf', 'ORDINE FORNITORE 57-AC'),
    ('C:/Users/39334/Documents/ORDINI/Ordine LS N°172.pdf', 'Ordine LS N°172'),
]

print("=" * 80)
print("TEXT ANALYSIS: Failing PDFs (PyPDF2 extraction only)")
print("=" * 80)

for filepath, name in failing_pdfs:
    if not os.path.exists(filepath):
        print(f"\n[ERROR] FILE NOT FOUND: {filepath}")
        continue
    
    print(f"\n{'='*80}")
    print(f"PDF: {name}")
    print(f"File: {os.path.basename(filepath)}")
    print('='*80)
    
    try:
        with open(filepath, 'rb') as f:
            pdf = PyPDF2.PdfReader(f)
            print(f"Pages: {len(pdf.pages)}")
            
            # Extract first page text
            if pdf.pages:
                text = pdf.pages[0].extract_text()
                print(f"\nFIRST PAGE TEXT (first 100 lines):")
                print("-" * 80)
                
                lines = text.split('\n')[:100]
                for i, line in enumerate(lines, 1):
                    if line.strip():  # Only print non-empty lines
                        print(f"{i:3d}: {line}")
                        
    except Exception as e:
        print(f"[ERROR] {e}")

print("\n" + "=" * 80)

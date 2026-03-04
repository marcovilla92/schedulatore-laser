#!/usr/bin/env python
"""Quick test of first 6 PDFs"""

from backend.pdf_parser import extract_pdf_content

pdfs = [
    'C:/Users/39334/Documents/ORDINI/300000946.pdf',
    'C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000173_00(50359).pdf',
    'C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000205_00(50359).pdf',
    'C:/Users/39334/Documents/ORDINI/OAFA202600125.pdf',
    'C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf',
    'C:/Users/39334/Documents/ORDINI/PO_20250006705-3.pdf',
]

for pdf in pdfs:
    name = pdf.split('/')[-1]
    result = extract_pdf_content(pdf)
    cliente = result.get('cliente', '(empty)')
    ordine = result.get('numero_ordine', '(empty)')
    articoli = len(result.get('articoli', []))
    print(f"{name:40s} | C: {cliente:30s} | O: {ordine:15s} | Art: {articoli}")

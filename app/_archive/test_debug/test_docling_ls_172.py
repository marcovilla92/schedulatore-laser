#!/usr/bin/env python
"""Test Docling extraction on Ordine LS N°172"""

from docling.document_converter import DocumentConverter

pdf_path = 'C:/Users/39334/Documents/ORDINI/Ordine LS N°172.pdf'

try:
    converter = DocumentConverter()
    doc_result = converter.convert(pdf_path)
    
    # Export to markdown
    markdown_text = doc_result.document.export_to_markdown()
    
    print(f"=== Docling extracted text (first 1500 chars) ===")
    print(markdown_text[:1500])
    
    print(f"\n=== Searching for company names ===")
    lines = markdown_text.split('\n')
    for i, line in enumerate(lines[:80]):
        line_upper = line.upper()
        if any(kw in line_upper for kw in ['S.R.L', 'SRL', 'S.P.A', 'SPA', 'ABIEFFE', 'TECNOAPP', 'DECA', 'TRADING']):
            print(f"Line {i}: {line}")
            
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

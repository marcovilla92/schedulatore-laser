#!/usr/bin/env python
"""Test Docling extraction on FOR-ORDINE 0000173"""

from docling.document_converter import DocumentConverter
import re

pdf_path = 'C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000173_00(50359).pdf'

try:
    converter = DocumentConverter()
    doc_result = converter.convert(pdf_path)
    
    if hasattr(doc_result, 'status'):
        print(f"Docling conversion status: {doc_result.status}")
    
    # Export to markdown
    markdown_text = doc_result.document.export_to_markdown()
    
    print(f"=== Docling extracted text (first 2000 chars) ===")
    print(markdown_text[:2000])
    
    print(f"\n=== Searching for company names ===")
    lines = markdown_text.split('\n')
    for i, line in enumerate(lines[:100]):
        line_upper = line.upper()
        if any(kw in line_upper for kw in ['S.R.L', 'SRL', 'S.P.A', 'SPA', 'ABIEFFE', 'TECNOAPP', 'DECA', 'OFFICINE']):
            print(f"Line {i}: {line}")
            
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

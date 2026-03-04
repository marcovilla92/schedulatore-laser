#!/usr/bin/env python
"""Test Docling function inline"""

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import ConversionStatus
import re

def test_docling_fallback(filepath: str) -> str:
    """Test version with debug output"""
    try:
        print(f"Converting with Docling: {filepath}")
        converter = DocumentConverter()
        doc_result = converter.convert(filepath)
        
        print(f"Conversion status: {doc_result.status}")
        
        # Estrai testo markdown e cerca il primo nome di azienda
        text = doc_result.document.export_to_markdown()[:800]
        
        print(f"\n=== First 400 chars of Docling output ===")
        print(text[:400])
        
        # Cerca il primo nome significativo
        lines = text.split('\n')
        print(f"\n=== Lines with company names ===")
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped and len(line_stripped) > 3 and len(line_stripped) < 100:
                # Debug: show all non-empty lines
                if i < 20:
                    print(f"Line {i}: {repr(line_stripped[:70])}")
                
                # Skip linee che sono indirizzi, numeri, etc
                if re.search(r'^(VIA|TEL|FAX|EMAIL|MAIL|PAGE|N\.|DATA|NUMERO|CODICE)', line_stripped.upper()):
                    continue
                    
                # Check the condition
                has_upper = any(c.isupper() for c in line_stripped)
                has_srl = 'S.r.l' in line_stripped
                has_spa = 'SpA' in line_stripped or 'S.p.A' in line_stripped
                
                full_condition = (has_upper and has_srl) or has_spa
                
                if full_condition:
                    print(f"\n✓ MATCH Line {i}: {line_stripped}")
                    print(f"  - Has uppercase: {has_upper}")
                    print(f"  - Has S.r.l: {has_srl}")
                    print(f"  - Has S.p.A: {has_spa}")
                    return line_stripped
        
        print("\nNo matching line found!")
        return ""
        
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return ""


pdf_path = 'C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000173_00(50359).pdf'
result = test_docling_fallback(pdf_path)
print(f"\n=== FINAL RESULT ===")
print(f"Cliente: '{result}'")

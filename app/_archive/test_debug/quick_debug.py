#!/usr/bin/env python3
"""Debug test su un singolo PDF"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from backend.pdf_parser import extract_pdf_content
    
    pdf = "C:/Users/39334/Documents/ORDINI/OAFA202600125.pdf"
    
    print(f"Testing: {pdf}")
    
    result = extract_pdf_content(pdf)
    
    print(f"\nRESULT:")
    print(f"  Cliente: {result.get('cliente')}")
    print(f"  Ordine: {result.get('numero_ordine')}")
    print(f"  Articoli: {len(result.get('articoli', []))}")
    
    if result.get('error'):
        print(f"  ERROR: {result.get('error')}")
    
    for art in result.get('articoli', [])[:3]:
        print(f"    - {art}")

except Exception as e:
    print(f"EXCEPTION: {e}")
    import traceback
    traceback.print_exc()

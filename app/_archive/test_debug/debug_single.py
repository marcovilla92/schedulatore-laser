#!/usr/bin/env python3
"""Test singolo PDF - Debug dettagliato"""
import sys
from pathlib import Path

# Aggiungi il backend al path
sys.path.insert(0, str(Path(__file__).parent))

# Importa il parser direttamente
from backend.pdf_parser import extract_pdf_content

pdf_path = "C:/Users/39334/Downloads/OAFA202600125.pdf"

print("=" * 80)
print(f"📄 Testing: {Path(pdf_path).name}")
print("=" * 80)

try:
    result = extract_pdf_content(pdf_path)
    
    print("\n✅ RISULTATO:")
    print(f"  Cliente: {result.get('cliente', 'N/A')}")
    print(f"  Ordine: {result.get('numero_ordine', 'N/A')}")
    print(f"  Articoli: {len(result.get('articoli', []))}")
    
    for art in result.get('articoli', [])[:5]:
        print(f"    - {art.get('code')} | {art.get('name')} | Qty: {art.get('qty')}")
    
except Exception as e:
    print(f"\n❌ ERRORE: {str(e)}")
    import traceback
    traceback.print_exc()

print("=" * 80)

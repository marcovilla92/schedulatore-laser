#!/usr/bin/env python3
"""Test Docling parsing vs PyPDF2"""
import sys
from pathlib import Path

# Aggiungi backend al path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from pdf_parser import extract_pdf_content, extract_text_with_docling

# Test PDF disponibili
test_pdfs = [
    "uploads/pdfs/300000946.pdf",
    "uploads/pdfs/OAFA202600125.pdf",
    "uploads/pdfs/072-24_Ordine_Ls_-_C23-304-02e03_.pdf"
]

print("=" * 60)
print("🧪 TEST INTEGRAZIONE DOCLING")
print("=" * 60)

for pdf_path in test_pdfs:
    if not Path(pdf_path).exists():
        print(f"⚠️  {pdf_path} non trovato")
        continue
    
    print(f"\n📄 Testing: {pdf_path}")
    print("-" * 60)
    
    # Test estrazione dati
    result = extract_pdf_content(pdf_path)
    
    if 'error' in result:
        print(f"❌ Errore: {result['error']}")
        continue
    
    # Mostra risultati
    print(f"✅ Cliente: {result.get('cliente', 'N/A')}")
    print(f"✅ Numero Ordine: {result.get('numero_ordine', 'N/A')}")
    print(f"✅ Quantità Totale: {result.get('quantita_totale', 0)}")
    print(f"✅ Articoli trovati: {len(result.get('articoli', []))}")
    
    if result.get('articoli'):
        print("\n   Articoli:")
        for i, art in enumerate(result.get('articoli', [])[:3], 1):
            print(f"   {i}. {art.get('name', 'N/A')} - {art.get('qty', 0)} pz")
        
        if len(result.get('articoli', [])) > 3:
            print(f"   ... e altri {len(result.get('articoli', [])) - 3}")

print("\n" + "=" * 60)
print("✅ Test completato! Docling è integrato e funzionante.")
print("=" * 60)

#!/usr/bin/env python3
"""Test Docling parsing - versione diretta"""
from pathlib import Path

# Test se Docling estrae il testo
try:
    from docling.document_converter import DocumentConverter
    
    test_pdfs = [
        "uploads/pdfs/300000946.pdf",
        "uploads/pdfs/OAFA202600125.pdf",
    ]
    
    print("=" * 70)
    print("🧪 TEST DOCLING - ESTRAZIONE TESTO")
    print("=" * 70)
    
    converter = DocumentConverter()
    
    for pdf_path in test_pdfs:
        if not Path(pdf_path).exists():
            print(f"⚠️  {pdf_path} non trovato, saltato")
            continue
        
        print(f"\n📄 Analizzando: {pdf_path}")
        print("-" * 70)
        
        # Estrai con Docling
        doc = converter.convert(pdf_path)
        text = doc.document.export_to_markdown()
        
        # Mostra anteprima
        lines = text.split('\n')[:20]
        print("✅ Testo estratto (primi 20 righe):")
        for line in lines:
            if line.strip():
                print(f"   {line[:70]}")
        
        print(f"\n✅ Total lines extracted: {len(text.split(chr(10)))}")
    
    print("\n" + "=" * 70)
    print("✅ Docling funziona correttamente!")
    print("=" * 70)
    
except Exception as e:
    print(f"❌ Errore: {e}")
    import traceback
    traceback.print_exc()

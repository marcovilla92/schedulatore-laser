#!/usr/bin/env python
"""Test veloce - bypassa Docling, usa solo PyPDF2"""
import PyPDF2
import sys

pdfs = [
    'uploads/pdfs/OAFA202600125.pdf',
    'uploads/pdfs/ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf', 
    'uploads/pdfs/Ordine LS N°172.pdf'
]

print("\n" + "="*70)
print("📊 ANALISI VELOCE - CONTENUTO RAW PDF (PyPDF2)")
print("="*70 + "\n")

for pdf in pdfs:
    print(f"\n{'─'*70}")
    print(f"📄 {pdf.split('/')[-1]}")
    print(f"{'─'*70}")
    
    try:
        with open(pdf, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ''
            for page in reader.pages:
                text += page.extract_text() + '\n'
        
        # Mostri primi 1000 caratteri
        print("\n📋 PRIMI 1000 CARATTERI:")
        print(text[:1000])
        print(f"\n📊 STATISTICHE:")
        print(f"   Totale testo: {len(text)} caratteri")
        print(f"   Pagine: {len(reader.pages)}")
        
        # Cerca patterns
        has_codice = 'CODICE' in text.upper() or 'CODE' in text.upper()
        has_qty = any(x in text.upper() for x in ['QUANTITA', 'QTY', 'CANTIDAD'])
        has_tabella = '|' in text
        
        print(f"   Ha pattern codice? {has_codice}")
        print(f"   Ha pattern quantità? {has_qty}")
        print(f"   Ha pipe table? {has_tabella}")
        
    except Exception as e:
        print(f"❌ Errore: {e}")

print("\n" + "="*70)

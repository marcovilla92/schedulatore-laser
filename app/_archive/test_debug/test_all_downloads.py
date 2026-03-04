#!/usr/bin/env python3
"""Test tutti i PDF in Downloads - Estrazione diretta"""
import sys
from pathlib import Path

# Aggiungi il backend al path
sys.path.insert(0, str(Path(__file__).parent))

# Importa il parser direttamente
from backend.pdf_parser import extract_pdf_content

DOWNLOADS = Path("C:/Users/39334/Downloads")

PDFs = [
    "OAFA202600125.pdf",
    "FOR-ORDINE_0000205_00(50359).pdf",
    "ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf",
    "Ordine LS N°172.pdf",
    "072-24 Ordine LS - C23-304-02e03 -.pdf",
    "300000946.pdf",
    "PO_20250006705-3.pdf",
]

print("=" * 100)
print("⚡ TEST TUTTI PDF DOWNLOADS - Estrazione Diretta")
print("=" * 100)

for pdf_name in PDFs:
    pdf_path = DOWNLOADS / pdf_name
    if not pdf_path.exists():
        print(f"\n❌ NON TROVATO: {pdf_name}")
        continue
    
    print(f"\n📄 {pdf_name}")
    try:
        result = extract_pdf_content(str(pdf_path))
        articoli = result.get('articoli', [])
        cliente = result.get('cliente', 'N/A')
        ordine = result.get('numero_ordine', 'N/A')
        
        print(f"   ✅ Articoli: {len(articoli):2d} | Cliente: {cliente:30s} | Ordine: {ordine}")
        
        for i, art in enumerate(articoli[:2], 1):
            print(f"      {i}. {art.get('code', '?'):20s} | {art.get('name', '?')[:40]:40s} | Qty: {art.get('qty')}")
        
        if len(articoli) > 2:
            print(f"      ... + {len(articoli) - 2} articoli")
    
    except Exception as e:
        print(f"   ❌ ERRORE: {str(e)[:100]}")

print("\n" + "=" * 100)

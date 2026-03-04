#!/usr/bin/env python3
"""Test rapido per PDF in Downloads"""
import requests
import json
from pathlib import Path

BACKEND = "http://localhost:5000"
DOWNLOADS = Path("C:/Users/39334/Downloads")

# PDF da testare
PDFs = [
    "OAFA202600125.pdf",
    "FOR-ORDINE_0000205_00(50359).pdf",
    "ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf",
    "Ordine LS N°172.pdf",
    "072-24 Ordine LS - C23-304-02e03 -.pdf",
    "300000946.pdf",
    "PO_20250006705-3.pdf",
]

print("=" * 80)
print("⚡ TEST DOWNLOADS - Verifica estrazioni")
print("=" * 80)

for pdf_name in PDFs:
    pdf_path = DOWNLOADS / pdf_name
    if not pdf_path.exists():
        print(f"\n❌ NON TROVATO: {pdf_name}")
        continue
    
    print(f"\n📄 {pdf_name}")
    print(f"   Size: {pdf_path.stat().st_size / 1024:.1f} KB")
    
    try:
        # Invia il PDF al backend
        with open(pdf_path, 'rb') as f:
            response = requests.post(
                f"{BACKEND}/api/extract-pdf-data",
                files={'file': f},
                timeout=60
            )
        
        if response.status_code == 200:
            data = response.json()
            articoli = data.get('articoli', [])
            cliente = data.get('cliente', 'N/A')
            ordine = data.get('numero_ordine', 'N/A')
            
            print(f"   ✅ Articoli: {len(articoli)} | Cliente: {cliente} | Ordine: {ordine}")
            for i, art in enumerate(articoli[:3], 1):
                print(f"      {i}. {art.get('code', '?')} | {art.get('name', '?')} | Qty: {art.get('qty', '?')}")
            if len(articoli) > 3:
                print(f"      ... + {len(articoli) - 3} articoli")
        else:
            print(f"   ❌ ERRORE: {response.status_code}")
            print(f"      {response.text[:200]}")
    
    except Exception as e:
        print(f"   ❌ ECCEZIONE: {str(e)[:100]}")

print("\n" + "=" * 80)

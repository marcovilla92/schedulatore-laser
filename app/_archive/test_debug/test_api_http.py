#!/usr/bin/env python3
"""Test dell'API HTTP per Upload PDF"""
import requests
from pathlib import Path

ORDINI = Path("C:/Users/39334/Documents/ORDINI")
BACKEND = "http://localhost:5000"

# Prendi i primi 3 PDF per test veloce
pdfs = sorted(ORDINI.glob("*.pdf"))[:3]

print("=" * 100)
print("TEST API HTTP - Upload PDF su Backend")
print("=" * 100)
print(f"\nTest su {len(pdfs)} PDF via endpoint /api/extract-pdf-data\n")

for pdf_path in pdfs:
    print(f"\n[TEST] {pdf_path.name}")
    
    try:
        with open(pdf_path, 'rb') as f:
            response = requests.post(
                f"{BACKEND}/api/extract-pdf-data",
                files={'file': f},
                timeout=120
            )
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                data = result.get('data', {})
                articoli = data.get('articoli', [])
                cliente = data.get('cliente', 'N/A')
                ordine = data.get('numero_ordine', 'N/A')
                
                print(f"  Status: OK")
                print(f"  Articles: {len(articoli)}")
                print(f"  Client: {cliente}")
                print(f"  Order: {ordine}")
            else:
                print(f"  ERROR: {result.get('error')}")
        else:
            print(f"  HTTP Error: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
    
    except Exception as e:
        print(f"  EXCEPTION: {str(e)[:100]}")

print("\n" + "=" * 100)

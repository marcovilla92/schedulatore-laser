#!/usr/bin/env python
"""Test veloce - tutti 3 PDF, report sintetico"""
import requests
import json
import os

tests = [
    ('uploads/pdfs/OAFA202600125.pdf', 'OAFA'),
    ('uploads/pdfs/ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf', 'FOR-ORDINE'),
    ('uploads/pdfs/Ordine LS N°172.pdf', 'LS'),
]

print("\n" + "="*80)
print("⚡ TEST VELOCE - 3 PDF CON STRATEGIA PYDF2+PATTERN MATCHING")
print("="*80)

for pdf_path, name in tests:
    print(f"\n{name}:")
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': f}
            r = requests.post('http://localhost:5000/api/extract-pdf-data', files=files, timeout=60)
        
        if r.status_code == 200:
            data = r.json().get('data', {})
            arts = data.get('articoli', [])
            print(f"  ✅ Articoli: {len(arts)} | Cliente: {data.get('cliente', 'N/A')} | Ordine: {data.get('numero_ordine', 'N/A')}")
            if arts:
                for i, a in enumerate(arts[:2], 1):
                    print(f"     {i}. {a.get('code')} | {a.get('name', '')[:40]} | Qty: {a.get('qty')}")
                if len(arts) > 2:
                    print(f"     ... + {len(arts)-2} articoli")
        else:
            print(f"  ❌ HTTP {r.status_code}")
    except Exception as e:
        print(f"  ❌ {e}")

print("\n" + "="*80 + "\n")

#!/usr/bin/env python
"""Debug rapido - Verifica cosa sta succedendo realmente"""
import requests
import json

pdf_path = 'uploads/pdfs/OAFA202600125.pdf'
url = 'http://localhost:5000/api/extract-pdf-data'

print("="*70)
print("DEBUG TEST OAFA")
print("="*70)

with open(pdf_path, 'rb') as f:
    files = {'file': f}
    print(f"\n📤 Invio PDF...")
    response = requests.post(url, files=files, timeout=180)

print(f"📨 Status: {response.status_code}")
print(f"\n📋 RISPOSTA COMPLETA:")
print(json.dumps(response.json(), indent=2, ensure_ascii=False))

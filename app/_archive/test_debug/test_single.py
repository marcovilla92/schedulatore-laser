#!/usr/bin/env python
"""Test singolo OAFA con salvataggio su file"""
import requests
import json
import os
import time

output_file = 'test_results_OAFA.json'

pdf_path = 'uploads/pdfs/OAFA202600125.pdf'
BASE_URL = 'http://localhost:5000/api/extract-pdf-data'

print(f"Testando: {pdf_path}")
print(f"Risultati salvati in: {output_file}\n")

result = {
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    'pdf': pdf_path,
    'status': 'pending',
    'data': None,
    'error': None
}

try:
    print("📤 Invio PDF al server...")
    with open(pdf_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(BASE_URL, files=files, timeout=180)
    
    print(f"📨 Risposta ricevuta: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        result['status'] = 'success'
        result['data'] = data.get('data', {})
        
        # Print summary
        articles = result['data'].get('articoli', [])
        print(f"\n✅ SUCCESS!")
        print(f"   Cliente: {result['data'].get('cliente', 'N/A')}")
        print(f"   Ordine: {result['data'].get('numero_ordine', 'N/A')}")
        print(f"   Articoli: {len(articles)}")
        
        for i, art in enumerate(articles[:5], 1):
            print(f"      {i}. {art.get('code')} | {art.get('name', 'N/A')[:40]} | Qty: {art.get('qty')}")
        
        if len(articles) > 5:
            print(f"      ... + {len(articles)-5} altri")
    else:
        result['status'] = 'error'
        result['error'] = f"HTTP {response.status_code}"
        print(f"\n❌ Errore: {response.status_code}")
        
except Exception as e:
    result['status'] = 'error'
    result['error'] = str(e)
    print(f"❌ Errore: {e}")

# Salva risultati
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"\n💾 Risultati salvati in {output_file}")

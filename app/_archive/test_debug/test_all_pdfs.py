#!/usr/bin/env python
"""Batch test for all PDF formats"""
import requests
import json
import os
import time

test_files = [
    ('uploads/pdfs/OAFA202600125.pdf', 'OAFA', 'Expect ~15-16 articles'),
    ('uploads/pdfs/ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf', 'FOR_ORDINE', 'Expect 6 articles'),
    ('uploads/pdfs/Ordine LS N°172.pdf', 'LS_GENERIC', 'Expect 1+ articles'),
]

print("="*80)
print("🧪 BATCH TEST - ALL PDF FORMATS")
print("="*80)
print()

results_summary = []

for pdf_path, expected_format, note in test_files:
    print(f"\n{'─'*80}")
    print(f"📄 Testing: {os.path.basename(pdf_path)}")
    print(f"   Format: {expected_format} | {note}")
    print(f"{'─'*80}")
    
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        results_summary.append((expected_format, 'MISSING', 0, 0))
        continue
    
    try:
        time.sleep(2)  # Small delay between requests
        
        with open(pdf_path, 'rb') as pdf:
            files = {'file': pdf}
            response = requests.post('http://localhost:5000/api/extract-pdf-data', 
                                    files=files, timeout=120)
        
        if response.status_code == 200:
            try:
                data = response.json()
                articles = data.get('data', {}).get('articoli', [])
                cliente = data.get('data', {}).get('cliente', 'N/A')
                ordine = data.get('data', {}).get('numero_ordine', 'N/A')
                
                print(f"✅ Parsing successful!")
                print(f"   Cliente: {cliente}")
                print(f"   Numero Ordine: {ordine}")
                print(f"   Articoli found: {len(articles)}")
                
                if articles:
                    print(f"\n   Article list:")
                    for i, art in enumerate(articles[:5], 1):  # Show first 5
                        print(f"      {i}. {art.get('code'):20} | {art.get('name', 'N/A')[:40]:40} | Qty: {art.get('qty', 0)}")
                    
                    if len(articles) > 5:
                        print(f"      ... and {len(articles)-5} more articles")
                
                results_summary.append((expected_format, 'SUCCESS', len(articles), 
                                      ordine if ordine != 'N/A' else 'N/A'))
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON response: {response.text[:200]}")
                results_summary.append((expected_format, 'ERROR', 0, 'JSON_ERROR'))
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            results_summary.append((expected_format, 'ERROR', 0, 'HTTP_ERROR'))
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        results_summary.append((expected_format, 'ERROR', 0, str(e)[:20]))

# Print summary
print(f"\n\n{'='*80}")
print("📊 TEST SUMMARY")
print(f"{'='*80}")
print(f"{'Format':<20} {'Status':<12} {'Articles':<12} {'Order ID':<20}")
print(f"{'-'*64}")

for fmt, status, count, ordine in results_summary:
    status_icon = '✅' if status == 'SUCCESS' else '❌' if status == 'ERROR' else '⚠️'
    print(f"{fmt:<20} {status_icon} {status:<10} {count:<12} {str(ordine):<20}")

print(f"{'='*80}\n")

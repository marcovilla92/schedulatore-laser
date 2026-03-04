#!/usr/bin/env python
"""Test script for OAFA202600125.pdf parsing"""
import requests
import json
import os
import time

# Attendi che il server sia pronto
print("⏳ Attendo che il server sia pronto...")
time.sleep(2)

# Carica il PDF OAFA
pdf_path = r'uploads/pdfs/OAFA202600125.pdf'

if not os.path.exists(pdf_path):
    print(f"❌ File non trovato: {pdf_path}")
else:
    print(f"📁 File trovato: {pdf_path}")
    print(f"📤 Invio PDF al server...")
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': f}
            response = requests.post('http://localhost:5000/api/extract-pdf-data', files=files, timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Parsing completato!")
            print(f"\n📋 RISULTATI:")
            print(f"   Cliente: {data.get('cliente', 'N/A')}")
            print(f"   Numero Ordine: {data.get('numero_ordine', 'N/A')}")
            print(f"   Data Consegna: {data.get('data_consegna', 'N/A')}")
            print(f"\n📦 ARTICOLI ({len(data.get('articoli', []))}):")
            for i, art in enumerate(data.get('articoli', []), 1):
                print(f"   {i:2d}. {art.get('code', 'N/A'):20} | {art.get('name', 'N/A')[:50]:50} | Qty: {art.get('qty', 0):>5}")
            
            print(f"\n🎯 TOTALE ARTICOLI ESTRATTI: {len(data.get('articoli', []))}")
            print(f"   Atteso: 17")
            print(f"   Risultato: {'✅ SUCCESSO!' if len(data.get('articoli', [])) == 17 else '❌ FALLITO'}")
            
        else:
            print(f"❌ Errore: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Errore di connessione: {e}")

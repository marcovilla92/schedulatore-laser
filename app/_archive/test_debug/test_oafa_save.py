#!/usr/bin/env python
"""Test script for OAFA202600125.pdf parsing - saves output to file"""
import requests
import json
import os
import time

output_file = 'test_oafa_results.txt'

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("📋 OAFA202600125 TEST RESULTS\n")
    f.write("="*70 + "\n\n")
    
    # Attendi che il server sia pronto
    f.write("⏳ Attendo che il server sia pronto...\n")
    f.flush()
    time.sleep(2)
    
    # Carica il PDF OAFA
    pdf_path = r'uploads/pdfs/OAFA202600125.pdf'
    
    if not os.path.exists(pdf_path):
        f.write(f"❌ File non trovato: {pdf_path}\n")
    else:
        f.write(f"📁 File trovato: {pdf_path}\n")
        f.write(f"📤 Invio PDF al server...\n")
        f.flush()
        
        try:
            with open(pdf_path, 'rb') as pdf:
                files = {'file': pdf}
                response = requests.post('http://localhost:5000/api/extract-pdf-data', files=files, timeout=120)
            
            if response.status_code == 200:
                data = response.json()
                f.write(f"\n✅ Parsing completato!\n\n")
                f.write(f"📋 RISULTATI:\n")
                f.write(f"   Cliente: {data.get('cliente', 'N/A')}\n")
                f.write(f"   Numero Ordine: {data.get('numero_ordine', 'N/A')}\n")
                f.write(f"   Data Consegna: {data.get('data_consegna', 'N/A')}\n")
                
                articles = data.get('articoli', [])
                f.write(f"\n📦 ARTICOLI ({len(articles)}):\n")
                for i, art in enumerate(articles, 1):
                    f.write(f"   {i:2d}. {art.get('code', 'N/A'):20} | {art.get('name', 'N/A')[:50]:50} | Qty: {art.get('qty', 0):>5}\n")
                
                f.write(f"\n🎯 TOTALE ARTICOLI ESTRATTI: {len(articles)}\n")
                f.write(f"   Atteso: 17\n")
                f.write(f"   Risultato: {'✅ SUCCESSO!' if len(articles) == 17 else f'❌ FALLITO ({len(articles)}/17)'}\n")
                
                # Stampa JSON completo
                f.write(f"\n📊 JSON COMPLETO:\n")
                f.write(json.dumps(data, indent=2, ensure_ascii=False))
                
            else:
                f.write(f"❌ Errore: {response.status_code}\n")
                f.write(f"Response:\n{response.text}\n")
        except Exception as e:
            f.write(f"❌ Errore di connessione: {e}\n")

# Leggi e stampa il file
print("\n" + "="*70)
print("RISULTATI TEST SALVATI IN:", output_file)
print("="*70)

with open(output_file, 'r', encoding='utf-8') as f:
    print(f.read())

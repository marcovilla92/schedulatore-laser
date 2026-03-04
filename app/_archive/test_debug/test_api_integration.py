#!/usr/bin/env python
"""Test della integrazione dell'API e del processing dei PDF"""
import os
import sys
import json

# Aggiungi il backend al path
sys.path.insert(0, 'backend')

from app import extract_pdf_content

def test_pdf_extraction():
    """Test estrazione PDF"""
    ordini_folder = 'C:/Users/39334/Documents/ORDINI'
    
    if not os.path.exists(ordini_folder):
        print(f"❌ Cartella non trovata: {ordini_folder}")
        return
    
    pdf_files = sorted([f for f in os.listdir(ordini_folder) if f.lower().endswith('.pdf')])
    
    print(f"\n📊 TEST ESTRAZIONE {len(pdf_files)} PDF")
    print("=" * 85)
    
    success_count = 0
    error_count = 0
    results = []
    
    for idx, pdf_file in enumerate(pdf_files[:8], 1):
        try:
            pdf_path = os.path.join(ordini_folder, pdf_file)
            data = extract_pdf_content(pdf_path)
            
            is_success = bool(data.get('numero_ordine'))
            status = "✓" if is_success else "✗"
            
            cliente = data.get('cliente', 'N/A')[:25]
            ordine = str(data.get('numero_ordine', 'N/A'))[:12]
            articoli = len(data.get('articoli', []))
            
            print(f"{status} [{idx}] {pdf_file[:45]:45s} | {cliente:25s} | ord: {ordine:12s} | art: {articoli}")
            
            results.append({
                'file': pdf_file,
                'cliente': data.get('cliente'),
                'ordine': data.get('numero_ordine'),
                'articoli': articoli,
                'status': 'ok' if is_success else 'error'
            })
            
            if is_success:
                success_count += 1
            else:
                error_count += 1
                
        except Exception as e:
            error_count += 1
            print(f"✗ [{idx}] {pdf_file[:45]:45s} | ERRORE: {str(e)[:45]}")
    
    print("=" * 85)
    print(f"✓ Successo: {success_count}/{len(pdf_files[:8])} | ✗ Errori: {error_count}")
    print()
    
    # Stampa JSON
    print("RISULTATI (JSON):")
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    test_pdf_extraction()

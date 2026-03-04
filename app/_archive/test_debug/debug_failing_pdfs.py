#!/usr/bin/env python
"""Debug script per analizzare i PDF che falliscono"""

from backend.pdf_parser import extract_pdf_content
import os

# Lista dei PDF che falliscono
failing_pdfs = [
    ('C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf', 'OF_260100'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf', 'ORDINE FORNITORE 57-AC'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 83-AC del 09-02-2026  L S S R L.pdf', 'ORDINE FORNITORE 83-AC'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 85-AC del 10-02-2026  L S S R L.pdf', 'ORDINE FORNITORE 85-AC'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 826-AC del 13-10-2025  L S S R L.pdf', 'ORDINE FORNITORE 826-AC'),
    ('C:/Users/39334/Documents/ORDINI/Ordine LS N°172.pdf', 'Ordine LS N°172'),
    ('C:/Users/39334/Documents/ORDINI/Ordine LS N°217.pdf', 'Ordine LS N°217'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE LS.PDF', 'ORDINE LS'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE_D_ACQUISTO_21-28707_LS.pdf', 'ORDINE_D_ACQUISTO_LS'),
]

print("=" * 80)
print("DEBUG: Analizzando PDF che falliscono")
print("=" * 80)

for filepath, name in failing_pdfs:
    if not os.path.exists(filepath):
        print(f"\n[ERROR] FILE NOT FOUND: {filepath}")
        continue
    
    print(f"\n{'='*80}")
    print(f"PDF: {name}")
    print(f"File: {os.path.basename(filepath)}")
    print('='*80)
    
    try:
        result = extract_pdf_content(filepath)
        
        cliente = result.get('cliente', '')
        ordine = result.get('numero_ordine', '')
        articoli = result.get('articoli', [])
        
        print(f"[OK] Cliente: '{cliente}'")
        print(f"[OK] Ordine: '{ordine}'")
        print(f"[OK] Articoli: {len(articoli)}")
        
        if articoli:
            print(f"\n  Esempi articoli:")
            for art in articoli[:3]:
                print(f"    - {art.get('code')}: {art.get('name')} (qty: {art.get('qty')})")
        else:
            print(f"\n  [WARNING] NESSUN ARTICOLO TROVATO!")
            
    except Exception as e:
        print(f"[ERROR] ERRORE: {e}")

print("\n" + "=" * 80)
print("DEBUG COMPLETO")
print("=" * 80)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test COMPLETO e DETTAGLIATO su TUTTI i 16 PDF - NESSUNA SOSTA FINCHE NON E' 100%"""
import os
import sys
from pathlib import Path
from backend.pdf_parser import extract_pdf_content

# Lista esatta dei 16 PDF
PDF_DIR = r'C:\Users\39334\Documents\ORDINI'
PDFS = [
    '300000946.pdf',
    'FOR-ORDINE_0000173_00(50359).pdf',
    'FOR-ORDINE_0000205_00(50359).pdf',
    'FOR-ORDINE_0000445_00(50359)[2].pdf',
    'FOR-ORDINE_0000537_00(50359).pdf',
    'OAFA202600125.pdf',
    'OF_260100-del-21-01-2026.pdf',
    'ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf',
    'ORDINE FORNITORE 826-AC del 13-10-2025  L S S R L.pdf',
    'ORDINE FORNITORE 83-AC del 09-02-2026  L S S R L.pdf',
    'ORDINE FORNITORE 85-AC del 10-02-2026  L S S R L.pdf',
    'Ordine LS N°172.pdf',
    'Ordine LS N°217.pdf',
    'ORDINE LS.PDF',
    'ORDINE_D_ACQUISTO_21-28707_LS.pdf',
    'PO_20250006705-3.pdf',
]

print('=' * 80)
print('TEST COMPLETO - TUTTI I 16 PDF - ACQUISIZIONE PARAMETRI 100%')
print('=' * 80)
print(f'\nTotali PDF da testare: {len(PDFS)}')
print()

success_count = 0
fail_count = 0
results = []

for idx, pdf_name in enumerate(PDFS, 1):
    pdf_path = os.path.join(PDF_DIR, pdf_name)
    
    print(f'\n[{idx:2d}/16] Testando: {pdf_name}')
    print('-' * 80)
    
    if not os.path.exists(pdf_path):
        print(f'      ERRORE: File non trovato!')
        fail_count += 1
        results.append({'file': pdf_name, 'status': 'FILE_NOT_FOUND'})
        continue
    
    try:
        # Estrai i dati
        result = extract_pdf_content(pdf_path)
        
        # Verifica i parametri
        cliente = result.get('cliente', '').strip()
        articoli_list = result.get('articoli', [])
        num_articoli = len(articoli_list)
        ordine = result.get('numero_ordine', '').strip()
        data_consegna = result.get('data_consegna', '').strip()
        
        # Valuta il successo
        if cliente and num_articoli > 0 and ordine:
            status = 'SUCCESS'
            success_count += 1
            print(f'      STATUS: OK')
            print(f'      Cliente: {cliente}')
            print(f'      Articoli: {num_articoli}')
            print(f'      Ordine: {ordine}')
            print(f'      Data Consegna: {data_consegna}')
            results.append({
                'file': pdf_name,
                'status': 'SUCCESS',
                'cliente': cliente,
                'num_articoli': num_articoli,
                'ordine': ordine
            })
        else:
            status = 'FAILED'
            fail_count += 1
            print(f'      STATUS: FAILED (dati incompleti)')
            print(f'      Cliente: "{cliente}" (vuoto={not cliente})')
            print(f'      Articoli: {num_articoli}')
            print(f'      Ordine: "{ordine}" (vuoto={not ordine})')
            if num_articoli > 0:
                print(f'      Primi articoli:')
                for i, art in enumerate(articoli_list[:2]):
                    print(f'        - {art.get("code", "N/A")} | {art.get("name", "N/A")[:50]}...')
            results.append({
                'file': pdf_name,
                'status': 'FAILED',
                'cliente': cliente,
                'num_articoli': num_articoli,
                'ordine': ordine,
                'debug': {
                    'has_cliente': bool(cliente),
                    'has_articoli': num_articoli > 0,
                    'has_ordine': bool(ordine)
                }
            })
            
    except Exception as e:
        fail_count += 1
        print(f'      STATUS: EXCEPTION')
        print(f'      Errore: {str(e)[:100]}')
        results.append({'file': pdf_name, 'status': 'EXCEPTION', 'error': str(e)})

# RIEPILOGO FINALE
print('\n' + '=' * 80)
print(f'RISULTATI FINALI: {success_count}/{len(PDFS)} SUCCESSI ({success_count*100//len(PDFS)}%)')
print('=' * 80)

print('\nPDF SUCCESSO:')
for r in results:
    if r['status'] == 'SUCCESS':
        print(f"  [OK] {r['file']}")
        print(f"       - Cliente: {r['cliente']}")
        print(f"       - Articoli: {r['num_articoli']}")
        print(f"       - Ordine: {r['ordine']}")

if fail_count > 0:
    print(f'\nPDF FALLITI: ({fail_count})')
    for r in results:
        if r['status'] != 'SUCCESS':
            print(f"  [FAIL] {r['file']}")
            if r['status'] == 'FAILED':
                print(f"         - Cliente presente: {r.get('debug', {}).get('has_cliente', False)}")
                print(f"         - Articoli estratti: {r.get('num_articoli', 0)}")
                print(f"         - Ordine presente: {r.get('debug', {}).get('has_ordine', False)}")
            else:
                print(f"         - Errore: {r.get('error', 'Unknown')}")

if success_count == len(PDFS):
    print('\n' + '!' * 80)
    print('SUCCESSO TOTALE - TUTTI I 16 PDF ESTRATTI AL 100%')
    print('!' * 80)
else:
    print(f'\nPROBLEMI RILEVATI: {fail_count} PDF non estratti correttamente')
    print('Prossimo step: Debug dei PDF falliti e fix dei pattern')

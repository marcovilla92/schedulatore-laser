#!/usr/bin/env python
"""Test tutti i 4 formati PDF"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backend.pdf_parser as pdf_parser

# Test file mapping
test_files = {
    'OAFA': ('uploads/pdfs/OAFA202600125.pdf', {
        'numero': 'A000125',
        'articoli': 17,
        'quantita': 21,
    }),
    'FOR-ORDINE': ('uploads/pdfs/FOR-ORDINE_0000205_00(50359).pdf', {
        'numero': '205',
        'articoli': 3,
        'quantita': 12,
    }),
    'DIVISIONE': ('uploads/pdfs/300000946.pdf', {
        'numero': '300000946',
        'articoli': 13,
        'quantita': 865,
    }),
    'PO_BEBITALIA': ('uploads/pdfs/PO_20250006705-3.pdf', {
        'numero': '20250006705-3',
        'articoli': 2,
        'quantita': 20,
    }),
}

print("=" * 70)
print("TEST TUTTI I 4 FORMATI PDF")
print("=" * 70)

results_summary = []

for format_name, (pdf_path, expected_data) in test_files.items():
    if not os.path.exists(pdf_path):
        print(f"\n[SKIP] {format_name}: file non trovato ({os.path.basename(pdf_path)})")
        results_summary.append((format_name, 'SKIP', 'File not found'))
        continue
    
    try:
        result = pdf_parser.extract_pdf_content(pdf_path)
        
        # Validate
        passed = True
        errors = []
        
        if 'numero' in expected_data and result.get('numero_ordine') != expected_data['numero']:
            passed = False
            errors.append(f"numero: atteso {expected_data['numero']}, trovato {result.get('numero_ordine')}")
        
        if 'articoli' in expected_data and len(result.get('articoli', [])) != expected_data['articoli']:
            passed = False
            errors.append(f"articoli: atteso {expected_data['articoli']}, trovati {len(result.get('articoli', []))}")
        
        if 'articoli_min' in expected_data and len(result.get('articoli', [])) < expected_data['articoli_min']:
            passed = False
            errors.append(f"articoli: minimo {expected_data['articoli_min']}, trovati {len(result.get('articoli', []))}")
        
        if 'quantita' in expected_data and result.get('quantita_totale', 0) != expected_data['quantita']:
            passed = False
            errors.append(f"quantita: atteso {expected_data['quantita']}, trovato {result.get('quantita_totale', 0)}")
        
        status = 'PASS' if passed else 'FAIL'
        print(f"\n[{status}] {format_name}")
        print(f"      File: {os.path.basename(pdf_path)}")
        print(f"      Numero: {result.get('numero_ordine', 'N/A')}")
        print(f"      Articoli: {len(result.get('articoli', []))}")
        print(f"      Quantita: {result.get('quantita_totale', 0)}")
        
        if errors:
            for error in errors:
                print(f"      ! {error}")
        
        results_summary.append((format_name, status, errors if errors else 'OK'))
        
    except Exception as e:
        print(f"\n[ERROR] {format_name}: {str(e)}")
        results_summary.append((format_name, 'ERROR', str(e)))

# Summary
print("\n" + "=" * 70)
print("RIEPILOGO")
print("=" * 70)
for format_name, status, msg in results_summary:
    status_display = f"[{status}]"
    print(f"{format_name:15} {status_display:8} {msg if isinstance(msg, str) else ''}")

# Overall result
all_passed = all(status == 'PASS' for _, status, _ in results_summary if status not in ('SKIP', 'ERROR'))
print()
if all_passed:
    print("RISULTATO: TUTTI I FORMATI FUNZIONANO CORRETTAMENTE!")
else:
    print("RISULTATO: ALCUNI FORMATI PRESENTANO PROBLEMI")
print("=" * 70)

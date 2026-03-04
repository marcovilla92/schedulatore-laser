#!/usr/bin/env python
"""Debug script per analizzare PDF OAFA"""
import re
import sys
sys.path.insert(0, r'C:\Users\39334\Documents\SCHEDULATORE LASER\app')

from docling.document_converter import DocumentConverter

# Load PDF
pdf_path = r'C:\Users\39334\Downloads\OAFA202600125.pdf'
print(f"📄 Analizzing: {pdf_path}\n")

converter = DocumentConverter()
result = converter.convert(pdf_path)
text = result.document.export_to_markdown()

# Salva il testo in un file per analisi manuale
with open('debug_oafa_text.txt', 'w', encoding='utf-8') as f:
    f.write(text)
print("✅ Testo estratto salvato in: debug_oafa_text.txt\n")

print('=== PATTERN SEARCH ===\n')

# Cerca codici tipo 25CCPA...
codes = re.findall(r'25[A-Z]{2}[A-Z0-9\-]{0,10}', text)
unique_codes = list(set(codes))
print(f'🔹 Codici trovati (25CCXX): {len(unique_codes)}')
for code in sorted(unique_codes):
    print(f'  - {code}')

print()

# Cerca quantità (numeri seguiti da Nr o n°)
qtys_nr = re.findall(r'(\d+[.,]\d+)\s*(?:Nr|n°)', text)
print(f'🔹 Quantità (pattern Nr/n°): {len(qtys_nr)}')
for i, qty in enumerate(qtys_nr[:20], 1):
    print(f'  {i}. {qty}')

print()

# Analizza struttura sezione articoli
print('🔹 Sezione articoli (primi 2000 caratteri):')
section_start = text.find('Codice')
if section_start >= 0:
    section = text[section_start:section_start+2000]
    # Mostra prime righe
    lines = section.split('\n')[:30]
    for line in lines:
        if line.strip():
            print(f'  {line[:80]}')

print('\n=== CONTEGGIO TOTALE ===')
print(f'Codici unici: {len(unique_codes)}')
print(f'Quantità trovate: {len(qtys_nr)}')
print(f'Nota: Se 17 articoli, dovrebbero essercene 17 di entrambi')

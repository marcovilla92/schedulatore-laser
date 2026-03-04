#!/usr/bin/env python3
"""Test pattern regex direttamente"""
import PyPDF2
import re

pdf = "C:/Users/39334/Downloads/FOR-ORDINE_0000205_00(50359).pdf"

with open(pdf, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted

print("=" * 100)
print("TEST PATTERN MATCHING")
print("=" * 100)

# Prova vari pattern
patterns = [
    (r'PZ\s+([\w0-9\-]{6,})', "Baseline: PZ CODICE"),
    (r'PZ\s+(\d{3}[A-Z]+\d+)', "Specifico: PZ 708 o simile"),
    (r'(708[A-Z0-9]+)\s+(\d+[,.]\d+)\s+(\d+)\s+([A-Z].*?)(?=\d{2}/\d{2}/\d{4}|$)', "Il formato esatto"),
    (r'708[A-Z0-9]+', "Cerca 708XXXX"),
]

for pattern, description in patterns:
    print(f"\n[{description}]")
    print(f"Pattern: {pattern}")
    matches = re.findall(pattern, text)
    print(f"Matches: {len(matches)}")
    for i, m in enumerate(matches[:3]):
        print(f"  {i+1}. {str(m)[:80]}")

print("\n" + "=" * 100)
print("CERCHIAMO 708SEDIMP31 NEL TESTO")
print("=" * 100)

if '708SEDIMP31' in text:
    idx = text.find('708SEDIMP31')
    print(f"Trovato! Indice: {idx}")
    print(f"Contesto (100 ch prima / dopo):")
    print(f"  ... {text[max(0, idx-100):idx+100]} ...")
else:
    print("NON TROVATO NEL TESTO!")
    print("\nSearching simili:")
    for match in re.finditer(r'708\w+', text):
        print(f"  {text[match.start():match.end()]}")

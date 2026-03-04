#!/usr/bin/env python3
"""Debug FOR-ORDINE_0000173 - perche estrae solo 1 articolo?"""
import PyPDF2
import re

pdf = "C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000173_00(50359).pdf"

with open(pdf, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted

print("=" * 100)
print("DEBUG FOR-ORDINE_0000173")
print("=" * 100)

# Stampa il testo riga per riga
print("\nTESTO COMPLETO:")
print("=" * 100)
lines = text.split('\n')
for i, line in enumerate(lines):
    if line.strip():
        print(f"{i:3d}: {line}")

# Cerca PZ
print("\n" + "=" * 100)
print("RICERCA PZ:")
print("=" * 100)
pz_pattern = r'PZ\s+([\w0-9\-]{6,})'
matches = list(re.finditer(pz_pattern, text))
print(f"Trovati {len(matches)} matches per PZ pattern")

for m in matches:
    idx = m.start()
    context = text[max(0, idx-50):min(len(text), idx+150)]
    print(f"\nMatch: {m.group(1)}")
    print(f"Context: ...{context}...")

# Debug: print tutto il testo per vedere cosa c'è
print("\n" + "=" * 100)
print(f"TESTO BRUTO ({len(text)} chars):")
print("=" * 100)
print(text)

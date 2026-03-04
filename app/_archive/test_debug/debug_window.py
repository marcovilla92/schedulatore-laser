#!/usr/bin/env python
from PyPDF2 import PdfReader

pdf_path = 'C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf'
reader = PdfReader(pdf_path)
text = reader.pages[0].extract_text()

pos = text.lower().find('tecnoapp')
spett_pos = text.find('Spett')

print(f'Tecnoapp at: {pos}')
print(f'Spett at: {spett_pos}')
print(f'So Tecnoapp IS BEFORE Spett: {pos < spett_pos}')
print(f'\nFirst 1000 chars search should find it...')
print(f'Checking: Is 577 in range 0-1000? {pos >= 0 and pos <= 1000}')

# Show what extract_cliente_for_ordine should see
print(f'\n=== First 1000 chars (what our function searches) ===')
text_window = text[:1000]
print(f'Tecnoapp in first 1000? {"tecnoapp" in text_window.lower()}')
print(f'Lines around Tecnoapp:')
lines = text_window.split('\n')
for i, line in enumerate(lines):
    if 'tecnoapp' in line.lower():
        print(f'  Line {i}: {repr(line)}')

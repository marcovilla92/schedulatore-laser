#!/usr/bin/env python
"""Debug OF_260100 document structure"""

from PyPDF2 import PdfReader

pdf_path = 'C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf'
reader = PdfReader(pdf_path)
text = reader.pages[0].extract_text()

# Find Tecnoapp
pos = text.lower().find('tecnoapp')
print(f'Tecnoapp found at position: {pos}')
print(f'Text length: {len(text)}')

# Find where 'Spett' is
spett_pos = text.find('Spett')
print(f'Spett found at position: {spett_pos}')

# The header search looks for 'Spett' as end marker
print(f'\nSearch window is: 0 to {spett_pos}')
print(f'But Tecnoapp is at position {pos}')
print(f'Tecnoapp is AFTER "Spett" - it\'s in the FOOTER!')

print(f'\nFull text at Tecnoapp location:')
print(text[max(0, pos-100):pos+150])

print('\n\n=== KEY INSIGHT ===')
print('This PDF is different - cliente info is in the FOOTER (company letterhead)')
print('Not in the header before "Spett.le"!')
print('We need to search AFTER finding "Spett.le" instead of before')

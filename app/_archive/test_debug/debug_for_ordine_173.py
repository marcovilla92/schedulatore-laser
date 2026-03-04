#!/usr/bin/env python
"""Check FOR-ORDINE 0000173 structure"""

from PyPDF2 import PdfReader

pdf_path = 'C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000173_00(50359).pdf'
reader = PdfReader(pdf_path)
text = reader.pages[0].extract_text()

print(f'Text length: {len(text)}')
print(f'\n=== FULL TEXT ===')
print(text)

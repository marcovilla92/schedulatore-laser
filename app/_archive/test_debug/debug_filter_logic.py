#!/usr/bin/env python
from PyPDF2 import PdfReader

pdf_path = 'C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf'
reader = PdfReader(pdf_path)
text = reader.pages[0].extract_text()

header_end = text.find('Spett')
if header_end == -1:
    header_end = 1000
else:
    header_end = min(header_end, 1000)

header = text[:header_end]
lines = header.split('\n')

print(f'=== Checking line filtering logic ===\n')
for i, line in enumerate(lines):
    line_stripped = line.strip()
    if line_stripped and len(line_stripped) > 3:
        if 'Tecnoapp' in line_stripped or 'tecnoapp' in line_stripped.lower():
            print(f'Line {i}: {repr(line_stripped[:100])}...')
            print(f'  Length: {len(line_stripped)}')
            print(f'  Stripped: {line_stripped[:80]}')
            
            # Check each filter
            import re
            starts_with_skip = re.search(r'^(VIA|TEL|FAX|EMAIL|MAIL|HTTP|WWW|IBAN|BIC|REG|RAE|CAP|PAGINA|E-mail|P\.|I\.V)', line_stripped.upper())
            matches_skip = re.match(r'^(NR\.|CODICE|IMPORTO|NUMERO|DATA|PZ|QUANTITA|VOSTRO|VOSTRI|CONDIZIONI)', line_stripped.upper())
            has_keywords = any(kw in line_stripped.upper() for kw in ['S.R.L', 'SRL', 'S.P.A', 'SPA', 'TRADING', 'TECNOAPP', 'OFFICINE', 'INC', 'LLC', 'LTD', '&', 'UNIPERSONALE', 'TECNOAP'])
            passes_len_check = len(line_stripped) <= 100
            
            print(f'  Starts with skip keywords? {bool(starts_with_skip)}')
            print(f'  Matches skip pattern? {bool(matches_skip)}')
            print(f'  Has company keywords? {has_keywords}')
            print(f'  Length <= 100 check? {passes_len_check} (length is {len(line_stripped)})')
            
            would_return = (not starts_with_skip) and (not matches_skip) and (passes_len_check) and has_keywords
            print(f'  Would be RETURNED? {would_return}')
            print()

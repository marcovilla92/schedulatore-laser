#!/usr/bin/env python
from backend.pdf_parser import extract_pdf_content

result = extract_pdf_content('C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000173_00(50359).pdf')
print(f'Cliente: {result.get("cliente")}')
print(f'Ordine: {result.get("numero_ordine")}')  
print(f'Articoli: {len(result.get("articoli", []))}')

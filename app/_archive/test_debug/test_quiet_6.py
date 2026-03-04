#!/usr/bin/env python
"""Quick test of first 6 PDFs - no debug output"""

import sys
sys.path.insert(0, '.')

from backend import pdf_parser
import os

# Temporarily disable debug output in PDF parser
original_stdout = sys.stdout

pdfs = [
    ('C:/Users/39334/Documents/ORDINI/300000946.pdf', 'DIVISIONE'),
    ('C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000173_00(50359).pdf', 'FOR-ORDINE 173'),
    ('C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000205_00(50359).pdf', 'FOR-ORDINE 205'),
    ('C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000445_00(50359)[2].pdf', 'FOR-ORDINE 445'),
    ('C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000537_00(50359).pdf', 'FOR-ORDINE 537'),
    ('C:/Users/39334/Documents/ORDINI/OAFA202600125.pdf', 'OAFA'),
    ('C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf', 'OF_260100'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf', 'ORDINE 57-AC'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 83-AC del 09-02-2026  L S S R L.pdf', 'ORDINE 83-AC'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 85-AC del 10-02-2026  L S S R L.pdf', 'ORDINE 85-AC'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE FORNITORE 826-AC del 13-10-2025  L S S R L.pdf', 'ORDINE 826-AC'),
    ('C:/Users/39334/Documents/ORDINI/Ordine LS N°172.pdf', 'LS N°172'),
    ('C:/Users/39334/Documents/ORDINI/Ordine LS N°217.pdf', 'LS N°217'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE LS.PDF', 'ORDINE LS'),
    ('C:/Users/39334/Documents/ORDINI/ORDINE_D_ACQUISTO_21-28707_LS.pdf', 'ORDINE ACQ LS'),
    ('C:/Users/39334/Documents/ORDINI/PO_20250006705-3.pdf', 'PO'),
]

print("\n=== QUICK TEST RESULTS ===\n")

for pdf, shortname in pdfs:
    class NullWriter:
        def write(self, x): pass
        def flush(self): pass
    
    # Suppress debug output
    sys.stdout = NullWriter()
    
    try:
        result = pdf_parser.extract_pdf_content(pdf)
    except Exception as e:
        sys.stdout = original_stdout
        print(f"{shortname:25s} | ERROR: {str(e)[:40]}")
        continue
    
    sys.stdout = original_stdout
    
    cliente = result.get('cliente', '(empty)') or '(empty)'
    ordine = result.get('numero_ordine', '(empty)') or '(empty)'
    articoli = len(result.get('articoli', []))
    
    # Truncate cliente for display
    cliente_display = (cliente[:25] + '...') if len(cliente) > 25 else cliente
    ordine_display = (ordine[:10] + '...') if len(ordine) > 10 else ordine
    
    status = "OK" if (cliente and cliente != '(empty)' and ordine and ordine != '(empty)' and articoli >= 1) else "FAIL"
    
    print(f"[{status}] {shortname:25s} | Cliente: {cliente_display:28s} | Ordine: {ordine_display:13s} | Art: {articoli}")

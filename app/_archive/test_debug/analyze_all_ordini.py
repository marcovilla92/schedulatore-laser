#!/usr/bin/env python3
"""Analisi completa di tutti i PDF in ORDINI per pattern recognition"""
import PyPDF2
import re
from pathlib import Path

ORDINI_FOLDER = Path("C:/Users/39334/Documents/ORDINI")

print("=" * 120)
print("ANALISI PDF - Identificazione Patterns")
print("=" * 120)

pdfs = sorted(ORDINI_FOLDER.glob("*.pdf"))
print(f"\nTrovati {len(pdfs)} PDF\n")

# Estrai info da ogni PDF
for pdf_path in pdfs:
    print(f"\n{'='*120}")
    print(f"[PDF] {pdf_path.name}")
    print(f"{'='*120}")
    
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            num_pages = len(reader.pages)
            text = ""
            
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted
        
        text_upper = text.upper()
        
        # Analizza markers per tipo di documento
        is_oafa = "DECA" in text_upper and "Spett.le" in text
        is_for_ordine = "ORDINE FORNITORE" in text_upper
        is_divisione = "DIVISIONE CUCINE" in text_upper or "N. 300" in text_upper
        is_po_bebitalia = "B&B ITALIA" in text_upper and "ORDINE ACQUISTO" in text_upper
        is_ls = "L.S." in text_upper or "L S S R L" in text_upper or "Ordine LS" in pdf_path.name
        
        # Identifica il tipo
        tipo = "SCONOSCIUTO"
        if is_oafa:
            tipo = "OAFA"
        elif is_divisione:
            tipo = "DIVISIONE"
        elif is_po_bebitalia:
            tipo = "PO_BEBITALIA"
        elif is_for_ordine:
            tipo = "FOR_ORDINE"
        elif is_ls:
            tipo = "LS/GENERIC"
        
        print(f"  [Type] {tipo}")
        print(f"  [Pages] {num_pages}")
        print(f"  [Chars] {len(text)}")
        
        # Estrai clienti e ordini
        cliente_pattern = r"(?:Spett\.le|Cliente|Azienda|Company)[:\s]*([A-Z][^\n]*?)(?:\n|$)"
        cliente_match = re.search(cliente_pattern, text)
        cliente = cliente_match.group(1).strip()[:40] if cliente_match else "N/A"
        
        ordine_pattern = r"(?:A\d{6}|ordine\s+(?:n\.?|n°)?[\s:]*(\d+))"
        ordine_match = re.search(ordine_pattern, text_upper)
        ordine = ordine_match.group(1) if ordine_match else "N/A"
        
        # Estrai articoli (pattern universale)
        codice_pattern = r"(?:^|[\s|])([\w\-]{4,})\s+(?:[\d.]+|NR|nr|Qty)"
        articoli_count = len(re.findall(codice_pattern, text, re.MULTILINE)[:10])
        
        print(f"  [Client] {cliente}")
        print(f"  [Order] {ordine}")
        print(f"  [Articles] {articoli_count}")
        
        # Prime 200 caratteri
        print(f"  [Preview] {text[:200].replace(chr(10), ' ')}")
        
    except Exception as e:
        print(f"  [ERROR] {str(e)[:100]}")

print("\n" + "=" * 120)
print("[OK] Analysis completed")
print("=" * 120)

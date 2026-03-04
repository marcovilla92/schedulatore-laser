"""Parser per formato B&B Italia PO"""
import re
import sys
from datetime import datetime
from .parsers_markdown_tables import extract_articles_from_markdown_table

def extract_po_bebitalia(text: str, markdown_text: str = None, filepath: str = None) -> dict:
    """Parser specifico per formato B&B Italia PO"""
    return {
        'cliente': extract_cliente_bebitalia(text),
        'numero_ordine': extract_numero_ordine_bebitalia(text),
        'data_consegna': extract_data_consegna_bebitalia(text),
        'data_ricezione': extract_data_ricezione_bebitalia(text),
        'articoli': extract_articoli_bebitalia(text, markdown_text),
    }

def extract_cliente_bebitalia(text: str) -> str:
    """Estrae cliente B&B Italia"""
    if "B&B ITALIA" in text.upper():
        return "B&B ITALIA S.p.A."
    return ""

def extract_numero_ordine_bebitalia(text: str) -> str:
    """Estrae numero ordine formato: 20250006705-3"""
    matches = re.findall(r'(\d{11}[\-]\d+)', text)
    if matches:
        return matches[0]
    
    matches = re.findall(r'(\d{10,}[\-]\d+)', text)
    if matches:
        for m in matches:
            if not m.startswith('0'):
                return m
    
    return ""

def extract_data_consegna_bebitalia(text: str) -> str:
    """Estrae data consegna
    Nel PDF B&B Italia la data di consegna appare nella tabella degli articoli
    Esempio: ASSEMBLAGGIO ... PZ 10,00 111,3100 09/03/2026
    """
    # Cerca date nella tabella articoli (linee che contengono numeri decimali di prezzo + data)
    pattern = r'(\d+[.,]\d+)\s+(\d{2})[/\-](\d{2})[/\-](\d{4})\s*$'
    matches = re.findall(pattern, text, re.MULTILINE)
    
    if matches:
        # Prendi la prima data trovata nella tabella
        day, month, year = matches[0][1:]
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.isoformat()
        except ValueError:
            pass
    
    # Fallback: prendi la seconda data trovata nel documento
    all_dates = re.findall(r'(\d{2})[/\-](\d{2})[/\-](\d{4})', text)
    dates_found = []
    for day, month, year in all_dates:
        try:
            dt = datetime(int(year), int(month), int(day))
            if dt not in dates_found:
                dates_found.append(dt)
        except ValueError:
            pass
    
    if len(dates_found) >= 2:
        dates_found.sort()
        return dates_found[1].isoformat()
    elif dates_found:
        return dates_found[0].isoformat()
    
    return ""

def extract_data_ricezione_bebitalia(text: str) -> str:
    """Estrae data ricevimento documento"""
    match = re.search(r'DATA\s+DOCUMENTO[^0-9]*(\d{2})[/\-](\d{2})[/\-](\d{4})', text, re.IGNORECASE)
    if match:
        try:
            dt = datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)))
            return dt.isoformat()
        except ValueError:
            pass
    return ""

def extract_articoli_bebitalia(text: str, markdown_text: str = None) -> list:
    """Estrae articoli formato B&B Italia
    Primo tenta Markdown table parser, poi pattern matching
    """
    articoli = []
    
    # PRIMO TENTATIVO: Markdown table parser (se disponibile)
    if markdown_text:
        print(f"\n      [TABLE] PO_BEBITALIA: Tentando estrazione con Markdown Table Parser...")
        sys.stdout.flush()
        
        try:
            articoli = extract_articles_from_markdown_table(markdown_text)
            
            if articoli and len(articoli) >= 1:
                print(f"      [OK] Markdown parser trovato {len(articoli)} articoli")
                sys.stdout.flush()
                return articoli
        except Exception as e:
            print(f"      [WARNING] Markdown parser fallito: {e}, provo pattern matching...")
            sys.stdout.flush()
    
    # SECONDO TENTATIVO: Pattern matching (metodo originale)
    print(f"      [PDF] PO_BEBITALIA: Tentando estrazione con pattern matching...")
    sys.stdout.flush()
    
    articoli_codes = set()  # Per evitare duplicati
    
    # Pattern per articoli B&B Italia: Codice S + numeri, descrizione, U.M. (PZ o NR), quantità
    # Esempio: S99976389 ASSEMBLAGGIO - TF SEDILE INFER VER DIV2P DS217-203P DIE PZ 10,00
    # Esempio: S99976390 ASSEMBLAGGIO - TF SEDILE INFER VERN DIV 3P DS277 DIESIS NR 10,00
    pattern = r'(S\d+)\s+([^\n]*?)\s+(?:PZ|NR)\s+([\d,]+)'
    matches = re.findall(pattern, text)
    
    for code, desc, qty_str in matches:
        # Evita duplicati (il PDF può averli nelle pagine)
        if code in articoli_codes:
            continue
        articoli_codes.add(code)
        
        # Pulisci la descrizione da spazi extra
        desc = ' '.join(desc.split())[:150]
        
        # Converti quantità: rimpiazza virgola con punto e poi a int
        try:
            qty = int(float(qty_str.replace(',', '.')))
            articoli.append({
                'code': code,
                'name': desc,
                'qty': qty,
            })
        except ValueError:
            pass
    
    if articoli:
        print(f"      [OK] Pattern matching trovato {len(articoli)} articoli")
        sys.stdout.flush()
    
    return articoli

"""Parser per formato DIVISIONE CUCINE"""
import re
import sys
from datetime import datetime
from .parsers_markdown_tables import extract_articles_from_markdown_table

def extract_divisione(text: str, markdown_text: str = None, filepath: str = None) -> dict:
    """Parser specifico per formato DIVISIONE CUCINE (300000946)"""
    return {
        'cliente': extract_cliente_divisione(text),
        'numero_ordine': extract_numero_ordine_divisione(text),
        'data_consegna': extract_data_consegna_divisione(text),
        'data_ricezione': extract_data_ricezione_divisione(text),
        'articoli': extract_articoli_divisione(text, markdown_text),
    }

def extract_cliente_divisione(text: str) -> str:
    """Estrae cliente dall'intestazione DIVISIONE CUCINE (non da Spett.le!)"""
    # Cerca "DIVISIONE CUCINE" nell'intestazione (primi 500 caratteri)
    header = text[:500]
    match = re.search(r'(DIVISIONE\s+CUCINE)', header, re.IGNORECASE)
    if match:
        return 'DIVISIONE CUCINE'
    return ""

def extract_numero_ordine_divisione(text: str) -> str:
    """Estrae numero ordine formato: 300000946"""
    match = re.search(r'N\.\s*(\d{3}\s*\d{3}\s*\d{3})', text, re.IGNORECASE)
    if match:
        return match.group(1).replace(' ', '')
    return ""

def extract_data_consegna_divisione(text: str) -> str:
    """Estrae data consegna richiesta
    Nel PDF DIVISIONE la riga con "Consegna richiesta" ha due date:
    - Prima data: 03/02/2026 (ricezione)
    - Seconda data: 03/04/2026 (consegna richiesta)
    """
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if 'CONSEGNA RICHIESTA' in line.upper() or 'DELIVERY DATE' in line.upper():
            # La riga con le date è la prossima
            if i + 1 < len(lines):
                date_line = lines[i + 1]
                # Cerca tutte le date nella riga
                dates = re.findall(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', date_line)
                if len(dates) >= 2:
                    # Prendi la seconda data
                    date_tuple = dates[1]
                    return normalize_date(f"{date_tuple[0]}/{date_tuple[1]}/{date_tuple[2]}")
                elif len(dates) == 1:
                    return normalize_date(f"{dates[0][0]}/{dates[0][1]}/{dates[0][2]}")
    
    return extract_data_consegna_generic(text)

def extract_data_ricezione_divisione(text: str) -> str:
    """Estrae data ricevimento (Data / Date nel header)"""
    # Pattern: "Data / Date" o "Date / Date" seguito da data
    pattern = r'(?:Data\s*/\s*Date|Date\s*/\s*Date)\s+(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return normalize_date(f"{match.group(1)}/{match.group(2)}/{match.group(3)}")
    
    return datetime.now().isoformat()

def extract_articoli_divisione(text: str, markdown_text: str = None) -> list:
    """Estrae articoli formato DIVISIONE
    Primo tenta Markdown table parser, poi pattern matching
    """
    articoli = []
    
    # PRIMO TENTATIVO: Markdown table parser (se disponibile)
    if markdown_text:
        print(f"\n      [TABLE] DIVISIONE: Tentando estrazione con Markdown Table Parser...")
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
    print(f"      [PDF] DIVISIONE: Tentando estrazione con pattern matching...")
    sys.stdout.flush()
    
    # Pattern per articoli DIVISIONE:
    # Pos Codice ---- NR Quantità DESCRIZIONE
    # Esempio: 305AVAR1380---- NR 500REGGIMENSOLA VERNICIATO GRIGIO
    pattern = r'^\d+([A-Z0-9]{10,})-{4,}\s+NR\s+(\d+)(.*)$'
    
    for line in text.split('\n'):
        line = line.strip()
        match = re.search(pattern, line)
        
        if match:
            codice = match.group(1)
            qty_str = match.group(2)
            desc = match.group(3).strip()
            
            try:
                qty = int(qty_str)
                articoli.append({
                    'code': codice,
                    'name': desc[:150] if desc else '',
                    'qty': qty,
                })
            except ValueError:
                pass
    
    if articoli:
        print(f"      [OK] Pattern matching trovato {len(articoli)} articoli")
        sys.stdout.flush()
    
    return articoli

def extract_data_consegna_generic(text: str) -> str:
    """Estrae data da testo generico"""
    date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', text)
    if date_match:
        return normalize_date(f"{date_match.group(1)}/{date_match.group(2)}/{date_match.group(3)}")
    return datetime.now().isoformat()

def normalize_date(date_str: str) -> str:
    """Normalizza la data nel formato ISO"""
    try:
        parts = date_str.split('/')
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        
        if year < 100:
            year += 2000
        
        dt = datetime(year, month, day)
        return dt.isoformat()
    except:
        return datetime.now().isoformat()

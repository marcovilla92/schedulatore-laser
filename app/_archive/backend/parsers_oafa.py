"""Parser per formato OAFA"""
import re
import PyPDF2
import sys
from datetime import datetime
from io import BytesIO
from .parsers_markdown_tables import extract_articles_from_markdown_table

def extract_oafa(text: str, filepath: str = None, markdown_text: str = None) -> dict:
    """Parser specifico per formato OAFA - usa Markdown tables come primo metodo"""
    data = {
        'cliente': extract_cliente_oafa(text),
        'numero_ordine': extract_numero_ordine_oafa(text),
        'data_consegna': extract_data_consegna_oafa(text),
        'data_ricezione': extract_data_ricezione_oafa(text),
        'articoli': extract_articoli_oafa(text, filepath, markdown_text),
    }
    return data

def extract_cliente_oafa(text: str) -> str:
    """Cliente per OAFA è sempre DECA S.r.l."""
    if "DECA" in text.upper():
        # Cerca il nome completo dell'azienda
        match = re.search(r'DECA\s+S\.?r\.?l\.?', text, re.IGNORECASE)
        if match:
            return match.group(0)
        return "DECA S.r.l."
    return ""

def extract_numero_ordine_oafa(text: str) -> str:
    """Estrae numero ordine formato: A000125"""
    match = re.search(r'A[\s]*(\d{3,})', text)
    if match:
        return f"A{match.group(1)}"
    return ""

def extract_data_consegna_oafa(text: str) -> str:
    """Estrae data consegna dalla tabella articoli (es: 18/02/26)"""
    # Cerca la data nella sezione articoli (non subito dopo numero ordine)
    # Nel PDF appare dopo ogni descrizione articolo
    lines = text.split('\n')
    
    # Cerca linee che hanno solo una data (formato gg/mm/yy o gg/mm/yyyy)
    found_first_article = False
    for i, line in enumerate(lines):
        # Salta fino a dove iniziano gli articoli
        if re.match(r'^\d{2}[A-Z]{2,}[A-Z0-9\-]+$', line.strip()):
            found_first_article = True
            # Una volta trovato il primo articolo, cerca la data
            if i+2 < len(lines):
                # Dopo codice, descrizione, c'è la data
                for j in range(i+1, min(i+5, len(lines))):
                    date_match = re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*$', lines[j].strip())
                    if date_match:
                        date_text = lines[j].strip()
                        parts = re.split(r'[/-]', date_text)
                        if len(parts) >= 3:
                            return normalize_date(f"{parts[0]}/{parts[1]}/{parts[2]}")
            break
    
    # Fallback: cerca altre date dopo la prima (escludendo la data ricezione all'inizio)
    date_matches = re.findall(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', text)
    if len(date_matches) >= 2:
        # Prendi la seconda data (prima era ricezione)
        day, month, year = date_matches[1]
        return normalize_date(f"{day}/{month}/{year}")
    
    return datetime.now().isoformat()

def extract_data_ricezione_oafa(text: str) -> str:
    """Estrae data ricevimento documento (prima riga con data)"""
    lines = text.split('\n')
    for line in lines:
        if any(x in line for x in ['Data', 'data', 'Documento', 'documento']):
            date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', line)
            if date_match:
                return normalize_date(f"{date_match.group(1)}/{date_match.group(2)}/{date_match.group(3)}")
    
    # Fallback: prima data nel documento
    dates_full = re.findall(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
    if dates_full:
        day, month, year = dates_full[0]
        return normalize_date(f"{day}/{month}/{year}")
    
    return datetime.now().isoformat()

def extract_articoli_oafa(text: str, filepath: str = None, markdown_text: str = None) -> list:
    """Estrae articoli OAFA - PRIMO usa PyPDF2 direttamente, poi fallback a Markdown"""
    import sys
    articoli = []
    
    # PRIMO TENTATIVO diretto con PyPDF2 (più affidabile di Docling per OAFA)
    print(f"\n      PDF OAFA: Tentando estrazione diretta con PyPDF2...")
    sys.stdout.flush()
    
    # Se abbiamo il filepath, usa PyPDF2 per testo pulito e strutturato
    pypdf_text = None
    if filepath:
        try:
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                pypdf_text = ''
                for page in reader.pages:
                    pypdf_text += page.extract_text() + '\n'
        except Exception as e:
            pypdf_text = None
    
    # Usa PyPDF2 text se disponibile
    extract_text = pypdf_text if pypdf_text else text
    
    # PARSING STRUTTURATO: processa riga per riga
    lines = extract_text.split('\n')
    
    # Prima passa: trova TUTTI i codici articolo
    # Pattern: numeri (2-3 cifre) + lettere + numeri/trattini (es: 13R025108, 12A402101-00, 12B200103-01)
    codici_trovati = []
    for i, line in enumerate(lines):
        # Cerca codici formato: 2-3 cifre + 1-2 lettere + cifre/trattini
        if re.match(r'^\d{2,3}[A-Z]{1,2}[A-Z0-9\-]{3,10}$', line.strip()):
            codici_trovati.append((i, line.strip()))
    
    print(f"      OK PyPDF2 found {len(codici_trovati)} articles")
    sys.stdout.flush()
    
    if len(codici_trovati) >= 5:  # Se PyPDF2 ha trovato abbastanza articoli, usali
        # Seconda passa: estrai dati per ogni codice
        for article_idx, (start_line, codice) in enumerate(codici_trovati):
            # Determina dove finisce questo articolo (prossimo codice o fine)
            if article_idx + 1 < len(codici_trovati):
                end_line = codici_trovati[article_idx + 1][0]
            else:
                end_line = len(lines)
            
            # Estrai linee di questo articolo
            articolo_lines = lines[start_line:end_line]
            
            # Cerca QUANTITA (pattern: "X,XX" o "X.XX" su linea sola)
            qty = None
            qty_line_idx = None
            
            for j, line in enumerate(articolo_lines):
                qty_match = re.match(r'^(\d+[.,]\d+)$', line.strip())
                if qty_match:
                    qty = float(qty_match.group(1).replace(',', '.'))
                    qty_line_idx = j
                    break
            
            if qty is None:
                continue
            
            # Descrizione: tra riga 1 (skip codice+commessa) e qty
            desc_lines = []
            for j in range(1, qty_line_idx):  # Include anche riga commessa potrebbe avere info utili
                line_text = articolo_lines[j].strip()
                # Skip linee vuote e pipes
                if line_text and '|' not in line_text:
                    desc_lines.append(line_text)

            # Unisci linee e ripulisci
            descrizione = ' '.join(desc_lines)[:300]

            # Se la descrizione è TROPPO corta o solo numeri/simboli, salta
            # Ma accetta descrizioni con "Piastra", "Nervatura", etc anche se hanno specifiche materiale
            if (not descrizione or len(descrizione) < 5 or
                (re.match(r'^[\d\s\(\)\.]+$', descrizione) and
                 not any(word in descrizione.upper() for word in ['PIASTRA', 'NERVATURA', 'ORDINE']))):
                continue
            
            articoli.append({
                'code': codice,
                'name': descrizione,
                'qty': int(qty) if qty == int(qty) else qty,
            })
        
        if articoli:
            print(f"      OK PyPDF2 parsing successful: {len(articoli)} articles")
            sys.stdout.flush()
            return articoli
    
    # FALLBACK: Se PyPDF2 non ha trovato abbastanza, prova Markdown parser
    if markdown_text:
        print(f"      INFO Fallback to Markdown Table Parser...")
        sys.stdout.flush()
        
        try:
            articoli = extract_articles_from_markdown_table(markdown_text)
            
            if articoli and len(articoli) >= 1:
                print(f"      [OK] Markdown parser trovato {len(articoli)} articoli")
                sys.stdout.flush()
                return articoli
        except Exception as e:
            print(f"      [WARNING] Markdown parser fallito: {e}")
            sys.stdout.flush()
    
    print(f"      [WARNING] Nessun articolo estratto")
    sys.stdout.flush()
    return articoli

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

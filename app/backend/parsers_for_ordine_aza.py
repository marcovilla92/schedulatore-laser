"""Parser per formato ORDINE FORNITORE AZA (variante 57-AC, 83-AC, 85-AC, 826-AC)"""
import re
import sys
from datetime import datetime

def extract_for_ordine_aza(text: str, markdown_text: str = None, filepath: str = None) -> dict:
    """Parser specifico per ORDINE FORNITORE AZA (formato diverso dal standard FOR_ORDINE)
    
    Formato:
    - Cliente dopo "n." linea: "n.LS S.R.L."
    - Ordine dopo "ORDINE FORNITORE": "57/AC del 30/01/2026"
    - Articoli: "NR 100,00 € 716,80 € 7,1680 SPORTELLO DOS. LINEARE 0582DOS1SN"
    """
    return {
        'cliente': extract_cliente_aza(text),
        'numero_ordine': extract_numero_ordine_aza(text),
        'data_consegna': extract_data_consegna_aza(text),
        'data_ricezione': extract_data_ricezione_aza(text),
        'articoli': extract_articoli_aza(text, markdown_text),
    }

def extract_cliente_aza(text: str) -> str:
    """Estrae cliente AZA INTERNATIONAL dall'intestazione (non da 'n.LS')"""
    # Cercaintestazione per "AZA INTERNATIONAL"
    match = re.search(r'(AZA\s+INTERNATIONAL[^\n]{0,40})', text[:600])
    if match:
        return match.group(1).strip()
    return ""



def extract_numero_ordine_aza(text: str) -> str:
    """Estrae numero ordine dal pattern 'XXXX/AC del DATE'"""
    # Cerca il pattern: numero/AC oppure numero-AC
    match = re.search(r'(\d+)(?:/|-)?AC\s+del', text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Fallback: cerca numero con "/AC"
    match = re.search(r'(\d+)/AC', text)
    if match:
        return match.group(1)
    
    return ""

def extract_data_consegna_aza(text: str) -> str:
    """Estrae data consegna da linea 'DATA CONSEGNA'"""
    # Cerca dopo  "DATA CONSEGNA/DESPATCH:"
    match = re.search(r'DATA\s+CONSEGNA.*?(\d{2})/(\d{2})/(\d{4})', text, re.IGNORECASE | re.DOTALL)
    if match:
        day, month, year = match.group(1), match.group(2), match.group(3)
        return normalize_date(f"{day}/{month}/{year}")
    
    return datetime.now().isoformat()

def extract_data_ricezione_aza(text: str) -> str:
    """Estrae data ricevimento da linea con data nel documento"""
    # Cerca prima data nel documento
    match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if match:
        day, month, year = match.group(1), match.group(2), match.group(3)
        return normalize_date(f"{day}/{month}/{year}")
    
    return datetime.now().isoformat()

def extract_articoli_aza(text: str, markdown_text: str = None) -> list:
    """Estrae articoli da formato AZA
    
    Formato:
    NR 100,00 € 716,80 € 7,1680 SPORTELLO DOS. LINEARE 0582DOS1SN
    
    Dove:
    - NR = unità (sempre "NR" per numero)
    - 100,00 = quantità
    - € 716,80 = prezzo totale (non usato)
    - € 7,1680 = prezzo unitario (non usato)
    - SPORTELLO DOS. LINEARE = descrizione
    - 0582DOS1SN = codice articolo
    """
    articoli = []
    
    print(f"\n      PDF FOR_ORDINE_AZA: Tentando estrazione con pattern matching...")
    sys.stdout.flush()
    
    # Pattern per linea articolo AZA:
    # Cercare linee che iniziano con "NR " per identificare articoli
    
    for line in text.split('\n'):
        line = line.strip()
        if not line.startswith('NR') or len(line) < 30:
            continue
        
        # Formato: NR 100,00 € 716,80 € 7,1680 SPORTELLO DOS. LINEARE 0582DOS1SN
        # Estrai da destra: codice (ultima sequenza alphanumerica senza spazi)
        # Poi: descrizione (testo prima del codice)
        # Quindi: quantità (numero dopo NR)
        
        parts = line.split()
        if len(parts) < 8:
            continue
        
        try:
            # Quantità è sempre al secondo token (dopo NR)
            qty_str = parts[1].replace(',', '.')
            qty = int(float(qty_str))
            
            # Codice è l'ultimo token con lettere e numeri
            code = None
            code_idx = -1
            for i in range(len(parts) - 1, 3, -1):
                if re.match(r'^[A-Z0-9]+$', parts[i]) and len(parts[i]) >= 4:
                    code = parts[i]
                    code_idx = i
                    break
            
            if code and code_idx > 4:  # Deve esserci spazio tra il prezzo e il codice
                # Descrizione: tutto tra i prezzi € e il codice
                # Indice 3 dovrebbe essere un € dopo il prezzo iniziale
                # Indice 4 dovrebbe ripartire la descrizione
                desc_parts = parts[4:code_idx]
                desc = ' '.join(desc_parts) if desc_parts else ''

                # Rimuovi simboli € dalla descrizione
                desc = desc.replace('€', '').replace('Ç', '').strip()

                # Rimuovi numeri di prezzo (pattern: numero,numero o numero.numero preceduto da spazio)
                desc = re.sub(r'\s*\d+[.,]\d+\s*', ' ', desc).strip()

                if 0 < qty <= 10000 and code and desc:
                    articoli.append({
                        'code': code,
                        'name': desc[:150],
                        'qty': qty,
                    })
        except (ValueError, IndexError):
            pass
    
    if articoli:
        print(f"      OK Pattern matching found {len(articoli)} articles")
        sys.stdout.flush()
    else:
        print(f"      [WARNING] Nessun articolo estratto (AZA pattern)")
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

"""
Parser Generico Intelligente - Basato su Docling
Estrae dati da qualsiasi formato di ordine PDF
"""
import re
import sys
from datetime import datetime
from typing import Dict, List, Any
from .parsers_markdown_tables import extract_articles_from_markdown_table


def extract_generic_intelligent(text: str, markdown_text: str = None) -> Dict[str, Any]:
    """
    Parser intelligente che funziona con qualsiasi formato di PDF
    Primo tenta estrazione da Markdown table, poi pattern matching
    """
    print("\n   [PARSER] PARSER GENERICO INTELLIGENTE")
    print("   " + "="*70)
    print(f"\n   [DATA] TESTO RICEVUTO (primi 1500 caratteri):")
    print("   " + "-"*70)
    print(text[:1500])
    print("   " + "-"*70)
    print(f"\n   [DATA] TESTO COMPLETO ({len(text)} caratteri):")
    print("   " + "-"*70)
    print(text)
    print("   " + "-"*70)
    sys.stdout.flush()
    
    data = {
        'cliente': '',
        'numero_ordine': '',
        'data_consegna': datetime.now().isoformat(),
        'data_ricezione': datetime.now().isoformat(),
        'articoli': [],
    }
    
    # ESTRAI CLIENTE
    print("   [1] Ricerca CLIENTE...")
    sys.stdout.flush()
    cliente = _extract_cliente(text)
    if cliente:
        data['cliente'] = cliente
        print(f"      [OK] Cliente trovato: {cliente}")
    else:
        print(f"      [WARNING] Cliente non trovato")
    sys.stdout.flush()
    
    # ESTRAI NUMERO ORDINE
    print("   [2] Ricerca NUMERO ORDINE...")
    sys.stdout.flush()
    numero_ordine = _extract_numero_ordine(text)
    if numero_ordine:
        data['numero_ordine'] = numero_ordine
        print(f"      [OK] Ordine trovato: {numero_ordine}")
    else:
        print(f"      [WARNING] Ordine non trovato")
    sys.stdout.flush()
    
    # ESTRAI DATA CONSEGNA
    print("   [3] Ricerca DATA CONSEGNA...")
    sys.stdout.flush()
    data_consegna = _extract_data_consegna(text)
    if data_consegna:
        data['data_consegna'] = data_consegna
        print(f"      [OK] Data trovata: {data_consegna}")
    else:
        print(f"      [WARNING] Data non trovata")
    sys.stdout.flush()
    
    # ESTRAI ARTICOLI DA TABELLA
    print("   [4] Ricerca ARTICOLI...")
    sys.stdout.flush()
    
    # PRIMO TENTATIVO: Pattern matching su testo raw (veloce)
    print("      [PDF] Tentando estrazione con pattern matching...")
    sys.stdout.flush()
    articoli = _extract_articoli_from_table(text)
    
    # FALLBACK: Se pattern ha fallito, prova Markdown parser
    if not articoli and markdown_text:
        print("      [TABLE] Fallback su Markdown Table Parser...")
        sys.stdout.flush()
        
        try:
            articoli = extract_articles_from_markdown_table(markdown_text)
            
            if articoli and len(articoli) >= 1:
                print(f"      [OK] Markdown parser trovato {len(articoli)} articoli")
                sys.stdout.flush()
        except Exception as e:
            print(f"      [WARNING] Markdown parser fallito: {e}")
            sys.stdout.flush()
            articoli = []
    
    if articoli:
        data['articoli'] = articoli
        print(f"      [OK] Articoli trovati: {len(articoli)}")
        for i, art in enumerate(articoli, 1):
            print(f"         {i}. {art.get('name', 'N/A')} - {art.get('qty', 0)} pz")
    else:
        print(f"      [WARNING] Nessun articolo trovato")
    sys.stdout.flush()
    
    print("   " + "="*70)
    sys.stdout.flush()
    return data


def _extract_cliente(text: str) -> str:
    """Estrae il nome del cliente (MITTENTE/SUPPLIER, NON LS che è il destinatario)"""
    print(f"      Cerco cliente...")
    sys.stdout.flush()

    # PRIMA OPZIONE: Cerca header Markdown "## AZIENDA" (mittente)
    header_match = re.search(r'^#+\s+([A-Za-z0-9\s\.]+?)(?:\s+-|\n)', text, re.MULTILINE)
    if header_match:
        cliente = header_match.group(1).strip()
        if cliente and len(cliente) > 3 and 'ORDINE' not in cliente.upper():
            return cliente

    # SECONDA OPZIONE: Cerca "Cordiali saluti CLIENTE" o "Consegna presso CLIENTE"
    cordiali_match = re.search(r'Cordiali\s+saluti\s+([A-Za-z0-9\s\.]+?)(?:\n|$)', text, re.IGNORECASE)
    if cordiali_match:
        cliente = cordiali_match.group(1).strip()
        if 'LS' not in cliente.upper():
            return cliente

    consegna_match = re.search(r'Consegna\s+presso\s+([A-Za-z0-9\s\.]+?)(?:\n|$)', text, re.IGNORECASE)
    if consegna_match:
        cliente = consegna_match.group(1).strip()
        if 'LS' not in cliente.upper():
            return cliente

    # TERZA OPZIONE: Cerca "Spettabile CLIENTE" ma ESCLUDE LS (che è il destinatario)
    spett_match = re.search(r'Spettabile\s+([A-Za-z0-9\s\.]+?)(?:\n|$|VIA|Via|via)', text, re.IGNORECASE)
    if spett_match:
        cliente = spett_match.group(1).strip()
        if not cliente.upper().startswith('LS'):
            return cliente

    # RICERCA FINALE nei pattern di testo libero - escludendo LS
    lines = text.split('\n')
    for line in lines[:30]:
        line_clean = line.strip()
        if line_clean and not re.match(r'^[\s#|-]*$', line_clean):
            if any(x in line_clean.upper() for x in ['S.R.L', 'SRL', 'S.P.A', 'SPA', 'S.A.S', 'SAS']):
                cleaned = line_clean.split('|')[0].split('-')[0].strip()
                if not cleaned.upper().startswith('LS') and cleaned and len(cleaned) > 3:
                    return cleaned

            if not any(x in line_clean.upper() for x in ['ORDINE', 'DATA', 'TELEFONO', 'FAX', 'NOTE', 'CONSEGNA', 'VIA', 'CIVATE', 'PAGINA', 'DESPATCH']):
                if len(line_clean) > 5 and len(line_clean.split()) >= 2:
                    cleaned = line_clean.split('|')[0].split('-')[0].strip()
                    if not cleaned.upper().startswith('LS') and cleaned and len(cleaned) > 3:
                        return cleaned

    return ""


def _extract_numero_ordine(text: str) -> str:
    """Estrae il numero dell'ordine"""
    print(f"      Cerco numero ordine...")
    sys.stdout.flush()
    
    # Cerca "Ordine n. XXX" o "Ordine n° XXX" o "Order #XXX" o "57/AC"
    patterns = [
        r'(?:##\s*)?ORDINE\s+FORNITORE\s*\n?\s*(\d+/[A-Z]+)',  # Formato "ORDINE FORNITORE 57/AC"
        r'(\d+/[A-Z]+)\s*n\.?',  # Standalone "57/AC n."
        r'[Oo]rdine\s+[\w\.]*\s*(\d+/[A-Z]+)',  # Formato "57/AC"
        r'[Oo]rdine\s+(?:n\.?|n°|#)\s*(\d+)',
        r'[Oo]rder\s*#\s*(\d+)',
        r'[Ff]ornitore\s+(\d+/[A-Z]+)',  # Per "ORDINE FORNITORE"
        r'[Oo]rdine\s+[\d\s]*(\d{3,})',  # Variante più loose
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
        if match:
            numero = match.group(1).strip()
            print(f"         → Trovato ordine: {numero}")
            sys.stdout.flush()
            return numero
    
    print(f"         → Ordine NON trovato")
    sys.stdout.flush()
    return ""


def _extract_data_consegna(text: str) -> str:
    """Estrae la data di consegna"""
    print(f"      Cerco data consegna...")
    
    # Cerca "Data di consegna:", "DATA CONSEGNA/DESPATCH:", "Delivery date:"
    # IMPORTANTE: La DATA CONSEGNA/DESPATCH ha priorità sulle altre date
    patterns = [
        # Priorità 1: DATA CONSEGNA/DESPATCH: (permissive with whitespace/newlines)
        r'[Dd]ata\s+(?:di\s+)?consegna.*?despatch\s*:?\s*[\n\s]*(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
        # Priorità 2: Solo DESPATCH (bilingual)
        r'[Dd]espatch\s*:?\s*[\n\s]*(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
        # Priorità 3: Data consegna standard
        r'[Dd]ata\s+di\s+consegna\s*:?\s*[\n\s]*(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
        r'[Dd]ata\s+consegna\s*:?\s*[\n\s]*(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                groups = match.groups()
                day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                # Converte in datetime ISO format
                dt = datetime(year, month, day)
                print(f"         → Trovata data: {day}/{month}/{year}")
                return dt.isoformat()
            except (ValueError, IndexError) as e:
                print(f"         → Errore parsing data: {e}")
                continue
    
    print(f"         → Data NON trovata")
    return datetime.now().isoformat()


def _extract_articoli_from_table(text: str) -> List[Dict[str, Any]]:
    """
    Estrae articoli da tabelle Markdown (formato Docling)
    o da strutture testo libero
    """
    print(f"      Cerco articoli...")
    sys.stdout.flush()
    
    articoli = []
    
    # Prova a estrarre da tabelle Markdown (formato Docling)
    # Split per righe e processa
    lines = text.split('\n')
    
    # Trova l'inizio della tabella articoli (riga con "Codice" o "Articolo")
    # Cerca specificamente "Codice articolo" o "Codice Articolo" nella riga
    articoli_start = -1
    for i, line in enumerate(lines):
        if ('Codice' in line or 'Quantità' in line) and 'articolo' in line.lower():
            articoli_start = i
            print(f"         → Trovata intestazione tabella articoli alla riga {i}")
            sys.stdout.flush()
            break
    
    if articoli_start >= 0:
        # Processa le righe DOPO l'intestazione
        # Salta header row e il separatore (----|---)
        for line in lines[articoli_start + 2:]:
            line = line.strip()
            
            # Salta righe vuote o separatori
            if not line or re.match(r'^[\s\-|=]*$', line):
                continue
            
            # Salta righe che contengono parole chiave
            if any(x in line.upper() for x in ['SOMMA', 'TOTALE', 'IVA', 'PAGAMENTO', 'CONSEGNA', 'CORDIALI']):
                break  # Fine della tabella
            
            # Estrai i campi (divisi da |)
            fields = [f.strip() for f in line.split('|')]
            
            # Filtra campi vuoti
            fields = [f for f in fields if f]
            
            # Articolo valido: almeno 3 campi (CODICE | DESCRIZIONE | ... | QUANTITÀ)
            if len(fields) >= 3:
                # Primo campo = Codice articolo
                code = fields[0]
                # Secondo campo = Descrizione
                description = fields[1]
                
                # Cerca quantità - preferisci NUMERI INTERI (10) ai decimali (47.19)
                # La quantità è tipicamente la prima colonna numerica dopo la descrizione
                quantity = 0
                
                # Esamina i campi dal 3º in poi (dopo codice e descrizione)
                for field in fields[2:]:
                    # Cerca prima un numero INTERO (quantità tipica)
                    int_match = re.search(r'\b(\d+)\b', field)
                    if int_match:
                        quantity = float(int_match.group(1))
                        break
                    # Se non trova intero, cerca decimale (fallback per prezzo)
                    dec_match = re.search(r'(\d+[.,]\d+)', field)
                    if dec_match:
                        quantity = float(dec_match.group(1).replace(',', '.'))
                        break
                
                # Accetta solo se:
                # - Ha un codice non numerico puro (es TFTAUT1, MD031000, ma non 20 o 341)
                # - Ha una descrizione con testo
                # - Ha una quantità > 0
                if (quantity > 0 and 
                    len(description) > 3 and 
                    not re.match(r'^\d+$', code) and  # Non è un numero puro
                    not code.replace(',', '').replace('.', '').isdigit()):  # Non è una data
                    
                    articoli.append({
                        'name': description,
                        'code': code,
                        'qty': quantity,
                    })
                    print(f"         → Articolo trovato: {code} | {description} | Qty: {quantity}")
                    sys.stdout.flush()
    
    else:
        # Fallback: cerca almeno righe che assomigliano ad articoli
        print(f"         → Intestazione tabella non trovata, cerco articoli con pattern generico")
        sys.stdout.flush()
        
        # Cerca pattern: CODICE(senza spazi) | TESTO | ... | NUMERO
        table_pattern = r'\|([A-Z0-9]{2,})\s*\|\s*([A-Za-z\s]+?)\s*\|.*?(\d+(?:[.,]\d+)?)\s*\|'
        matches = re.finditer(table_pattern, text)
        
        for match in matches:
            code = match.group(1).strip()
            description = match.group(2).strip()
            quantity = float(match.group(3).replace(',', '.'))
            
            # Filtra
            if (quantity > 0 and
                len(description) > 3 and
                len(code) > 1):
                
                articoli.append({
                    'name': description,
                    'code': code,
                    'qty': quantity,
                })
                print(f"         → Articolo trovato (pattern): {code} | {description} | Qty: {quantity}")
                sys.stdout.flush()
    
    if not articoli:
        print(f"         → Nessun articolo valido trovato")
    
    sys.stdout.flush()
    return articoli

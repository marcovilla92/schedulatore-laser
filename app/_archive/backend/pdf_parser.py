"""PDF Parser - Dispatcher multi-formato con Docling"""
import PyPDF2
import re
import sys
from datetime import datetime
from .parsers_oafa import extract_oafa
from .parsers_for_ordine import extract_for_ordine
from .parsers_divisione import extract_divisione
from .parsers_po_bebitalia import extract_po_bebitalia
from .parsers_for_ordine_aza import extract_for_ordine_aza
from .parsers_ordine_ls import extract_ordine_ls
from .parsers_generic import extract_generic_intelligent
from .parsers_markdown_tables import extract_articles_from_markdown_table

# Docling sarà caricato in lazy loading (solo quando serve)
DOCLING_AVAILABLE = None  # None = non ancora testato, True/False = testato
DOCLING_CONVERTER = None


def _ensure_docling_loaded():
    """Carica Docling in lazy loading (solo al primo utilizzo) - DISABLED FOR TESTING"""
    global DOCLING_AVAILABLE, DOCLING_CONVERTER
    
    if DOCLING_AVAILABLE is not None:
        return DOCLING_AVAILABLE  # Già testato
    
    # TEMPORARILY DISABLED FOR TESTING
    DOCLING_AVAILABLE = False
    return False


def extract_text_with_docling(filepath: str) -> str:
    """Estrae testo da PDF usando Docling (migliore qualità)"""
    try:
        # Carica Docling in lazy loading se non è ancora caricato
        if not _ensure_docling_loaded():
            print(f"[PDF] Docling non disponibile per {filepath}")
            return None
        
        print(f"[PDF] Parsing con Docling: {filepath}")
        sys.stdout.flush()
        
        global DOCLING_CONVERTER
        print(f"   > Converter inizializzato, inizio conversione...")
        sys.stdout.flush()
        
        doc_result = DOCLING_CONVERTER.convert(filepath)
        
        # Estrae il testo dal documento
        print(f"   > Conversione completata, estrazione testo...")
        sys.stdout.flush()
        
        text = doc_result.document.export_to_markdown()
        
        if text:
            print(f"   [OK] Docling estratto {len(text)} caratteri")
            sys.stdout.flush()
        else:
            print(f"   [WARNING] Docling ha estratto testo vuoto")
            sys.stdout.flush()
            
        return text if text else None
        
    except Exception as e:
        print(f"[ERROR] Errore Docling ({filepath}): {str(e)}")
        print(f"   > Ricade su PyPDF2...")
        sys.stdout.flush()
        return None


def extract_cliente_with_docling_fallback(filepath: str) -> str:
    """Estrae cliente dal logo usando Docling - solo come fallback"""
    try:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.base_models import ConversionStatus
        
        print(f"      [PDF] Tentando estrazione cliente con Docling (OCR logo)...")
        sys.stdout.flush()
        
        converter = DocumentConverter()
        doc_result = converter.convert(filepath)
        
        if doc_result.status != ConversionStatus.SUCCESS:
            print(f"      [WARNING] Docling conversion failed")
            return ""
        
        # Estrai testo markdown e cerca il primo nome di azienda
        text = doc_result.document.export_to_markdown()[:800]
        
        # Cerca il primo nome significativo (stringhe uppercase che non sono indirizzi)
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line) > 3 and len(line) < 100:
                # Skip linee che sono indirizzi, numeri, etc
                if re.search(r'^(VIA|TEL|FAX|EMAIL|MAIL|PAGE|N\.|DATA|NUMERO|CODICE)', line.upper()):
                    continue
                # Trovato il nome!
                if any(c.isupper() for c in line) and 'S.r.l' in line or 'SpA' in line or 'S.p.A' in line:
                    print(f"      [OK] Docling found cliente: {line[:60]}")
                    sys.stdout.flush()
                    return line
        
        return ""
        
    except ImportError:
        print(f"      [WARNING] Docling non installato, skip OCR")
        return ""
    except Exception as e:
        print(f"      [WARNING] Docling error: {str(e)[:50]}")
        return ""


def extract_pdf_content(filepath: str) -> dict:
    """
    Estrae dati dal PDF riconoscendo automaticamente il formato
    Supporta: OAFA, FOR-ORDINE, DIVISIONE, PO_BEBITALIA
    
    STRATEGIA: PyPDF2 PRIMA (veloce), Docling SOLO se needful (fallback)
    """
    try:
        print(f"\nSTART parsing: {filepath}")
        sys.stdout.flush()
        
        # STEP 1: Estrai con PyPDF2 SUBITO (veloce, non aspettare Docling)
        print(f"   PDF Extraction with PyPDF2...")
        sys.stdout.flush()
        
        pypdf_text = ""
        with open(filepath, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            num_pages = len(pdf_reader.pages)
            print(f"   > Pages found: {num_pages}")
            sys.stdout.flush()
            
            for i, page in enumerate(pdf_reader.pages):
                extracted = page.extract_text()
                if extracted:
                    pypdf_text += extracted
                print(f"   > Page {i+1}/{num_pages}: {len(extracted) if extracted else 0} chars")
                sys.stdout.flush()
        
        if not pypdf_text:
            print(f"   ERROR: No text extracted!")
            sys.stdout.flush()
            return {'error': 'No text extracted from PDF', 'filepath': filepath}
        
        print(f"   OK PyPDF2 complete: {len(pypdf_text)} chars")
        sys.stdout.flush()
        
        # STEP 2: Identifica formato e chiama parser specifico (che usa PyPDF2)
        text = pypdf_text
        pdf_format = detect_pdf_format(text)
        print(f"\n   > Format detected: {pdf_format}")
        sys.stdout.flush()
        
        if pdf_format == "FOR_ORDINE":
            data = extract_for_ordine(text, None, filepath)
        elif pdf_format == "FOR_ORDINE_AZA":
            data = extract_for_ordine_aza(text, None, filepath)
        elif pdf_format == "ORDINE_LS":
            data = extract_ordine_ls(text, None, filepath)
        elif pdf_format == "DIVISIONE":
            data = extract_divisione(text, None, filepath)
        elif pdf_format == "PO_BEBITALIA":
            data = extract_po_bebitalia(text, None, filepath)
        elif pdf_format == "OAFA":
            data = extract_oafa(text, filepath, None)
        else:
            print(f"\n   [WARNING] Format not recognized, use intelligent generic parser")
            sys.stdout.flush()
            data = extract_generic_intelligent(text, None)
        
        # STEP 3: Fallback Docling SOLO per formati sconosciuti OR formati riconosciuti senza articoli
        articoli_trovati = len(data.get('articoli', []))
        should_try_docling = False
        
        if pdf_format == "FOR_ORDINE" or pdf_format == "FOR_ORDINE_AZA" or pdf_format == "ORDINE_LS" or pdf_format == "DIVISIONE" or pdf_format == "PO_BEBITALIA":
            # Formato riconosciuto: usa Docling SOLO se 0 articoli estratti
            should_try_docling = (articoli_trovati == 0)
        else:
            # Formato sconosciuto (generico): usa Docling se <5 articoli
            should_try_docling = (articoli_trovati < 5)
        
        if should_try_docling:
            if articoli_trovati == 0:
                print(f"\n   WARNING: No articles extracted, trying Docling as fallback...")
            else:
                print(f"\n   WARNING: Unknown format with {articoli_trovati} articles, trying Docling...")
            sys.stdout.flush()
            
            markdown_text = extract_text_with_docling(filepath)
            
            if markdown_text:
                # Richiama parser con markdown_text (per fallback Markdown table parser)
                if pdf_format == "FOR_ORDINE":
                    data = extract_for_ordine(text, markdown_text, filepath)
                elif pdf_format == "FOR_ORDINE_AZA":
                    data = extract_for_ordine_aza(text, markdown_text, filepath)
                elif pdf_format == "ORDINE_LS":
                    data = extract_ordine_ls(text, markdown_text, filepath)
                elif pdf_format == "DIVISIONE":
                    data = extract_divisione(text, markdown_text, filepath)
                elif pdf_format == "PO_BEBITALIA":
                    data = extract_po_bebitalia(text, markdown_text, filepath)
                elif pdf_format == "OAFA":
                    data = extract_oafa(text, filepath, markdown_text)
                else:
                    data = extract_generic_intelligent(text, markdown_text)
        
        # STEP 4: Post-processing
        # Se il nome articolo è vuoto, usa il codice come fallback
        for articolo in data.get('articoli', []):
            if not articolo.get('name') or articolo.get('name', '').strip() == '':
                articolo['name'] = articolo.get('code', 'N/A')
        
        data['quantita_totale'] = sum(float(a.get('qty', 0)) for a in data.get('articoli', []))
        
        print(f"   OK Parsing complete: {len(data.get('articoli', []))} articles found")
        print(f"   OK Client: {data.get('cliente', 'N/A')}")
        print(f"   OK Order: {data.get('numero_ordine', 'N/A')}")
        sys.stdout.flush()
        
        return data
        
    except Exception as e:
        print(f"ERROR during parsing: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return {'error': str(e), 'filepath': filepath}


def detect_pdf_format(text: str) -> str:
    """Identifica il formato del PDF in base a marker univoci"""
    print(f"\n   FORMAT DETECTION:")
    text_upper = text.upper()
    
    # DIVISIONE: ha markers specifici
    has_divisione = "DIVISIONE CUCINE" in text_upper or ("N. 300" in text_upper and "ORDINE FORNITORE" in text_upper)
    print(f"      - DIVISIONE CUCINE? {has_divisione}")
    if has_divisione:
        print(f"      FOUND: DIVISIONE")
        return "DIVISIONE"
    
    # PO_BEBITALIA: ha markers molto specifici
    has_bebitalia = "B&B ITALIA" in text_upper and "ORDINE ACQUISTO" in text_upper
    print(f"      - B&B ITALIA + ORDINE ACQUISTO? {has_bebitalia}")
    if has_bebitalia:
        print(f"      FOUND: PO_BEBITALIA")
        return "PO_BEBITALIA"
    
    # OAFA: check PRIMA di FOR_ORDINE (perché OAFA contiene "ORDINE FORNITORE")
    # OAFA ha: A000125 + "DECA" (azienda) + "Spett.le"
    has_oafa_code = bool(re.search(r'A\s*\d{3,}', text))
    has_deca = "DECA" in text_upper
    has_spettale = "Spett.le" in text
    has_oafa = has_oafa_code and has_deca and has_spettale
    print(f"      - Codice A000XXX? {has_oafa_code}")
    print(f"      - DECA? {has_deca}")
    print(f"      - Spett.le? {has_spettale}")
    if has_oafa:
        print(f"      FOUND: OAFA")
        return "OAFA"
    
    # Check for ORDINE_LS last AFTER checking FOR_ORDINE (since LS PDFs might also mention ORDINE)
    # Only mark as LS format if it's NOT already detected as another format
    # AND has ORDINE + LS as standalone elements (not mixed with FOR_ORDINE)
    # Actually, skip LS detection for now if FOR_ORDINE is detected
    
    # FOR_ORDINE: check for AZA variant first (has "AZA INTERNATIONAL")
    has_aza = "AZA INTERNATIONAL" in text_upper
    has_for_ordine = "ORDINE FORNITORE" in text_upper
    print(f"      - ORDINE FORNITORE? {has_for_ordine}")
    print(f"      - AZA INTERNATIONAL? {has_aza}")
    
    if has_for_ordine and has_aza:
        print(f"      FOUND: FOR_ORDINE_AZA")
        return "FOR_ORDINE_AZA"
    elif has_for_ordine:
        print(f"      FOUND: FOR_ORDINE")
        return "FOR_ORDINE"
    
    # Default
    # Check for LS variants AFTER checking FOR_ORDINE
    # Markers: "Abieffe" OR "ORDINE LS" OR "ORDINE D'ACQUISTO" + LS text
    has_abieffe = "ABIEFFE" in text_upper
    has_ordine_ls = "ORDINE" in text_upper and ("LS" in text_upper or "L.S" in text_upper)
    has_ordine_acquisto = "ORDINE" in text_upper and ("D'ACQUISTO" in text_upper or "D ACQUISTO" in text_upper)
    
    if has_abieffe or (has_ordine_ls and not has_for_ordine) or (has_ordine_acquisto and ("LS" in text_upper or "L.S" in text_upper)):
        print(f"      FOUND: ORDINE_LS")
        return "ORDINE_LS"
    
    print(f"      WARNING: Format not recognized - Using generic parser")
    sys.stdout.flush()
    return "GENERIC"


def extract_generic(text: str) -> dict:
    """Parser generico di fallback"""
    return {
        'cliente': "",
        'numero_ordine': "",
        'data_consegna': datetime.now().isoformat(),
        'data_ricezione': datetime.now().isoformat(),
        'articoli': [],
    }

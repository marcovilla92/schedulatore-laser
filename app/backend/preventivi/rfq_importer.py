"""AI RFQ Importer: parsing automatico di un pacchetto ZIP con
PDF ordine cliente + cartella DXF, per pre-compilare un preventivo BOZZA.

Workflow:
1. `parse_order_pdf(pdf_bytes)` → Gemini estrae header (cliente/data/N.ord)
   + tabella articoli (codice/qty/materiale/spessore/descrizione).
2. `match_dxf_to_articoli(articoli, dxf_filenames)` → fuzzy match tra codice
   del PDF e nome file DXF.
3. `build_preventivo_draft(pdf_data, matches)` → dict pronto per PreventivoManager.create()
   + lista warnings (DXF senza articolo, articolo senza DXF, campi mancanti).

Dipendenze: google-generativeai (già in requirements per llm_material_normalizer).
Fallback: se Gemini API key non presente, ritorna None con warning esplicito.
"""
from __future__ import annotations

import json
import logging
import os
import re
import zipfile
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from io import BytesIO
from typing import Any

logger = logging.getLogger(__name__)


# ─── Config ────────────────────────────────────────────────────────────────
GEMINI_MODEL = 'gemini-2.0-flash-exp'
FUZZY_MATCH_THRESHOLD = 0.55  # ratio SequenceMatcher sotto cui NON matcha


# ─── Data classes ─────────────────────────────────────────────────────────
@dataclass
class ArticoloRFQ:
    """Riga articolo estratta dal PDF ordine."""
    codice: str
    quantita: int = 1
    materiale: str | None = None
    spessore_mm: float | None = None
    descrizione: str = ''
    matched_dxf: str | None = None  # filename DXF matchato (basename)
    _matched_score: float = 0.0     # score fuzzy match (0-1)


@dataclass
class RFQParseResult:
    """Risultato del parsing dell'intero pacchetto."""
    success: bool
    cliente: str = ''
    numero_ordine_cliente: str = ''
    data_consegna: str | None = None  # ISO YYYY-MM-DD
    note: str = ''
    articoli: list[ArticoloRFQ] = field(default_factory=list)
    dxf_no_match: list[str] = field(default_factory=list)  # DXF nella cartella senza articolo PDF
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


# ─── Gemini API ────────────────────────────────────────────────────────────

def _get_api_key() -> str | None:
    return os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')


def _build_extraction_prompt() -> str:
    """Prompt strutturato per Gemini: estrai header + tabella articoli dal PDF ordine.

    IMPORTANTE: il prompt chiede JSON strict. Se il PDF è ambiguo/incompleto,
    Gemini deve lasciare i campi null invece di inventarsi valori.
    """
    return (
        "Sei un assistente che estrae dati strutturati da PDF di ordini clienti "
        "di una carpenteria metallica italiana.\n\n"
        "Analizza il PDF allegato e estrai:\n"
        "1. HEADER: cliente, numero ordine, data consegna (formato YYYY-MM-DD)\n"
        "2. ARTICOLI: elenco di righe con codice pezzo, quantità, materiale, "
        "spessore in mm, descrizione (se presente)\n\n"
        "RISPONDI SOLO CON JSON VALIDO (nessun testo extra, nessun markdown). "
        "Schema esatto:\n"
        "```\n"
        "{\n"
        '  "cliente": "nome ragione sociale o null",\n'
        '  "numero_ordine_cliente": "riferimento ordine cliente o null",\n'
        '  "data_consegna": "YYYY-MM-DD o null",\n'
        '  "note": "note generali dell\'ordine o stringa vuota",\n'
        '  "articoli": [\n'
        '    {\n'
        '      "codice": "codice pezzo (obbligatorio)",\n'
        '      "quantita": 1,\n'
        '      "materiale": "S235|ZINCATO|INOX_304|INOX_316|ALU|ALU_5754|ALU_5083|OTTONE o null",\n'
        '      "spessore_mm": 3.0,\n'
        '      "descrizione": "descrizione libera"\n'
        '    }\n'
        '  ]\n'
        "}\n"
        "```\n\n"
        "REGOLE:\n"
        "- Se un valore non è presente nel PDF, usa null (NON inventare).\n"
        "- 'codice' è OBBLIGATORIO per ogni riga. Se manca, salta la riga.\n"
        "- 'quantita' default 1 se non specificato.\n"
        "- 'materiale' — normalizza in uno dei codici standard. Esempi mapping:\n"
        "  'acciaio', 'ferro', 'fe' → S235\n"
        "  'acciaio zincato', 'zincato', 'zn' → ZINCATO\n"
        "  'inox 304', 'aisi 304', 'x5crni' → INOX_304\n"
        "  'inox 316' → INOX_316\n"
        "  'alluminio', 'al 5754' → ALU_5754\n"
        "  'ottone' → OTTONE\n"
        "- 'spessore_mm' — solo il numero (es. 'sp. 3 mm' → 3.0).\n"
        "- 'data_consegna' — parse formati italiani ('25/07/2026', '25 luglio 2026') → YYYY-MM-DD.\n"
        "- Le tabelle sono spesso strutturate a colonne. Se il PDF ha lettera + tabella, estrai la tabella.\n"
    )


def parse_order_pdf(pdf_bytes: bytes, filename: str = 'order.pdf') -> dict | None:
    """Chiama Gemini per estrarre dati strutturati dal PDF ordine.

    Args:
        pdf_bytes: contenuto binario del PDF
        filename: nome file (per log)

    Returns:
        Dict con {cliente, numero_ordine_cliente, data_consegna, note, articoli[]}
        oppure None se API key mancante o parsing fallito.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning('GEMINI_API_KEY non configurata: skip RFQ parsing')
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)

        # Multi-modal: PDF come parte inline
        pdf_part = {'mime_type': 'application/pdf', 'data': pdf_bytes}
        prompt = _build_extraction_prompt()

        response = model.generate_content(
            [prompt, pdf_part],
            generation_config={
                'temperature': 0.0,      # deterministico
                'response_mime_type': 'application/json',
            }
        )
        raw = (response.text or '').strip()

        # Rimuovi eventuali fence markdown residui (Gemini a volte li aggiunge)
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        data = json.loads(raw)
        logger.info('RFQ parsed: cliente=%s, articoli=%d, filename=%s',
                    data.get('cliente'), len(data.get('articoli') or []), filename)
        return data
    except json.JSONDecodeError as je:
        logger.warning('RFQ Gemini output non JSON valido: %s', je)
        return None
    except Exception as e:
        logger.exception('RFQ parsing fallito: %s', e)
        return None


# ─── Fuzzy matching PDF articoli ↔ DXF files ──────────────────────────────

def _normalize_code(s: str) -> str:
    """Normalizza codice per matching: uppercase + solo alfanumerici."""
    return re.sub(r'[^A-Z0-9]', '', (s or '').upper())


def _fuzzy_score(a: str, b: str) -> float:
    """Ratio Levenshtein-like tra due codici normalizzati (0-1)."""
    na, nb = _normalize_code(a), _normalize_code(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # Se uno è prefisso dell'altro (es. '20PA00693' vs '20PA00693-00') → alto
    if na.startswith(nb) or nb.startswith(na):
        min_len = min(len(na), len(nb))
        max_len = max(len(na), len(nb))
        return 0.85 * (min_len / max_len) + 0.15
    return SequenceMatcher(None, na, nb).ratio()


def match_dxf_to_articoli(articoli: list[dict], dxf_filenames: list[str]) -> tuple[list[ArticoloRFQ], list[str]]:
    """Fuzzy match: per ogni articolo PDF cerca il DXF più vicino per codice.

    Args:
        articoli: dict list dal parse_order_pdf (chiavi: codice, quantita, ...)
        dxf_filenames: lista basename DXF (es. ['20PA00693-00.dxf', 'ABC.dxf'])

    Returns:
        (articoli_matched, dxf_no_match)
        - articoli_matched: lista ArticoloRFQ con .matched_dxf popolato dove possibile
        - dxf_no_match: DXF nella cartella che non hanno articolo corrispondente nel PDF
    """
    # Prepara stem (senza estensione) per confronto
    dxf_stems = {fn: os.path.splitext(fn)[0] for fn in dxf_filenames}
    used_dxf: set[str] = set()

    matched: list[ArticoloRFQ] = []
    for a in (articoli or []):
        codice = (a.get('codice') or '').strip()
        if not codice:
            continue
        art = ArticoloRFQ(
            codice=codice,
            quantita=int(a.get('quantita') or 1),
            materiale=(a.get('materiale') or None),
            spessore_mm=(float(a['spessore_mm']) if a.get('spessore_mm') is not None else None),
            descrizione=(a.get('descrizione') or ''),
        )
        # Trova best match tra DXF non ancora usati
        best_fn, best_score = None, 0.0
        for fn, stem in dxf_stems.items():
            if fn in used_dxf:
                continue
            score = _fuzzy_score(codice, stem)
            if score > best_score:
                best_score = score
                best_fn = fn
        if best_fn and best_score >= FUZZY_MATCH_THRESHOLD:
            art.matched_dxf = best_fn
            art._matched_score = best_score
            used_dxf.add(best_fn)
        matched.append(art)

    # DXF senza match
    dxf_no_match = [fn for fn in dxf_filenames if fn not in used_dxf]
    return matched, dxf_no_match


# ─── ZIP extraction ────────────────────────────────────────────────────────

def extract_zip_package(zip_bytes: bytes) -> tuple[bytes | None, str | None, dict[str, bytes]]:
    """Estrae un pacchetto ZIP con PDF ordine + DXF.

    Args:
        zip_bytes: contenuto ZIP

    Returns:
        (pdf_bytes, pdf_filename, dxf_files_map)
        - pdf_bytes: primo PDF trovato (None se assente)
        - pdf_filename: nome file PDF
        - dxf_files_map: {basename: bytes} per ogni .dxf/.dwg nel ZIP

    Ignora file di sistema (thumbs.db, .DS_Store, __MACOSX/) e sotto-cartelle
    (usa solo basename → duplicati di nome vengono sovrascritti, ultimo vince).
    """
    pdf_bytes = None
    pdf_filename = None
    dxf_map: dict[str, bytes] = {}

    try:
        with zipfile.ZipFile(BytesIO(zip_bytes), 'r') as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                base = os.path.basename(name)
                if not base or base.startswith('.') or base.lower() in ('thumbs.db',):
                    continue
                if '__MACOSX' in name:
                    continue
                ext = os.path.splitext(base)[1].lower()
                if ext == '.pdf' and pdf_bytes is None:
                    # Prende il primo PDF trovato (spesso c'è solo l'ordine)
                    pdf_bytes = zf.read(info)
                    pdf_filename = base
                elif ext in ('.dxf', '.dwg'):
                    dxf_map[base] = zf.read(info)
    except zipfile.BadZipFile as e:
        raise ValueError(f'ZIP non valido: {e}')
    except Exception as e:
        raise ValueError(f'Errore estrazione ZIP: {e}')

    return pdf_bytes, pdf_filename, dxf_map


# ─── Pipeline completo ────────────────────────────────────────────────────

def process_rfq_package(zip_bytes: bytes) -> RFQParseResult:
    """Pipeline end-to-end: ZIP → RFQParseResult.

    NON crea il preventivo (compito del caller). Ritorna solo i dati strutturati
    + warnings, così il caller può decidere se scrivere in DB, chiedere conferma
    all'utente, ecc.
    """
    result = RFQParseResult(success=False)

    # 1. Estrai ZIP
    try:
        pdf_bytes, pdf_filename, dxf_map = extract_zip_package(zip_bytes)
    except ValueError as e:
        result.error = str(e)
        return result

    if not pdf_bytes:
        result.error = 'Nessun PDF ordine trovato nel ZIP. Il pacchetto deve contenere almeno un file .pdf'
        return result

    if not dxf_map:
        result.warnings.append('Nessun file DXF trovato nel ZIP: gli articoli verranno creati senza disegno.')

    # 2. Chiama Gemini per parsare il PDF
    parsed = parse_order_pdf(pdf_bytes, pdf_filename or 'order.pdf')
    if not parsed:
        result.error = (
            'AI extraction del PDF fallita. '
            'Verifica che GEMINI_API_KEY sia configurata e che il PDF sia leggibile.'
        )
        return result

    # 3. Popola header
    result.cliente = (parsed.get('cliente') or '').strip() or 'Cliente da specificare'
    result.numero_ordine_cliente = (parsed.get('numero_ordine_cliente') or '').strip()
    result.data_consegna = parsed.get('data_consegna')
    result.note = (parsed.get('note') or '').strip()

    articoli_raw = parsed.get('articoli') or []
    if not articoli_raw:
        result.warnings.append('Nessun articolo estratto dal PDF. Verifica che la tabella sia leggibile.')

    # 4. Fuzzy match articoli PDF ↔ DXF cartella
    articoli, dxf_no_match = match_dxf_to_articoli(articoli_raw, list(dxf_map.keys()))
    result.articoli = articoli
    result.dxf_no_match = dxf_no_match

    # 5. Warnings su completezza
    n_no_dxf = sum(1 for a in articoli if not a.matched_dxf)
    if n_no_dxf > 0:
        result.warnings.append(f'{n_no_dxf} articoli del PDF senza DXF corrispondente nella cartella')
    if dxf_no_match:
        result.warnings.append(f'{len(dxf_no_match)} file DXF nella cartella senza riferimento nel PDF: {", ".join(dxf_no_match[:3])}{"..." if len(dxf_no_match) > 3 else ""}')
    n_no_mat = sum(1 for a in articoli if not a.materiale)
    if n_no_mat > 0:
        result.warnings.append(f'{n_no_mat} articoli senza materiale specificato')
    n_no_sp = sum(1 for a in articoli if not a.spessore_mm)
    if n_no_sp > 0:
        result.warnings.append(f'{n_no_sp} articoli senza spessore specificato')

    result.success = True
    # Salva dxf_map dentro result per il caller (che deve scrivere i file su disco)
    # Uso un attributo non-dataclass:
    result.dxf_map = dxf_map  # type: ignore
    return result

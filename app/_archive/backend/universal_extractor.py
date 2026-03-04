"""
Estrattore Universale PDF — Docling + Gemini 2.0 Flash

Estrae campi strutturati (cliente, numero_ordine, data_consegna, articoli)
da qualsiasi PDF ordine senza configurazione per formato specifico.
Utilizza Docling per convertire il PDF in testo Markdown, poi Gemini 2.0 Flash
per interpretare semanticamente il testo ed estrarre i campi con confidence.

Uso CLI:
    python app/backend/universal_extractor.py <path/to/file.pdf> [--debug]

Uso come libreria:
    from backend.universal_extractor import extract_universal, ExtractionError
    result = extract_universal("path/to/file.pdf")
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Literal

# Pydantic v2 richiesto — dipendenza garantita da docling==2.2.0
from pydantic import BaseModel, Field

# Package: google-genai (NON google-generativeai che e EOL nov 2025)
# Installazione: pip install google-genai
# Import corretto per il nuovo SDK GA (maggio 2025):
from google import genai
from google.genai import types

# Docling: caricamento lazy con fallback se non disponibile
_DOCLING_AVAILABLE = False
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    _DOCLING_AVAILABLE = True
except ImportError as _docling_import_err:
    print(
        f"[WARNING] Docling non disponibile: {_docling_import_err}. "
        "universal_extractor non puo funzionare senza Docling.",
        file=sys.stderr,
    )

# Tentativo di import del backend veloce PyPdfium2
# (disponibile in docling 2.2.0 ma il path esatto va verificato)
_PYPDFIUM_BACKEND = None
if _DOCLING_AVAILABLE:
    try:
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
        _PYPDFIUM_BACKEND = PyPdfiumDocumentBackend
    except ImportError:
        # Fallback: usa il backend default di Docling (piu lento ma funzionale)
        pass

# Costante modello Gemini — cambiare qui per migrare al modello successivo.
# NOTA: gemini-2.0-flash va in pensione il 31 marzo 2026.
# Per migrare: GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MODEL = "gemini-2.0-flash"


# ---------------------------------------------------------------------------
# Eccezione tipizzata
# ---------------------------------------------------------------------------

class ExtractionError(Exception):
    """
    Sollevata quando l'estrazione PDF non puo essere completata.
    Include situazioni come: Docling non disponibile, API key mancante,
    risposta Gemini vuota o malformata, errore di conversione PDF.
    """


# ---------------------------------------------------------------------------
# Schema Pydantic per l'output strutturato di Gemini
# ---------------------------------------------------------------------------

ConfidenceLabel = Literal["alta", "media", "bassa"]


class ArticoloEstratto(BaseModel):
    """Singolo articolo estratto dall'ordine."""

    codice: str = Field(
        description=(
            "Codice articolo (es. TFTAUT1, MD031000, 00600-R01). "
            "Stringa vuota se non trovato."
        )
    )
    descrizione: str = Field(
        description="Descrizione testuale dell'articolo."
    )
    quantita: float = Field(
        description="Quantita numerica dell'articolo (numero intero o decimale)."
    )


class OrdineEstratto(BaseModel):
    """Campi chiave estratti da un ordine di acquisto italiano."""

    cliente: str = Field(
        description=(
            "Nome dell'azienda che EMETTE l'ordine (il fornitore/cliente). "
            "NON 'L.S. S.R.L.' che e il destinatario/acquirente."
        )
    )
    cliente_confidence: ConfidenceLabel = Field(
        description=(
            "Certezza nell'identificazione del cliente: "
            "'alta' = inequivocabile, 'media' = ambiguo, 'bassa' = deduzione."
        )
    )
    numero_ordine: str = Field(
        description=(
            "Numero identificativo dell'ordine (es. '57/AC', '0000173', '300000946'). "
            "Stringa vuota se non trovato."
        )
    )
    numero_ordine_confidence: ConfidenceLabel = Field(
        description="Certezza nell'estrazione del numero ordine."
    )
    data_consegna: str = Field(
        description=(
            "Data di consegna nel formato ISO 8601 (YYYY-MM-DDTHH:MM:SS). "
            "Stringa vuota '' se non trovata nel documento."
        )
    )
    data_consegna_confidence: ConfidenceLabel = Field(
        description="Certezza nell'estrazione della data di consegna."
    )
    articoli: List[ArticoloEstratto] = Field(
        description="Lista degli articoli nell'ordine con codice, descrizione e quantita."
    )
    articoli_confidence: ConfidenceLabel = Field(
        description=(
            "Certezza nell'estrazione della lista articoli nel suo complesso "
            "(un unico score per tutta la lista, non per singolo articolo)."
        )
    )


# ---------------------------------------------------------------------------
# Funzioni private — pipeline interna
# ---------------------------------------------------------------------------

def _build_docling_converter() -> "DocumentConverter":
    """
    Crea un DocumentConverter Docling in modalita rapida (no OCR, no table ML).

    Usa PyPdfiumDocumentBackend se disponibile per conversione ~10x piu veloce.
    Fallback al backend default se PyPdfium2 non e importabile.

    Returns:
        DocumentConverter configurato per PDF digitali senza OCR.

    Raises:
        ExtractionError: Se Docling non e disponibile nell'ambiente.
    """
    if not _DOCLING_AVAILABLE:
        raise ExtractionError(
            "Docling non e installato o non importabile. "
            "Eseguire: pip install docling==2.2.0"
        )

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = False

    if _PYPDFIUM_BACKEND is not None:
        # Backend veloce: pypdfium2 (~10x piu rapido del default)
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                    backend=_PYPDFIUM_BACKEND,
                )
            }
        )
    else:
        # Fallback: backend default di Docling (piu lento ma funzionale)
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            }
        )


def _extract_text_via_docling(
    filepath: str,
    converter: "DocumentConverter",
    debug: bool = False,
) -> str:
    """
    Converte un PDF in testo Markdown usando Docling.

    Args:
        filepath: Percorso al file PDF da convertire.
        converter: Istanza DocumentConverter gia configurata.
        debug: Se True, stampa i primi 2000 caratteri su stderr.

    Returns:
        Testo Markdown estratto dal PDF.

    Raises:
        ExtractionError: Se la conversione Docling fallisce.
    """
    try:
        result = converter.convert(filepath)
        testo = result.document.export_to_markdown()
        if debug:
            print(
                f"[DEBUG] Testo Docling (primi 2000 car.):\n{testo[:2000]}",
                file=sys.stderr,
            )
        return testo
    except Exception as e:
        raise ExtractionError(f"Errore Docling su {filepath}: {e}") from e


def _build_gemini_client() -> genai.Client:
    """
    Crea il client Gemini leggendo la chiave API da GEMINI_API_KEY.

    Returns:
        genai.Client inizializzato con la chiave API.

    Raises:
        ExtractionError: Se GEMINI_API_KEY non e configurata o e vuota.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ExtractionError(
            "GEMINI_API_KEY non configurata. "
            "Impostare la variabile d'ambiente o aggiungere al file app/.env"
        )
    return genai.Client(api_key=api_key)


def _build_prompt(markdown_text: str) -> str:
    """
    Costruisce il prompt per Gemini per l'estrazione dei campi ordine.

    Istruisce Gemini su:
    - Il ruolo di L.S. S.R.L. come DESTINATARIO (non il cliente)
    - Il formato atteso per data_consegna (ISO 8601)
    - Le label di confidence e il loro significato

    Args:
        markdown_text: Testo Markdown del PDF estratto da Docling.

    Returns:
        Stringa prompt completa da passare a Gemini.
    """
    return f"""Sei un sistema di estrazione dati da ordini di acquisto italiani per un'azienda di carpenteria metallica.

Analizza il seguente documento (convertito da PDF a Markdown) ed estrai le informazioni richieste.

## Istruzioni per i campi

- **cliente**: Il nome dell'azienda che EMETTE l'ordine (il fornitore/cliente, NON il destinatario). IMPORTANTE: "L.S. S.R.L." e il destinatario/acquirente — NON e il cliente. Cerca il nome nel logo, nell'intestazione, o dopo "Spettabile"/"Spett.le" quando si riferisce al mittente.
- **numero_ordine**: Il numero identificativo dell'ordine (es. "57/AC", "0000173", "300000946"). Cerca dopo "Ordine Fornitore", "Ordine n.", "PO Number", "Numero ordine". Restituisci stringa vuota "" se non trovato.
- **data_consegna**: La data di consegna richiesta dal cliente. Restituisci in formato ISO 8601 (YYYY-MM-DDTHH:MM:SS), esempio "2026-03-15T00:00:00". Se non trovata, restituisci stringa vuota "".
- **articoli**: Lista degli articoli con codice prodotto, descrizione e quantita. Ogni riga della tabella prodotti e un articolo separato.

## Istruzioni per la confidence

Per ogni campo, valuta la TUA certezza nell'estrazione usando queste label:
- **"alta"**: Il campo e chiaramente presente e inequivocabile nel testo.
- **"media"**: Il campo e presente ma potrebbe essere ambiguo o parziale.
- **"bassa"**: Il campo non e chiaramente presente, hai fatto una deduzione.

## Documento da analizzare

{markdown_text}
"""


def _call_gemini_with_retry(
    client: genai.Client,
    markdown_text: str,
    max_retries: int = 3,
) -> OrdineEstratto:
    """
    Chiama Gemini con retry esponenziale per errori 429 (rate limit).

    Logica retry:
    - Errore 429/RESOURCE_EXHAUSTED: attesa 5s, 10s, 20s (backoff esponenziale)
    - Altri errori: rilancia immediatamente (non si beneficia di retry)
    - Dopo max_retries tentativi: solleva ExtractionError

    Args:
        client: Client Gemini inizializzato.
        markdown_text: Testo Markdown da analizzare.
        max_retries: Numero massimo di tentativi (default 3).

    Returns:
        OrdineEstratto validato da Pydantic.

    Raises:
        ExtractionError: Per risposta vuota, schema malformato, o esaurimento tentativi.
    """
    from pydantic import ValidationError

    last_exc: Exception = Exception("Nessun tentativo eseguito")
    prompt = _build_prompt(markdown_text)

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=OrdineEstratto,
                    temperature=0.1,
                ),
            )

            # Validazione risposta: non deve essere vuota o None
            if not response.text:
                raise ExtractionError("Risposta Gemini vuota o None")

            # Validazione schema Pydantic
            try:
                return OrdineEstratto.model_validate_json(response.text)
            except ValidationError as ve:
                raise ExtractionError(f"Risposta Gemini malformata: {ve}") from ve

        except ExtractionError:
            # ExtractionError e definitivo — non si riprova
            raise

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait_time = 5 * (2 ** attempt)  # 5s, 10s, 20s
                print(
                    f"[WARNING] Rate limit 429 — attesa {wait_time}s "
                    f"(tentativo {attempt + 1}/{max_retries})",
                    file=sys.stderr,
                )
                time.sleep(wait_time)
                last_exc = e
            else:
                # Errore non-429: rilancia immediatamente senza ulteriori tentativi
                raise ExtractionError(
                    f"Errore Gemini non recuperabile: {type(e).__name__}: {e}"
                ) from e

    raise ExtractionError(
        f"Gemini non disponibile dopo {max_retries} tentativi: {last_exc}"
    )


def _to_parser_compatible_dict(ordine: OrdineEstratto) -> dict:
    """
    Converte OrdineEstratto nel formato dict usato dai parser esistenti.

    Aggiunge i campi _confidence come estensione compatibile con la pipeline
    Flask (Phase 6). I campi standard sono identici al formato di parsers_generic.py.

    Args:
        ordine: Istanza OrdineEstratto validata da Pydantic.

    Returns:
        Dict con campi standard (cliente, numero_ordine, data_consegna,
        data_ricezione, articoli, quantita_totale) piu campi _confidence
        e il metadato estrattore="universal".
    """
    articoli_list = [
        {
            "code": art.codice,
            "name": art.descrizione,
            "qty": art.quantita,
        }
        for art in ordine.articoli
    ]

    # data_consegna: usa il valore estratto, fallback a now() se stringa vuota
    data_consegna_value = ordine.data_consegna or datetime.now().isoformat()

    return {
        # Campi standard — compatibili con OrderManager e database
        "cliente": ordine.cliente,
        "numero_ordine": ordine.numero_ordine,
        "data_consegna": data_consegna_value,
        "data_ricezione": datetime.now().isoformat(),
        "articoli": articoli_list,
        "quantita_totale": sum(art.quantita for art in ordine.articoli),
        # Estensione: confidence scores per campo
        # Ignorati dai parser esistenti, usati dalla Phase 6 (integrazione pipeline)
        "cliente_confidence": ordine.cliente_confidence,
        "numero_ordine_confidence": ordine.numero_ordine_confidence,
        "data_consegna_confidence": ordine.data_consegna_confidence,
        "articoli_confidence": ordine.articoli_confidence,
        # Metadato: identifica la provenienza dell'estrazione
        "estrattore": "universal",
    }


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def extract_universal(filepath: str, debug: bool = False) -> dict:
    """
    Estrae campi strutturati da un PDF usando la pipeline Docling + Gemini.

    Pipeline:
    1. Docling converte il PDF in testo Markdown (fast mode: do_ocr=False)
    2. Gemini 2.0 Flash interpreta semanticamente il testo ed estrae:
       cliente, numero_ordine, data_consegna, articoli
       con confidence label (alta/media/bassa) per ogni campo

    Args:
        filepath: Percorso al file PDF da analizzare. Puo essere relativo o assoluto.
        debug: Se True, stampa il testo Docling (primi 2000 car.) su stderr.

    Returns:
        Dict con chiavi:
            cliente (str), numero_ordine (str), data_consegna (str ISO 8601),
            data_ricezione (str ISO 8601), articoli (list of dicts con code/name/qty),
            quantita_totale (float), cliente_confidence, numero_ordine_confidence,
            data_consegna_confidence, articoli_confidence (tutti ConfidenceLabel),
            estrattore="universal"

    Raises:
        ExtractionError: Se Docling non disponibile, GEMINI_API_KEY mancante,
            conversione PDF fallisce, risposta Gemini vuota o schema non valido.
    """
    converter = _build_docling_converter()
    markdown_text = _extract_text_via_docling(filepath, converter, debug=debug)
    client = _build_gemini_client()
    ordine = _call_gemini_with_retry(client, markdown_text)
    return _to_parser_compatible_dict(ordine)


# ---------------------------------------------------------------------------
# Punto di ingresso CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Fix encoding Windows: evita UnicodeEncodeError su stdout
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # Carica GEMINI_API_KEY da app/.env (relativo a questo file: app/backend/../.env)
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    if len(sys.argv) < 2:
        print(
            "Uso: python universal_extractor.py <path/to/file.pdf> [--debug]",
            file=sys.stderr,
        )
        sys.exit(1)

    pdf_path = sys.argv[1]
    debug_mode = "--debug" in sys.argv

    try:
        result = extract_universal(pdf_path, debug=debug_mode)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except ExtractionError as exc:
        print(f"[ERRORE] {exc}", file=sys.stderr)
        sys.exit(1)

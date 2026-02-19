# Phase 5: Estrattore Universale - Research

**Researched:** 2026-02-19
**Domain:** Docling PDF-to-text + Gemini LLM structured extraction + confidence scoring
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Struttura confidence score
- Il confidence score viene assegnato **per campo** (non un unico score per ordine)
  - Campi che ricevono confidence individuale: `cliente`, `numero_ordine`, `data_consegna`, `articoli`
- La rappresentazione e una **label testuale**: `"alta"`, `"media"`, `"bassa"`
  - Formato nel dict: `{"cliente": "Rossi SRL", "cliente_confidence": "alta"}`
  - Non un numero 0.0-1.0
- Il confidence e **dichiarato da Gemini nel JSON di risposta** — il prompt chiede a Gemini di valutare la propria certezza per ogni campo
  - Non calcolato con euristiche nostre
- Per gli **articoli** (lista): un unico `articoli_confidence` per l'intera lista, non per ogni singolo articolo
  - Formato: `{"articoli": [...], "articoli_confidence": "alta"}`

### Claude's Discretion
- Formato output e compatibilita con i parser esistenti (struttura del dict, nomi campi)
- Gestione errori Gemini (retry logic, timeout, eccezioni tipizzate)
- Ruolo di Docling: se e come riabilitarlo, gestione testo intermedio
- Struttura del prompt Gemini (schema JSON richiesto, istruzioni per confidence)
- Dove posizionare il modulo nel progetto (`app/backend/` vs `app/`)

### Deferred Ideas (OUT OF SCOPE)
- Nessuna idea fuori scope emersa dalla discussione
- Integrazione nella pipeline Flask (Phase 6)
- UI per confidence scores (Phase 6)
- Caching (Phase 6)
- Batch processing (Phase 6)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXTR-01 | Il sistema converte qualsiasi PDF in testo strutturato tramite Docling prima di passarlo al modello LLM | Docling API verified: `DocumentConverter` + `export_to_markdown()`. Fast mode with `do_ocr=False` + `PyPdfiumDocumentBackend` documented. |
| EXTR-02 | Il sistema chiama Gemini 2.0 Flash con il testo estratto e riceve i campi chiave in formato JSON strutturato (cliente, numero_ordine, data_consegna, articoli con quantita e descrizione) | `google-genai` SDK + `response_mime_type="application/json"` + Pydantic schema pattern verified from official docs. |
| EXTR-03 | Ogni campo estratto ha un indicatore di confidenza (alta/media/bassa) restituito insieme ai dati | Confidence-as-string approach: schema includes `*_confidence` fields alongside data fields. Gemini produces them natively via prompt instruction. |
| EXTR-04 | L'estrattore funziona su PDF mai visti in precedenza senza richiedere configurazione o nuovo codice | Architecture: Docling extracts text without format-specific rules; Gemini interprets semantically. No format detection needed. |
</phase_requirements>

---

## Summary

Phase 5 builds a standalone Python module that replaces the format-specific dispatcher approach with a two-step universal pipeline: Docling converts any PDF to structured text (Markdown), then Gemini evaluates the text semantically and extracts structured fields with per-field confidence labels. The module requires no format detection or regex patterns.

The critical SDK decision is that **`google-generativeai` is deprecated** (support ended November 30, 2025). The current official SDK is `google-genai` (pip install google-genai), which uses `from google import genai`. Structured JSON output is produced via `response_mime_type="application/json"` and a Pydantic schema. Gemini 2.0 Flash (`gemini-2.0-flash`) is the user-locked model choice; it remains functional but is **scheduled for shutdown March 31, 2026** — the code should use a configurable model string constant so Phase 6 can swap to `gemini-2.5-flash` without code changes.

Docling 2.2.0 is already installed in `app/requirements.txt` but disabled in `pdf_parser.py` via `DOCLING_AVAILABLE = False`. The universal extractor creates its own `DocumentConverter` instance independently, bypassing the disabled flag entirely. For digital PDFs (which all 16 known orders are), Docling should be run with `do_ocr=False` and `PyPdfiumDocumentBackend` for 10x faster conversion.

**Primary recommendation:** Place the module at `app/backend/universal_extractor.py`, use `google-genai` SDK with Pydantic-defined output schema, configure Docling in fast mode (no OCR), and define the Gemini model string as a module-level constant `GEMINI_MODEL = "gemini-2.0-flash"`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `google-genai` | latest (>=1.0, GA May 2025) | Official Gemini API SDK for Python | Replaced deprecated `google-generativeai`; actively maintained; structured output support |
| `docling` | 2.2.0 (already in requirements.txt) | PDF-to-Markdown conversion | Already installed; provides format-agnostic text extraction |
| `pydantic` | v2 (installed as docling dependency) | Define JSON output schema for Gemini | Integrates directly with `google-genai` structured output via `model_json_schema()` |
| `python-dotenv` | 1.0.0 (already in requirements.txt) | Load `GEMINI_API_KEY` from `app/.env` | Already in project; standard pattern for secret management |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tenacity` | any | Retry with exponential backoff for 429 errors | If rate limit errors are observed during testing |
| `PyPdfiumDocumentBackend` | (part of docling) | Fast Docling PDF backend | Use instead of default backend for 10x speedup |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `google-genai` | `google-generativeai` | Old SDK deprecated Nov 30, 2025 — do not use |
| Pydantic schema | Raw JSON schema dict | Pydantic gives type validation for free; use Pydantic |
| `gemini-2.0-flash` | `gemini-2.5-flash` | 2.0 Flash shuts down March 31, 2026; use constant so it's easy to swap |
| Docling (no-OCR mode) | Full Docling with OCR | OCR adds 30s+ per PDF; all known orders are digital PDFs with text layers |

**Installation (new dependency only):**
```bash
cd app
pip install google-genai
```

Pydantic v2 is already installed (docling dependency). python-dotenv already installed.

---

## Architecture Patterns

### Recommended Project Structure
```
app/
├── .env                          # GEMINI_API_KEY=... (already exists)
├── backend/
│   ├── universal_extractor.py    # New: this phase's deliverable
│   ├── pdf_parser.py             # Existing: untouched (dispatcher)
│   └── parsers_*.py              # Existing: untouched
└── audit_parsers.py              # Existing: Phase 4 baseline script
```

The module lives in `app/backend/` to match the existing package structure. This makes Phase 6 integration trivial (same import path as other parsers). It is also directly runnable as a CLI script via `if __name__ == "__main__"` guard.

### Pattern 1: Docling Fast-Mode Conversion
**What:** Convert a PDF to Markdown text without OCR, using the fast pypdfium2 backend.
**When to use:** Always for this project — all 16 known PDF orders have embedded text layers (they are generated PDFs, not scans).

```python
# Source: Official Docling docs + github.com/docling-project/docling/discussions/245
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

def _build_docling_converter() -> DocumentConverter:
    """Crea un DocumentConverter in modalita rapida (no OCR, no table structure ML)."""
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = False

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend,
            )
        }
    )

def extract_text_via_docling(filepath: str, converter: DocumentConverter) -> str:
    """Converte un PDF in Markdown usando Docling. Ritorna stringa vuota su errore."""
    result = converter.convert(filepath)
    return result.document.export_to_markdown()
```

### Pattern 2: Pydantic Schema for Gemini Structured Output
**What:** Define the expected JSON structure using Pydantic, then pass it to Gemini's structured output API. Gemini enforces the schema syntactically; the prompt guides semantics.
**When to use:** Whenever JSON output with a known schema is required.

```python
# Source: Official Gemini API structured output docs (ai.google.dev/gemini-api/docs/structured-output)
from pydantic import BaseModel, Field
from typing import List, Literal

ConfidenceLabel = Literal["alta", "media", "bassa"]

class ArticoloEstratto(BaseModel):
    codice: str = Field(description="Codice articolo (es. TFTAUT1, MD031000). Stringa vuota se non trovato.")
    descrizione: str = Field(description="Descrizione testuale dell'articolo.")
    quantita: float = Field(description="Quantita numerica dell'articolo.")

class OrdineEstratto(BaseModel):
    cliente: str = Field(description="Nome azienda cliente/fornitore che emette l'ordine.")
    cliente_confidence: ConfidenceLabel = Field(description="Certezza nell'estrazione del cliente.")
    numero_ordine: str = Field(description="Numero identificativo dell'ordine (es. 57/AC, 0000173).")
    numero_ordine_confidence: ConfidenceLabel = Field(description="Certezza nell'estrazione del numero ordine.")
    data_consegna: str = Field(description="Data di consegna nel formato ISO 8601 (YYYY-MM-DDTHH:MM:SS). Stringa vuota se non trovata.")
    data_consegna_confidence: ConfidenceLabel = Field(description="Certezza nell'estrazione della data di consegna.")
    articoli: List[ArticoloEstratto] = Field(description="Lista degli articoli nell'ordine.")
    articoli_confidence: ConfidenceLabel = Field(description="Certezza nell'estrazione della lista articoli nel suo complesso.")
```

### Pattern 3: Gemini API Call with Structured Output
**What:** Call Gemini with the Pydantic schema enforced via `response_mime_type` + `response_json_schema`.
**When to use:** The primary extraction call in `universal_extractor.py`.

```python
# Source: Official google-genai SDK docs (googleapis.github.io/python-genai/)
import os
from google import genai
from google.genai import types

GEMINI_MODEL = "gemini-2.0-flash"  # Costante: cambiare qui per migrare a 2.5

def _build_gemini_client() -> genai.Client:
    """Crea il client Gemini leggendo la chiave da GEMINI_API_KEY."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY non trovata nelle variabili d'ambiente.")
    return genai.Client(api_key=api_key)

def _call_gemini(client: genai.Client, markdown_text: str) -> OrdineEstratto:
    """Invia il testo Markdown a Gemini e riceve i campi strutturati."""
    prompt = _build_prompt(markdown_text)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=OrdineEstratto,  # Pydantic class direttamente
            temperature=0.1,  # Bassa variabilita per estrazione dati
        ),
    )
    return OrdineEstratto.model_validate_json(response.text)
```

**Note on `response_schema` vs `response_json_schema`:** The `google-genai` SDK accepts a Pydantic class directly as `response_schema` (the SDK serializes it internally). The alternative `response_json_schema` accepts a raw dict from `Model.model_json_schema()`. Both work; passing the class directly is cleaner.

### Pattern 4: Prompt Engineering for Extraction + Confidence
**What:** A system prompt that instructs Gemini to (a) extract the fields, (b) rate its own confidence per field using the three Italian labels.
**When to use:** The prompt passed to `_call_gemini()`.

```python
# Source: research — derived from official structured output docs and prompt engineering best practices
def _build_prompt(markdown_text: str) -> str:
    return f"""Sei un sistema di estrazione dati da ordini di acquisto italiani per un'azienda di carpenteria metallica.

Analizza il seguente documento (convertito da PDF a Markdown) ed estrai le informazioni richieste.

## Istruzioni per i campi

- **cliente**: Il nome dell'azienda che EMETTE l'ordine (il fornitore/cliente, non "L.S. S.R.L." che e il destinatario). Cerca il nome nel logo, nell'intestazione, o dopo "Spettabile"/"Spett.le".
- **numero_ordine**: Il numero identificativo dell'ordine (es. "57/AC", "0000173", "300000946"). Cerca dopo "Ordine Fornitore", "Ordine n.", "PO Number".
- **data_consegna**: La data di consegna richiesta. Restituisci in formato ISO 8601 (YYYY-MM-DDTHH:MM:SS). Se non trovata, restituisci stringa vuota "".
- **articoli**: Lista degli articoli con codice, descrizione e quantita. Ogni riga della tabella prodotti e un articolo.

## Istruzioni per la confidence

Per ogni campo, valuta la TUA certezza nell'estrazione usando queste label:
- **"alta"**: Il campo e chiaramente presente e inequivocabile nel testo.
- **"media"**: Il campo e presente ma potrebbe essere ambiguo o parziale.
- **"bassa"**: Il campo non e chiaramente presente, hai fatto una deduzione.

## Documento da analizzare

{markdown_text}
"""
```

### Pattern 5: Output Dict Compatible with Existing Parsers
**What:** Convert the Pydantic model output to the same dict format as existing `parsers_*.py` modules.
**When to use:** When returning results from `extract_universal()`, the module's public API.

```python
# Source: analysis of parsers_generic.py return structure
from datetime import datetime

def _to_parser_compatible_dict(ordine: OrdineEstratto) -> dict:
    """
    Converte OrdineEstratto nel formato dict usato dai parser esistenti,
    aggiungendo i campi _confidence come estensione.
    """
    articoli_list = [
        {
            "code": art.codice,
            "name": art.descrizione,
            "qty": art.quantita,
        }
        for art in ordine.articoli
    ]

    return {
        # Campi standard (compatibili con OrderManager e database)
        "cliente": ordine.cliente,
        "numero_ordine": ordine.numero_ordine,
        "data_consegna": ordine.data_consegna or datetime.now().isoformat(),
        "data_ricezione": datetime.now().isoformat(),
        "articoli": articoli_list,
        "quantita_totale": sum(a.quantita for a in ordine.articoli),
        # Estensione: confidence scores (ignorati dai parser esistenti, usati da Phase 6)
        "cliente_confidence": ordine.cliente_confidence,
        "numero_ordine_confidence": ordine.numero_ordine_confidence,
        "data_consegna_confidence": ordine.data_consegna_confidence,
        "articoli_confidence": ordine.articoli_confidence,
        # Metadato
        "estrattore": "universal",
    }
```

### Pattern 6: CLI Entry Point
**What:** Standard `if __name__ == "__main__"` block so the module is testable from command line.
**When to use:** Required by EXTR-04 — must be runnable without Flask.

```python
# Source: pattern from app/audit_parsers.py and app/batch_test_ordini.py
if __name__ == "__main__":
    import sys
    from pathlib import Path
    from dotenv import load_dotenv

    # Carica .env dalla directory app/
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)

    if len(sys.argv) < 2:
        print("Uso: python universal_extractor.py <path/to/file.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    result = extract_universal(pdf_path)

    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

### Anti-Patterns to Avoid
- **Importing from `google.generativeai`:** Old SDK, deprecated Nov 30, 2025. Use `from google import genai` (package: `google-genai`).
- **Calling `_ensure_docling_loaded()` from pdf_parser.py:** That function hard-codes `DOCLING_AVAILABLE = False`. The universal extractor creates its own `DocumentConverter` instance — it does not go through `pdf_parser.py` at all.
- **Hardcoded model string in multiple places:** Define `GEMINI_MODEL = "gemini-2.0-flash"` once at module level. Migration to 2.5 Flash will be a one-line change.
- **Using `response_json_schema` with a raw dict containing `Literal` fields:** Pydantic's `model_json_schema()` correctly serializes `Literal["alta", "media", "bassa"]` to `{"enum": ["alta", "media", "bassa"]}`. Do not hand-write the JSON schema dict.
- **Importing `universal_extractor.py` from `app/` root:** The module is in `app/backend/`. If run from `app/`, the CLI block must add `app/` to `sys.path` (same pattern as `audit_parsers.py`).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema enforcement | Regex post-processing on Gemini output | `response_mime_type="application/json"` + Pydantic schema | Gemini guarantees syntactically valid JSON matching the schema |
| PDF text extraction | PyPDF2 fallback regex | Docling `DocumentConverter` | Docling handles tables, multi-column layouts, headers that PyPDF2 flattens incorrectly |
| Retry on 429 | Manual sleep loop | `tenacity` with exponential backoff | Handles jitter, max retries, specific exception types correctly |
| API key loading | `os.environ` with manual fallback | `python-dotenv` `load_dotenv()` | Already in project; handles `.env` file location portably |
| Confidence calculation | Heuristics on returned strings | Gemini self-reports confidence | LLM self-evaluation is more accurate than post-hoc heuristics for semantic ambiguity |

**Key insight:** The power of this phase is that neither the extraction logic nor the confidence scoring requires domain-specific code. Both come from Gemini's language understanding. Custom code is only needed for: (1) calling Docling, (2) calling Gemini, (3) validating the response schema, (4) converting to the project's dict format.

---

## Common Pitfalls

### Pitfall 1: Wrong Gemini SDK Package
**What goes wrong:** `pip install google-generativeai` installs the old SDK. `from google.generativeai import GenerativeModel` works but the API is different and the old SDK no longer receives updates.
**Why it happens:** Web search results and StackOverflow answers from 2024 still reference the old package name.
**How to avoid:** Install `google-genai`. Import with `from google import genai`. The new client API: `genai.Client(api_key=...)`.
**Warning signs:** If you see `import google.generativeai` anywhere in the module, it's using the wrong SDK.

### Pitfall 2: Gemini 2.0 Flash Retirement Approaching
**What goes wrong:** `gemini-2.0-flash` shuts down March 31, 2026. Code using a hardcoded string will break on that date.
**Why it happens:** User locked this model choice for Phase 5 (valid choice, still works today). Phase 6 will need migration.
**How to avoid:** Define `GEMINI_MODEL = "gemini-2.0-flash"` as a module-level constant. Document the retirement date in a comment. Migration to `gemini-2.5-flash` is a one-line change.
**Warning signs:** Any API call where the model string is a string literal inside the function body.

### Pitfall 3: Docling Takes 30+ Seconds Without Fast Mode
**What goes wrong:** Default `DocumentConverter()` (no options) enables OCR and table structure ML models, which are very slow on CPU-only machines.
**Why it happens:** The existing codebase disabled Docling entirely to avoid slowness. But the universal extractor needs Docling to work.
**How to avoid:** Use `do_ocr=False`, `do_table_structure=False`, and `PyPdfiumDocumentBackend`. For the 16 known PDF orders (all generated digital PDFs, not scans), this is safe — there is no handwritten content.
**Warning signs:** Conversion of a single PDF takes more than 5 seconds.

### Pitfall 4: Gemini Treats "L.S. S.R.L." as Cliente
**What goes wrong:** The same problem that affects existing parsers — L.S. S.R.L. is the destination/recipient of orders, not the client placing them. Gemini without explicit instruction may extract it as `cliente`.
**Why it happens:** L.S. S.R.L. appears prominently in headers and "Spettabile" sections.
**How to avoid:** The prompt explicitly instructs Gemini to exclude "L.S. S.R.L." and look for the sender. Example instruction already included in Pattern 4's prompt template.
**Warning signs:** Test result shows `cliente = "L.S. S.R.L."` or `cliente = "L.S. SRL"`.

### Pitfall 5: Rate Limit 429 on Free Tier
**What goes wrong:** Free tier for Gemini 2.0 Flash has been cut to approximately 15 RPM and ~1500 RPD (per community reports, Feb 2026). For standalone testing of 16 PDFs, this is sufficient. But if the full batch runs fast (under 1 minute), 16 calls at 15 RPM is fine.
**Why it happens:** Google reduced free tier limits significantly in December 2025.
**How to avoid:** Add a simple retry with 5-second sleep on 429 errors. If `tenacity` is not available, a manual try/except loop with `time.sleep(5)` is sufficient for Phase 5.
**Warning signs:** `google.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED`.

### Pitfall 6: `.env` File Path Relative to Working Directory
**What goes wrong:** `load_dotenv()` without arguments looks for `.env` in the current working directory. If the script is run from `app/backend/` or from the project root, it won't find `app/.env`.
**Why it happens:** The `.env` file is at `app/.env` but `python universal_extractor.py` may be run from different directories.
**How to avoid:** Use `load_dotenv(Path(__file__).parent.parent / ".env")` to always resolve to `app/.env` regardless of CWD. See Pattern 6 for the full CLI entry point.
**Warning signs:** `GEMINI_API_KEY not found` error even though the key exists in the file.

### Pitfall 7: Pydantic v1 vs v2 API Mismatch
**What goes wrong:** `model_json_schema()` and `model_validate_json()` are Pydantic v2 methods. If Pydantic v1 is installed, these do not exist (`schema()` and `parse_raw()` are the v1 equivalents).
**Why it happens:** Pydantic v1 is still common in older projects.
**How to avoid:** Docling 2.2.0 requires Pydantic v2, so it is guaranteed to be installed. Verify with `import pydantic; print(pydantic.VERSION)`. If v2, proceed.
**Warning signs:** `AttributeError: type object 'OrdineEstratto' has no attribute 'model_json_schema'`.

---

## Code Examples

Verified patterns from official sources:

### Complete Module Skeleton
```python
# app/backend/universal_extractor.py
# Source: patterns derived from google-genai official docs + docling official docs
"""
Estrattore Universale PDF — Docling + Gemini 2.0 Flash
Estrae campi strutturati da qualsiasi PDF ordine senza configurazione per formato.
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from google import genai
from google.genai import types
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

# Costante: cambiare qui per migrare al modello successivo.
# NOTA: gemini-2.0-flash va in pensione il 31 marzo 2026.
# Rimpiazzo: GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MODEL = "gemini-2.0-flash"


# --- Schema output ---

ConfidenceLabel = Literal["alta", "media", "bassa"]

class ArticoloEstratto(BaseModel):
    codice: str
    descrizione: str
    quantita: float

class OrdineEstratto(BaseModel):
    cliente: str
    cliente_confidence: ConfidenceLabel
    numero_ordine: str
    numero_ordine_confidence: ConfidenceLabel
    data_consegna: str
    data_consegna_confidence: ConfidenceLabel
    articoli: List[ArticoloEstratto]
    articoli_confidence: ConfidenceLabel


# --- Public API ---

def extract_universal(filepath: str) -> dict:
    """
    Estrae campi strutturati da un PDF usando Docling + Gemini.
    Ritorna un dict compatibile con i parser esistenti + campi _confidence.
    """
    load_dotenv(Path(__file__).parent.parent / ".env")

    converter = _build_docling_converter()
    markdown_text = _extract_text(filepath, converter)

    client = _build_gemini_client()
    ordine = _call_gemini(client, markdown_text)

    return _to_parser_compatible_dict(ordine)
```

### Docling Fast-Mode Converter Initialization
```python
# Source: docling official docs + github.com/docling-project/docling/discussions/245
def _build_docling_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = False

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend,
            )
        }
    )
```

### Gemini Call with Structured Output
```python
# Source: ai.google.dev/gemini-api/docs/structured-output
def _call_gemini(client: genai.Client, markdown_text: str) -> OrdineEstratto:
    prompt = _build_prompt(markdown_text)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=OrdineEstratto,
            temperature=0.1,
        ),
    )
    return OrdineEstratto.model_validate_json(response.text)
```

### Simple Retry for 429 Rate Limit (no tenacity dependency)
```python
# Source: research — community pattern for Gemini 429 handling
import time

def _call_gemini_with_retry(client: genai.Client, markdown_text: str,
                             max_retries: int = 3) -> OrdineEstratto:
    last_exc = None
    for attempt in range(max_retries):
        try:
            return _call_gemini(client, markdown_text)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait_time = 5 * (2 ** attempt)  # 5s, 10s, 20s
                print(f"[WARNING] Rate limit 429 - attesa {wait_time}s (tentativo {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                last_exc = e
            else:
                raise  # Non e un errore di rate limit, rilancia
    raise RuntimeError(f"Gemini non disponibile dopo {max_retries} tentativi: {last_exc}")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `google-generativeai` SDK | `google-genai` SDK | GA May 2025 | Different import, different client API, supports structured output better |
| `GenerativeModel.generate_content()` | `client.models.generate_content()` | May 2025 | New client-based API; old style deprecated |
| `response_schema` (old SDK) | `response_schema` in `GenerateContentConfig` | 2025 | Same parameter name but different object hierarchy |
| Docling full pipeline (OCR + table ML) | `do_ocr=False` + `PyPdfiumDocumentBackend` | Always available | 10x faster; safe for digital PDFs |
| `gemini-2.0-flash` | `gemini-2.5-flash` (from April 2026) | Shutdown: March 31, 2026 | Use constant to allow 1-line migration |

**Deprecated/outdated:**
- `google-generativeai` package: EOL November 30, 2025. Do not install.
- `gemini-2.0-flash` model: Shutdown March 31, 2026. Still valid for Phase 5 but needs migration in Phase 6.

---

## Open Questions

1. **Gemini response_schema with Pydantic Literal["alta", "media", "bassa"]**
   - What we know: `response_schema` accepts Pydantic models. `Literal` types serialize to JSON Schema `enum`. Official docs confirm Pydantic integration.
   - What's unclear: Whether `Literal` with Italian strings works cleanly through the SDK's internal serialization (no explicit example found in official docs).
   - Recommendation: Test this in the first implementation task. If `Literal` causes schema rejection, replace with `str` and add enum constraint via `Field(pattern="^(alta|media|bassa)$")`. Add validation post-response.

2. **Docling 2.2.0 vs current API compatibility**
   - What we know: The API (`DocumentConverter`, `export_to_markdown()`, `PdfPipelineOptions`, `do_ocr`) has been stable. The project pins `docling==2.2.0`.
   - What's unclear: Whether `PyPdfiumDocumentBackend` and `PdfFormatOption` exist in 2.2.0 specifically (they were added in early Docling versions but the exact version is unverified).
   - Recommendation: First task should include a quick import test. If `PyPdfiumDocumentBackend` import fails on 2.2.0, fall back to `do_ocr=False` alone with the default backend.

3. **Docling Markdown quality for Italian order PDFs**
   - What we know: Docling was previously used successfully in this project (disabled only for speed reasons, not quality). `export_to_markdown()` is called in the existing `extract_text_with_docling()` function.
   - What's unclear: Quality of table extraction in no-table-structure mode (with `do_table_structure=False`). Tables in orders may be rendered as plain text rows.
   - Recommendation: Test with at least one known-format PDF (e.g., OAFA202600125.pdf with 16 articles). If table structure is lost, re-enable `do_table_structure=True` (adds ~3-5s per PDF but preserves table Markdown).

---

## Sources

### Primary (HIGH confidence)
- Official Gemini API docs — `ai.google.dev/gemini-api/docs/structured-output` — Pydantic schema, response_mime_type, response_schema pattern
- Official Gemini API docs — `ai.google.dev/gemini-api/docs/deprecations` — gemini-2.0-flash shutdown date March 31, 2026; replacement gemini-2.5-flash
- Official Gemini API docs — `ai.google.dev/gemini-api/docs/quickstart` — SDK package name `google-genai`, client initialization, GEMINI_API_KEY env var
- Official Docling docs — `docling-project.github.io/docling/getting_started/quickstart/` — DocumentConverter, export_to_markdown() API
- Docling GitHub discussion #245 — `github.com/docling-project/docling/discussions/245` — `do_ocr=False`, `do_table_structure=False`, PyPdfiumDocumentBackend
- `app/backend/pdf_parser.py` — existing `extract_text_with_docling()`, DOCLING_AVAILABLE flag, how Docling is currently (not) used
- `app/backend/parsers_generic.py` — existing return dict structure (`cliente`, `numero_ordine`, `data_consegna`, `data_ricezione`, `articoli`, `quantita_totale`)
- `app/requirements.txt` — confirms `docling==2.2.0`, `python-dotenv==1.0.0` already installed; `google-genai` not yet installed

### Secondary (MEDIUM confidence)
- WebSearch aggregated results — `google-generativeai` deprecated Nov 30, 2025 (confirmed by multiple sources including PyPI and GitHub)
- WebSearch — free tier rate limits: ~15 RPM, ~1500 RPD for gemini-2.0-flash (community-reported, Feb 2026; not from official docs)
- WebSearch + docling GitHub issues — `PyPdfiumDocumentBackend` exists and provides fast mode (mentioned in multiple issues and discussions)

### Tertiary (LOW confidence)
- Rate limit numbers for gemini-2.0-flash free tier: conflicting community reports (some say 15 RPM, some say 5 RPM post-December 2025 cuts). The plan should not assume specific limits; implement retry logic regardless.

---

## Metadata

**Confidence breakdown:**
- Standard stack (google-genai, Docling, Pydantic): HIGH — verified from official docs
- Architecture (module placement, dict format): HIGH — derived from existing codebase analysis
- Gemini structured output pattern: HIGH — official docs example verified
- Docling fast mode API: MEDIUM — `do_ocr=False` verified; `PyPdfiumDocumentBackend` in 2.2.0 needs import test
- Rate limits: LOW — community-reported numbers only; use retry regardless

**Research date:** 2026-02-19
**Valid until:** 2026-03-10 (Gemini model situation is fast-moving; re-verify before Phase 6 planning)

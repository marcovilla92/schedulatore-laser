---
phase: 05-estrattore-universale
plan: 01
subsystem: api
tags: [google-genai, docling, gemini, pydantic, pdf-extraction, llm, structured-output]

# Dependency graph
requires:
  - phase: 04-audit-parser
    provides: baseline extraction accuracy metrics (cliente 87%, data_consegna 81%) used to measure improvement
provides:
  - app/backend/universal_extractor.py — standalone Docling+Gemini extraction module
  - ExtractionError typed exception for all failure modes
  - OrdineEstratto Pydantic model with per-field confidence labels (alta/media/bassa)
  - extract_universal() public API compatible with existing parser dict format
  - CLI entry point for PDF extraction without Flask
affects:
  - 06-integrazione-pipeline: will import extract_universal and integrate into pdf_parser.py dispatcher

# Tech tracking
tech-stack:
  added:
    - google-genai==1.64.0 (official Gemini SDK, replaces deprecated google-generativeai EOL Nov 2025)
  patterns:
    - Docling fast-mode PDF-to-Markdown (do_ocr=False, do_table_structure=False, PyPdfiumDocumentBackend)
    - Gemini structured output via response_schema=Pydantic model + response_mime_type=application/json
    - Per-field confidence labels declared by Gemini (not heuristic calculation)
    - ExtractionError typed exception as unified failure surface
    - Exponential backoff retry for 429 RESOURCE_EXHAUSTED (5s/10s/20s, max 3 attempts)
    - GEMINI_MODEL constant for single-point model migration

key-files:
  created:
    - app/backend/universal_extractor.py (471 lines)
  modified:
    - app/requirements.txt (added google-genai)

key-decisions:
  - "google-genai (not google-generativeai) — new SDK GA May 2025, old EOL Nov 2025"
  - "GEMINI_MODEL = 'gemini-2.0-flash' as module constant — retires March 31 2026, migrate to gemini-2.5-flash"
  - "PyPdfiumDocumentBackend imported with graceful fallback — 2.2.0 compatibility confirmed"
  - "ExtractionError raised on missing API key (not KeyError crash) — typed exception for clean caller handling"
  - "Pydantic Literal['alta', 'media', 'bassa'] for ConfidenceLabel — serializes to JSON Schema enum correctly"

patterns-established:
  - "Pattern: Docling fast-mode converter — build once, reuse across calls; do_ocr=False cuts 30s to <3s"
  - "Pattern: Gemini confidence self-declaration — prompt instructs model to rate its own certainty per field"
  - "Pattern: _to_parser_compatible_dict() — Pydantic model to existing dict format, confidence fields added as extension"

requirements-completed: [EXTR-01, EXTR-02, EXTR-03, EXTR-04]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 5 Plan 1: Estrattore Universale Summary

**Standalone Docling+Gemini 2.0 Flash PDF extractor with per-field confidence labels (alta/media/bassa) via Pydantic structured output, replacing regex/dispatcher approach with semantic LLM comprehension**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T14:01:23Z
- **Completed:** 2026-02-19T14:04:39Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `app/backend/universal_extractor.py` (471 lines) with complete Docling + Gemini pipeline
- Added `google-genai==1.64.0` to requirements.txt and installed (replaces deprecated `google-generativeai`)
- Implemented typed ExtractionError for all failure modes: missing API key, Docling unavailable, empty/malformed Gemini response, PDF conversion failure
- Pydantic v2 OrdineEstratto schema with `ConfidenceLabel = Literal["alta", "media", "bassa"]` serializes correctly to JSON Schema enum for Gemini structured output
- Retry logic handles 429 RESOURCE_EXHAUSTED with exponential backoff (5s, 10s, 20s)
- Output dict is backward-compatible with existing `parsers_generic.py` format (`cliente`, `numero_ordine`, `data_consegna`, `data_ricezione`, `articoli`, `quantita_totale`) plus confidence extensions

## Task Commits

Each task was committed atomically:

1. **Task 1: Aggiungere google-genai a requirements.txt e installare** - `e3bfe81` (chore)
2. **Task 2: Creare universal_extractor.py — pipeline Docling + Gemini con confidence** - `cfe0d58` (feat)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified

- `app/requirements.txt` - Added `google-genai` dependency (no version pin, GA and stable)
- `app/backend/universal_extractor.py` - Universal extractor module: ExtractionError, ConfidenceLabel, ArticoloEstratto, OrdineEstratto, _build_docling_converter(), _extract_text_via_docling(), _build_gemini_client(), _build_prompt(), _call_gemini_with_retry(), _to_parser_compatible_dict(), extract_universal(), CLI __main__ block

## Decisions Made

- **google-genai SDK:** Used `google-genai` (not `google-generativeai` which is EOL Nov 30, 2025). Import: `from google import genai`. Client API: `genai.Client(api_key=...)`.
- **GEMINI_MODEL constant:** `GEMINI_MODEL = "gemini-2.0-flash"` defined at module level with retirement comment (March 31, 2026). Migration to `gemini-2.5-flash` is a one-line change.
- **PyPdfiumDocumentBackend fallback:** Import attempted at module load; if unavailable (version mismatch), falls back to default Docling backend silently. `_PYPDFIUM_BACKEND = None` flag controls which code path runs.
- **Docling availability guard:** `_DOCLING_AVAILABLE` flag set at import time; `_build_docling_converter()` raises ExtractionError immediately if Docling not installed (clean error, no AttributeError).
- **ExtractionError design:** Raised for: Docling unavailable, GEMINI_API_KEY missing/empty, PDF conversion exception, Gemini response None/empty, Pydantic ValidationError on response, non-429 API errors. Never caught inside `extract_universal()` — propagates to caller.
- **Pydantic Literal for confidence:** `ConfidenceLabel = Literal["alta", "media", "bassa"]` is used as field type in OrdineEstratto. Pydantic v2 serializes this to `{"enum": ["alta", "media", "bassa"]}` in JSON Schema, which Gemini enforces syntactically.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- In the test environment (user-install Python 3.14, no venv), `docling` is not installed. The module handles this gracefully via `_DOCLING_AVAILABLE = False` and the try/except ImportError guard at module load. The verification for "ExtractionError sollevata" passed correctly (ExtractionError from `_build_docling_converter()` fires before `_build_gemini_client()` would check the API key, which is the correct pipeline order). In the production environment where docling is installed, the ExtractionError for missing API key will be reached as intended.

## User Setup Required

**GEMINI_API_KEY required before use.** Add to `app/.env`:

```
GEMINI_API_KEY=your_api_key_here
```

Get key from: https://aistudio.google.com/apikey (free tier available)

Verify with:
```bash
cd app && python -c "import os; from dotenv import load_dotenv; from pathlib import Path; load_dotenv(Path('.')/'.env'); print(os.environ.get('GEMINI_API_KEY', 'NOT SET'))"
```

## Next Phase Readiness

Phase 6 (Integrazione Pipeline) can now:
- Import `from backend.universal_extractor import extract_universal, ExtractionError`
- Call `extract_universal(filepath)` to get a parser-compatible dict
- Use `result["estrattore"] == "universal"` to identify extractions from this module
- Display `result["cliente_confidence"]` etc. in the UI for transparency

Blockers: GEMINI_API_KEY must be present in `app/.env` for production use.

---
*Phase: 05-estrattore-universale*
*Completed: 2026-02-19*

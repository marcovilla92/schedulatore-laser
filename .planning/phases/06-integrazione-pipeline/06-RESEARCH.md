# Phase 6: Integrazione Pipeline - Research

**Researched:** 2026-02-20
**Domain:** Flask pipeline integration, graceful degradation, confidence UI indicators
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PIPE-01 | La pipeline di parsing usa l'estrattore universale come primo tentativo; i parser specifici esistenti rimangono disponibili come fallback per i 16 formati noti | Integration point is `extract_pdf_content()` in `pdf_parser.py` and the `/api/extract-pdf-data` endpoint in `app.py`. Universal extractor wraps with try/except ExtractionError, then falls back to existing pipeline. |
| PIPE-02 | Nella pagina ordini estratti, i campi con confidenza bassa sono evidenziati visivamente così l'utente sa cosa verificare manualmente | API response must pass through `_confidence` fields. `ordini_estratti.html` already has amber/red CSS variables. Confidence badges render per-field using existing inline style pattern. |
| PIPE-03 | Se Gemini API non è raggiungibile, il sistema cade in fallback sui parser esistenti senza errori bloccanti per l'utente | `ExtractionError` is the typed exception from `universal_extractor.py`. Catching it in the integration layer + logging + falling back is the pattern. The `.env` is NOT currently loaded when Flask runs — this gap must be fixed in `run.py`. |
</phase_requirements>

---

## Summary

Phase 6 integrates `universal_extractor.py` (built in Phase 5) into the existing parsing pipeline as the default extraction path, with the existing format-specific parsers remaining as fallback. The work spans three concerns: (1) backend pipeline wiring, (2) `.env` loading at Flask startup, and (3) frontend UI confidence indicators.

The backend integration is a localized change. The single call site is the `/api/extract-pdf-data` endpoint in `app.py` (line 250: `pdf_data = extract_pdf_content(filepath)`). The strategy is to wrap `extract_universal()` in the `extract_pdf_data` route before delegating to `extract_pdf_content()`. On `ExtractionError`, fall through to `extract_pdf_content()` and log the reason. No changes are needed in `pdf_parser.py` itself.

A critical gap exists: `GEMINI_API_KEY` is in `app/.env` but neither `run.py` nor `start_backend.py` call `load_dotenv()`. The `universal_extractor.py` only loads `.env` in its `__main__` block (CLI mode). When called as a library from Flask, `os.environ.get("GEMINI_API_KEY")` will return `None`, causing `ExtractionError("GEMINI_API_KEY non configurata")`. This must be fixed by adding `load_dotenv` in `run.py` before Flask starts. This is the most important prerequisite for PIPE-03.

The frontend change is self-contained: `ordini_estratti.html` already has the design system (amber `--accent-amber`, red `--accent-red`, CSS variables) and the table rendering logic in `displayOrders()`. The response from `/api/extract-pdf-data` must include the `_confidence` fields so the frontend can render per-field badges. The current response structure wraps extraction data in `data.data` — the `_confidence` fields from `universal_extractor.py` are already included in that dict, they just need to be surfaced in the UI.

**Primary recommendation:** Wire `extract_universal()` in `app.py`'s `extract_pdf_data` route with try/except, fix `.env` loading in `run.py`, pass `_confidence` fields through to the frontend JSON response, and add amber border/badge CSS for low-confidence fields in `ordini_estratti.html`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `python-dotenv` | 1.0.0 | Load `app/.env` into `os.environ` at Flask startup | Already in `requirements.txt`; used in test scripts |
| `universal_extractor.ExtractionError` | (internal) | Typed exception for all universal extractor failures | Already defined in Phase 5; catching it is the fallback trigger |
| Flask `jsonify` | 2.3.2 | Return JSON responses from `/api/extract-pdf-data` | Already the pattern in `app.py` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `google-genai` | latest | Gemini API client | Already installed; used by `universal_extractor.py` internally |
| `docling` | 2.2.0 | PDF-to-Markdown conversion | Already installed; used by `universal_extractor.py` internally |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Modifying `app.py` endpoint | Modifying `extract_pdf_content()` in `pdf_parser.py` | Modifying `pdf_parser.py` would mix pipeline logic with format detection; `app.py` is the correct integration boundary |
| `load_dotenv` in `run.py` | Environment variable set in OS/shell | `run.py` approach is self-contained, consistent with how `test_universal_extractor.py` works, no user setup required |

**Installation:** All dependencies already in `requirements.txt`. No new packages needed.

---

## Architecture Patterns

### Recommended Integration Structure

The existing code paths to understand:

```
POST /api/extract-pdf-data
  └── app.py:extract_pdf_data()          ← INTEGRATION POINT
        └── extract_pdf_content()         ← existing pipeline
              └── detect_pdf_format()
              └── extract_for_ordine() | extract_oafa() | ... | extract_generic_intelligent()
```

After Phase 6, the call chain becomes:

```
POST /api/extract-pdf-data
  └── app.py:extract_pdf_data()
        ├── TRY: extract_universal()      ← NEW (first attempt)
        │     └── Docling + Gemini        ← returns dict with _confidence fields
        └── EXCEPT ExtractionError:
              ├── log reason              ← console only, NOT shown to user
              └── extract_pdf_content()  ← existing fallback (unchanged)
```

### Pattern 1: Try/Except Fallback in Endpoint

**What:** Wrap `extract_universal()` in the Flask route with `except ExtractionError`. On failure, silently fall back to `extract_pdf_content()`. Log the failure reason to stdout (same pattern as existing `print()` logging throughout `app.py`).

**When to use:** Any time the universal extractor might fail — API key missing, Gemini unreachable, Docling not installed, malformed response.

**Example:**

```python
# In app.py, inside extract_pdf_data() after file is saved to filepath:

# Source: Phase 5 contract — extract_universal raises ExtractionError on failure
from .universal_extractor import extract_universal, ExtractionError

try:
    print(f"   -> Tentativo estrattore universale...")
    pdf_data = extract_universal(filepath)
    print(f"   OK Estrattore universale: estrattore={pdf_data.get('estrattore')}")
except ExtractionError as e:
    print(f"   [FALLBACK] Estrattore universale non disponibile: {e}")
    print(f"   -> Ricado sui parser esistenti...")
    pdf_data = extract_pdf_content(filepath)

# Continue with existing post-processing (quantita_totale, etc.)
```

**Critical:** The import of `extract_universal` and `ExtractionError` must be at the top of `app.py` or inside the function — NOT at module level if Docling might not be installed (to avoid import-time crash). Safe approach: import inside the `try` block or at function level.

### Pattern 2: load_dotenv at Flask Startup

**What:** Add `load_dotenv` call in `run.py` before Flask app import, so `GEMINI_API_KEY` is in `os.environ` when `extract_universal()` calls `os.environ.get("GEMINI_API_KEY")`.

**When to use:** Every Flask startup. This is the fix for PIPE-03.

**Example:**

```python
# In run.py, BEFORE "from backend.app import app":
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")  # Loads app/.env
```

**Path note:** `run.py` is at `app/run.py`. The `.env` is at `app/.env`. So `Path(__file__).parent / ".env"` is correct — same pattern used in `test_universal_extractor.py` (line 45).

### Pattern 3: Confidence Field Pass-Through in API Response

**What:** The `/api/extract-pdf-data` endpoint currently returns `{'success': True, 'data': pdf_data}`. When `pdf_data` comes from `extract_universal()`, it already contains `cliente_confidence`, `numero_ordine_confidence`, `data_consegna_confidence`, `articoli_confidence`, and `estrattore="universal"`. These fields pass through automatically since the response wraps the whole dict.

**When to use:** No change needed in response structure. Frontend reads `data.data.cliente_confidence` etc.

**Example of what the frontend receives when universal extractor succeeds:**

```json
{
  "success": true,
  "data": {
    "cliente": "DIVISIONE CUCINE S.R.L.",
    "cliente_confidence": "alta",
    "numero_ordine": "300000946",
    "numero_ordine_confidence": "alta",
    "data_consegna": "2026-03-15T00:00:00",
    "data_consegna_confidence": "media",
    "articoli": [...],
    "articoli_confidence": "alta",
    "estrattore": "universal",
    "quantita_totale": 12.0,
    "data_ricezione": "2026-02-20T09:00:00"
  }
}
```

**When fallback parser runs:** Response has no `_confidence` fields and no `estrattore` field. Frontend must handle missing confidence gracefully (treat as "alta" or no badge).

### Pattern 4: Confidence Visual Indicators in ordini_estratti.html

**What:** In the `displayOrders()` function in `ordini_estratti.html`, render a confidence badge next to fields extracted by the universal extractor. Low confidence ("bassa") fields get amber/warning styling using existing CSS variables.

**The existing design system already has:**
- `--accent-amber: #ffa502` — amber color for warnings
- `--accent-red: #ff4757` — red for errors
- `.badge.success` / `.badge.error` — badge CSS already defined
- CSS `--transition`, `backdrop-filter: blur(10px)` — established patterns

**Confidence badge HTML pattern** (consistent with existing badge style):

```html
<!-- For "bassa" confidence -->
<span class="confidence-badge confidence-bassa" title="Verificare manualmente">
  ! bassa
</span>

<!-- For "media" confidence -->
<span class="confidence-badge confidence-media">
  ~ media
</span>

<!-- "alta" = no badge (don't clutter) -->
```

**CSS to add inline in `<style>` block:**

```css
.confidence-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.3px;
    margin-left: 6px;
    vertical-align: middle;
}
.confidence-bassa {
    background: rgba(255, 165, 2, 0.15);
    color: var(--accent-amber);
    border: 1px solid rgba(255, 165, 2, 0.3);
}
.confidence-media {
    background: rgba(0, 212, 255, 0.08);
    color: var(--accent-cyan);
    border: 1px solid rgba(0, 212, 255, 0.15);
}
```

**Where to show confidence:** In the table row for each order — attach badge to the "Cliente" cell and "N. Ordine" cell (highest user-facing value). For "Data Consegna", if confidence is bassa show amber styling on the date cell itself.

**The table row template** in `displayOrders()` currently builds string template literals. Confidence badges slot into the template without restructuring.

### Pattern 5: Fallback Notification in UI (PIPE-03)

**What:** When universal extractor is unavailable and fallback parser runs, optionally show a non-blocking informational message. This must NOT be an error — just an informational banner or status indicator.

**Implementation options** (choose one):
1. Return `estrattore: "legacy"` in the response dict when fallback runs, and show a subtle note in the UI
2. Add a non-blocking status message via the existing `showStatus()` function with type `"loading"` (purple, subtle) for a few seconds, then auto-hide

**Recommendation:** Use option 2 at the API response level — when `pdf_data.get('estrattore')` is absent or `!= 'universal'`, call `showStatus('Usati parser classici (Gemini non disponibile)', 'loading')` for 4 seconds, auto-dismiss. This matches the existing status pattern exactly.

### Anti-Patterns to Avoid

- **Importing `extract_universal` at module top in `app.py`:** If Docling is not installed, the import chain `from .universal_extractor import ...` would succeed (the module handles the ImportError internally), but the module-level import of `google.genai` would fail if `google-genai` is not installed. Safe approach: import at function level inside `try`.

  Actually — reading `universal_extractor.py` again: `from google import genai` is at the module top (line 31), not guarded. If `google-genai` is not installed, importing `universal_extractor` raises `ImportError`. Therefore the import of `universal_extractor` itself must be wrapped in try/except ImportError as an outer guard, separate from `ExtractionError`.

- **Showing "Gemini non disponibile" as a blocking error:** PIPE-03 explicitly says no blocking errors. The message must be informational only.

- **Modifying `extract_pdf_content()` in `pdf_parser.py`:** The correct integration boundary is `app.py`. `pdf_parser.py` should remain unchanged — it is the fallback, not the integration point.

- **Storing `estrattore` field in the database:** The `articles` column in the `orders` table is JSON, but `estrattore` is metadata about extraction — not order data. Don't persist it; it's only needed during the upload flow.

- **Showing confidence indicators for orders loaded from database:** `ordini_estratti.html` also loads orders via `GET /api/extracted-orders` (the `loadOrders()` function). Those orders come from the database and have no `_confidence` fields. Confidence display must be limited to the immediate upload response, not the order list.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Loading `.env` at startup | Manual file parsing | `python-dotenv` `load_dotenv()` | Already in `requirements.txt`; handles edge cases (quoting, encoding) |
| Retry logic for Gemini | Custom retry loop | Already in `_call_gemini_with_retry()` | Phase 5 built it with exponential backoff for 429; don't duplicate |
| Confidence level comparison | String comparison logic | Direct `== "bassa"` check | Only 3 values ("alta", "media", "bassa"); no library needed |
| Exception type checking | `isinstance()` on base `Exception` | `except ExtractionError` | Phase 5 already defined the typed exception |

**Key insight:** All complex logic (retry, Docling, Gemini schema validation, confidence assignment) lives in `universal_extractor.py`. Phase 6 is pure integration plumbing — the complexity ceiling is low.

---

## Common Pitfalls

### Pitfall 1: GEMINI_API_KEY Not Available at Runtime

**What goes wrong:** `extract_universal()` raises `ExtractionError("GEMINI_API_KEY non configurata")`. The fallback catches it and runs the legacy parser — which works. But the user never gets universal extraction even when Gemini is available. This happens silently.

**Why it happens:** `run.py` does not call `load_dotenv()`. `app/.env` is never loaded into `os.environ`. So `os.environ.get("GEMINI_API_KEY")` returns `None` every time.

**How to avoid:** Add `load_dotenv(Path(__file__).parent / ".env")` in `run.py` BEFORE importing `from backend.app import app`. Verified: `python-dotenv==1.0.0` is already in `requirements.txt`.

**Warning signs:** Console shows `[FALLBACK] Estrattore universale non disponibile: GEMINI_API_KEY non configurata` on every PDF upload.

### Pitfall 2: ImportError on `universal_extractor` Import

**What goes wrong:** `from .universal_extractor import extract_universal, ExtractionError` at the top of `app.py` raises `ImportError` if `google-genai` is not installed, crashing Flask startup.

**Why it happens:** `universal_extractor.py` imports `from google import genai` at module level (line 31), not in a try/except. If `google-genai` is missing, importing the module raises `ModuleNotFoundError`.

**How to avoid:** Wrap the import inside the Flask route function with `try/except ImportError`:

```python
try:
    from .universal_extractor import extract_universal, ExtractionError as UniversalExtractionError
    _UNIVERSAL_AVAILABLE = True
except ImportError:
    _UNIVERSAL_AVAILABLE = False
```

Then check `_UNIVERSAL_AVAILABLE` before calling `extract_universal()`. Note: `google-genai` IS in `requirements.txt`, so this is a safety net, not primary flow.

**Warning signs:** Flask fails to start with `ModuleNotFoundError: No module named 'google.genai'`.

### Pitfall 3: Confidence Fields Shown for Legacy-Extracted Orders in the Order List

**What goes wrong:** The `loadOrders()` function fetches all orders from `/api/extracted-orders`. Those orders come from the database and have no `_confidence` fields. If the confidence rendering code assumes these fields are present, it will show `undefined` or broken badges.

**Why it happens:** Two separate flows use the same `displayOrders()` function: the order list (no confidence) and the upload result (has confidence).

**How to avoid:** Only show confidence badges in the upload response display (the immediate feedback after PDF upload), not in the full order table. Or: in `displayOrders()`, guard confidence rendering with `if (order.cliente_confidence) {...}`.

**Warning signs:** Table cells show "undefined" or empty badge elements.

### Pitfall 4: `extract_universal()` Called with Relative Path

**What goes wrong:** Docling's `converter.convert(filepath)` might fail or behave unexpectedly with relative paths on Windows.

**Why it happens:** Flask runs from `app/` directory. The `filepath` constructed in `extract_pdf_data()` (line 241: `os.path.join(PDFS_FOLDER, file.filename)`) is absolute — `PDFS_FOLDER` uses `os.path.dirname(__file__)` which gives an absolute path. This is already correct.

**How to avoid:** No action needed — the existing `filepath` construction is already absolute.

**Warning signs:** `ExtractionError: Errore Docling su ./uploads/pdfs/...`

### Pitfall 5: `process-pdfs` Endpoint Also Needs Universal Extractor

**What goes wrong:** The `/api/process-pdfs` endpoint (line 324: `pdf_data = extract_pdf_content(pdf_path)`) bypasses the universal extractor. The batch-processing path never uses Gemini.

**Why it happens:** Two separate call sites call `extract_pdf_content()` directly. Phase 6 requirements (PIPE-01, PIPE-02, PIPE-03) are written in terms of "caricando un PDF" — the success criteria mention the ordini_estratti page specifically.

**How to avoid:** Phase 6 success criteria focus on the single-PDF upload flow. The batch `process-pdfs` endpoint can be updated in a future phase. Document this explicitly in the plan. Do NOT try to refactor both endpoints in Phase 6 — keep scope tight.

---

## Code Examples

### Integration in `app.py` — Full Pattern

```python
# Source: Pattern derived from Phase 5 contract (universal_extractor.py lines 69-74, 410-440)

# At module level (after existing imports):
try:
    from .universal_extractor import extract_universal, ExtractionError as UniversalExtractionError
    _UNIVERSAL_EXTRACTOR_AVAILABLE = True
except ImportError as _e:
    _UNIVERSAL_EXTRACTOR_AVAILABLE = False
    print(f"[INFO] Estrattore universale non disponibile: {_e}")

# Inside extract_pdf_data() route, after file is saved to filepath:
if _UNIVERSAL_EXTRACTOR_AVAILABLE:
    try:
        print(f"   -> Estrattore universale (Docling + Gemini)...")
        sys.stdout.flush()
        pdf_data = extract_universal(filepath)
        print(f"   OK Estrattore universale: {len(pdf_data.get('articoli', []))} articoli")
        sys.stdout.flush()
    except UniversalExtractionError as exc:
        print(f"   [FALLBACK] Universale non disponibile: {exc}")
        print(f"   -> Parser classici in uso...")
        sys.stdout.flush()
        pdf_data = extract_pdf_content(filepath)
else:
    pdf_data = extract_pdf_content(filepath)
```

### `load_dotenv` in `run.py`

```python
# Source: Pattern from test_universal_extractor.py (line 44-45) adapted for run.py

# Add BEFORE "from backend.app import app":
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")  # Carica app/.env
```

### Confidence Badge in `ordini_estratti.html` — `displayOrders()` segment

```javascript
// Source: Extend existing template literal in displayOrders()

function confidenceBadge(level) {
    if (!level || level === 'alta') return '';
    const label = level === 'bassa' ? '! bassa' : '~ media';
    return `<span class="confidence-badge confidence-${level}"
                  title="Confidenza ${level} — verificare manualmente">${label}</span>`;
}

// In the row template (example for cliente cell):
`<td><strong>${order.cliente || 'Sconosciuto'}</strong>${confidenceBadge(order.cliente_confidence)}</td>`
```

### Upload Response Handling — Show Fallback Message

```javascript
// In processAllPDFs() or uploadPDF() fetch .then(), after displaying results:
// When universal extractor was not used, data.data.estrattore is absent
if (data.data && data.data.estrattore !== 'universal') {
    showStatus('Estrazione classica (Gemini non disponibile)', 'loading');
    setTimeout(() => {
        document.getElementById('status').style.display = 'none';
    }, 4000);
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-path pipeline (`extract_pdf_content`) | Universal extractor first, format-specific parsers as fallback | Phase 6 | Newer/unknown PDF formats handled without parser development |
| No confidence indicators | Per-field confidence ("alta"/"media"/"bassa") | Phase 5+6 | User knows which fields to verify |
| No `.env` loading in Flask | `load_dotenv` at startup | Phase 6 | `GEMINI_API_KEY` available to all backend modules |

**Notes:**
- `GEMINI_MODEL = "gemini-2.0-flash"` — the comment in `universal_extractor.py` (line 62) warns this model retires 2026-03-31 (39 days from research date). Migration to `"gemini-2.5-flash"` is a 1-line change. This is outside Phase 6 scope but must be tracked.
- `ordini_estratti.html` currently has an upload drag-and-drop area for single PDF uploads (`welcome.html` has the main upload UI). The confidence display logic needs to integrate with whichever page calls `/api/extract-pdf-data`.

---

## Open Questions

1. **Where exactly is a single PDF uploaded via the frontend?**
   - What we know: `/api/extract-pdf-data` is the endpoint. `welcome.html` has a file upload area. `ordini_estratti.html` has `processAllPDFs()` which calls `/api/process-pdfs` (batch), not `/api/extract-pdf-data`.
   - What's unclear: The success criteria say "caricando un PDF nella pagina ordini estratti" — but the ordini_estratti page currently only has batch processing, not single-file upload with confidence display.
   - Recommendation: Add a single-file upload control to `ordini_estratti.html` that calls `/api/extract-pdf-data` and shows results with confidence badges. This is the correct implementation for PIPE-02. The planner should scope this explicitly.

2. **Should `estrattore` field be returned in the response to distinguish universal vs. legacy?**
   - What we know: `extract_universal()` returns `estrattore: "universal"`. The legacy `extract_pdf_content()` returns no `estrattore` field.
   - What's unclear: PIPE-03 says "messaggio informativo" when Gemini unavailable — does this need to be in the response JSON or just in UI logic?
   - Recommendation: Return `estrattore: "legacy"` explicitly when fallback runs by adding it to `pdf_data` after the except block. This makes the frontend logic simple: `if (data.estrattore !== 'universal') showFallbackMessage()`.

3. **Does the confidence display apply to orders already in the database?**
   - What we know: `_confidence` fields are NOT stored in the database (they're transient extraction metadata). The `GET /api/extracted-orders` endpoint returns orders from DB with no confidence data.
   - What's unclear: Whether PIPE-02 intends confidence display only for newly uploaded PDFs or for all orders.
   - Recommendation: Confidence display is only for the immediate upload response. Orders in the table (from DB) show no confidence badges. This is the only implementation that's technically feasible without schema changes.

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `app/backend/pdf_parser.py` — full pipeline, integration point identified at `extract_pdf_content()` call in `app.py`
- Direct code inspection: `app/backend/universal_extractor.py` — Phase 5 deliverable, `extract_universal()` signature and `ExtractionError` contract
- Direct code inspection: `app/backend/app.py` — `extract_pdf_data()` endpoint (lines 214-269), existing response structure
- Direct code inspection: `app/frontend/ordini_estratti.html` — existing CSS design system, `displayOrders()` JS function
- Direct code inspection: `app/run.py` — confirms `load_dotenv` is NOT called
- Direct code inspection: `app/requirements.txt` — confirms `python-dotenv==1.0.0` and `google-genai` are available
- Direct code inspection: `app/test_universal_extractor.py` — confirms `load_dotenv` pattern at line 44-45

### Secondary (MEDIUM confidence)
- `.planning/phases/05-estrattore-universale/05-VERIFICATION.md` — Phase 5 contract verification, confidence field structure confirmed

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies already installed and in `requirements.txt`
- Architecture: HIGH — direct code inspection of all integration points
- Pitfalls: HIGH — `.env` gap confirmed by code inspection; ImportError risk confirmed by reviewing module-level imports in `universal_extractor.py`
- UI patterns: HIGH — existing CSS design system inspected, confidence badge approach derived from existing `.badge` patterns

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (stable — no fast-moving dependencies; only risk is Gemini model retirement on 2026-03-31)

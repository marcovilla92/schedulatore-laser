# Phase 4: Audit Parser - Research

**Researched:** 2026-02-19
**Domain:** PDF parser audit, success rate measurement, Python scripting
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUDIT-01 | Il sistema esegue un test di estrazione su tutti i PDF nella cartella di test e produce un report con success rate per campo (cliente, numero_ordine, articoli, quantita, data_consegna) per ciascun formato noto | Pattern found in existing test scripts; field-level evaluation logic defined in research |
| AUDIT-02 | Il report identifica quali formati e quali campi specifici falliscono o producono dati incompleti/errati, fornendo una baseline misurabile | Per-field, per-format breakdown structure documented; known failure patterns already identified from existing test results |
</phase_requirements>

---

## Summary

Phase 4 requires a standalone audit script that calls the existing `extract_pdf_content()` dispatcher on every PDF in `C:\Users\39334\Documents\ORDINI` and produces a structured report. The task is essentially measurement, not implementation: no parser code is modified, and the script must produce a baseline that Phase 5 can compare against.

The existing codebase already has `test_all_16_final.py` and `batch_test_ordini.py` which do partial versions of this. However, those scripts use a binary pass/fail criterion (any cliente + any ordine + at least 1 article = OK). The audit script must go further: per-field success rates, per-format breakdowns, data quality indicators (empty strings, fallback values, wrong values), and a persistent report file.

The existing test run results file (`test_all_16_results.txt`) documents a 8/16 (50%) overall pass rate. The research below maps exactly which formats fail, which fields fail, and what the known root causes are. This allows the audit script to be written with the right evaluation logic from day one.

**Primary recommendation:** Write `app/audit_parsers.py` as a self-contained script that imports the existing dispatcher, evaluates each of the 5 target fields independently with clear PASS/FAIL/EMPTY/FALLBACK criteria, and writes a timestamped plain-text report with per-format and per-field success tables.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`pathlib`, `sys`, `time`, `datetime`, `json`) | 3.8+ | File discovery, timing, report generation | Zero additional dependencies |
| `app/backend/pdf_parser.py` | existing | `extract_pdf_content()` dispatcher entry point | Already wraps all 6+ format-specific parsers |
| `app/backend/pdf_parser.py` | existing | `detect_pdf_format()` utility | Reports detected format alongside extraction result |

### No new dependencies required
The audit script needs only Python stdlib + the existing backend package. All parsing libraries (PyPDF2, pdfplumber, Docling) are already installed and called indirectly through `extract_pdf_content()`.

**Installation:**
```bash
# No new packages. Run from app/ directory:
cd app
python audit_parsers.py --dir "C:/Users/39334/Documents/ORDINI"
```

---

## Architecture Patterns

### Recommended Project Structure
```
app/
├── audit_parsers.py          # New: standalone audit script
├── backend/
│   ├── pdf_parser.py         # Existing: entry point called by audit
│   └── parsers_*.py          # Existing: called internally (not touched)
└── audit_reports/            # Auto-created by script
    └── audit_YYYYMMDD_HHMMSS.txt
```

### Pattern 1: Calling the Existing Dispatcher Without Modifying It

**What:** Import `extract_pdf_content` and `detect_pdf_format` from the backend package using the same `sys.path` trick already used in `batch_test_ordini.py`.

**When to use:** Mandatory — the constraint says no existing parser code may be modified.

**Example:**
```python
# Source: app/batch_test_ordini.py (existing codebase pattern)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.pdf_parser import extract_pdf_content, detect_pdf_format
```

### Pattern 2: Per-Field Evaluation with Explicit Criteria

**What:** For each extracted field, apply a specific evaluation function that returns PASS, FAIL, EMPTY, or FALLBACK.

**When to use:** For every PDF in the test set. Each field needs its own definition of "success" because:
- `cliente`: empty string or known wrong value ("Spettabile", "L.S. SRL" when LS is the recipient) = FAIL
- `numero_ordine`: empty string = FAIL; non-empty = PASS (no ground-truth validation needed)
- `articoli`: count = 0 = FAIL; count > 0 = PASS (count is also reported)
- `quantita`: sum of article quantities; 0 when no articles = FAIL
- `data_consegna`: equals `datetime.now().isoformat()` prefix (i.e., fallback default) = FALLBACK not PASS

**Example:**
```python
# Source: research — derived from parser source code analysis
def evaluate_field(field_name, value, result):
    """Return PASS / FAIL / EMPTY / FALLBACK for a single extracted field."""
    if field_name == 'cliente':
        bad_values = {'', 'spettabile', 'l.s. srl', 'ls srl', 'cliente sconosciuto'}
        return 'FAIL' if str(value).strip().lower() in bad_values else 'PASS'

    elif field_name == 'numero_ordine':
        return 'FAIL' if not str(value).strip() else 'PASS'

    elif field_name == 'articoli':
        count = len(result.get('articoli', []))
        return 'PASS' if count > 0 else 'FAIL'

    elif field_name == 'quantita':
        qty = result.get('quantita_totale', 0)
        return 'PASS' if qty > 0 else 'FAIL'

    elif field_name == 'data_consegna':
        # Default fallback is datetime.now().isoformat() — detect by checking
        # if value matches today's date prefix (YYYY-MM-DD)
        today = datetime.now().strftime('%Y-%m-%d')
        return 'FALLBACK' if str(value).startswith(today) else 'PASS'
```

### Pattern 3: Per-Format Aggregation

**What:** Group results by detected format, then compute per-field success rates within each group.

**When to use:** Required by AUDIT-02. The detected format comes from calling `detect_pdf_format(text)` on the PyPDF2 text — but this requires re-extracting the text. Simpler: call `extract_pdf_content()` which already prints the detected format; capture it from the result dict by adding `format` key, OR derive it by calling `detect_pdf_format` separately on the raw text.

**Note:** `extract_pdf_content()` does NOT return the detected format in its result dict. The audit script must either:
- Option A: Call `detect_pdf_format()` separately after extracting PyPDF2 text (adds ~50ms per file, clean approach)
- Option B: Read the format from the filename heuristic (fragile)
- **Use Option A.** The function is already importable.

```python
# Source: research — derived from pdf_parser.py analysis
import PyPDF2

def get_pdf_format(filepath):
    """Detect format without going through full extraction."""
    try:
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ''.join(p.extract_text() or '' for p in reader.pages)
        return detect_pdf_format(text)
    except Exception:
        return 'UNKNOWN'
```

### Pattern 4: Plain-Text Report Generation

**What:** Write results to stdout AND to a timestamped file in `app/audit_reports/`.

**When to use:** Meets the requirement "leggibile senza strumenti speciali". Stdout satisfies immediate use; file provides the persistent baseline for Phase 5 comparison.

**Format:**
```
AUDIT PARSER BASELINE — 2026-02-19 14:30:00
============================================================
PDF Directory: C:\Users\39334\Documents\ORDINI
Total PDFs tested: 16
Total time: 12.4s

PER-FORMAT SUMMARY
------------------
Format            PDFs  cliente  numero_ordine  articoli  quantita  data_consegna
DIVISIONE            1   100%         100%        100%      100%         FALLBACK
FOR_ORDINE           5   100%         100%        100%      100%         FALLBACK
FOR_ORDINE_AZA       4     0%         100%          0%        0%         FALLBACK
OAFA                 1   100%         100%        100%      100%              100%
ORDINE_LS            4     0%           0%          0%        0%         FALLBACK
PO_BEBITALIA         1   100%         100%        100%      100%         FALLBACK
GENERIC              0     —            —           —         —               —

PER-FILE DETAIL
---------------
[OK]  300000946.pdf          DIVISIONE      cliente:PASS  ordine:PASS  articoli:13  qty:PASS  data:FALLBACK
[FAIL] ORDINE FORNITORE 57-AC  FOR_ORDINE_AZA  cliente:FAIL  ordine:PASS  articoli:0   qty:FAIL  data:FALLBACK
...
```

### Anti-Patterns to Avoid

- **Calling Flask app to extract PDFs:** The audit script must be standalone, not a server request. Import the backend modules directly.
- **Using the binary pass/fail metric from test_all_16_final.py:** That metric (cliente + ordine + >=1 article) hides field-level failures. The audit requires per-field evaluation.
- **Suppressing parser print output during audit:** The parsers print heavily to stdout. Redirect or suppress with `sys.stdout` redirect to avoid garbled audit output. However, keep parser errors visible.
- **Treating FALLBACK date as PASS:** When `data_consegna` returns `datetime.now()` it means the parser did not find a real date. This is a distinct status, not a success.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction | Custom PDF reader | `extract_pdf_content()` already does it | Dispatcher handles format detection + fallbacks |
| Format detection | Filename parsing | `detect_pdf_format(text)` | Already implemented with 6 marker-based rules |
| Article count | Re-parse articles | `result.get('articoli', [])` | Dispatcher already returns structured list |
| Quantity total | Sum individually | `result.get('quantita_totale', 0)` | Post-processed by dispatcher (Step 4 in `extract_pdf_content`) |

**Key insight:** The audit script is a measurement wrapper around existing code. Almost nothing needs to be built from scratch except the evaluation criteria and report formatter.

---

## Common Pitfalls

### Pitfall 1: Unicode Errors Crashing the Audit Loop

**What goes wrong:** The existing test run (`test_all_16_results.txt`) shows that `Ordine LS N°172.pdf`, `Ordine LS N°217.pdf`, `ORDINE LS.PDF`, and `ORDINE_D_ACQUISTO_21-28707_LS.pdf` crash with `UnicodeEncodeError: 'charmap' codec can't encode characters`. The `°` character in the filename cannot be encoded by Windows `cp1252` console. This propagates as an exception in `print()` inside the parser.

**Why it happens:** The parsers use `print()` without explicit encoding. On Windows, stdout defaults to `cp1252`. The `°` in filenames passed to print triggers the error.

**How to avoid:** Two-part fix in the audit script only (not in parsers):
1. Set `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` at script start (Python 3.7+)
2. Wrap each `extract_pdf_content()` call in `try/except Exception` and record the exception as a FAIL with its message

**Warning signs:** Any PDF with non-ASCII characters in its filename will trigger this on Windows.

### Pitfall 2: FOR_ORDINE_AZA PDFs Mis-Detected as FOR_ORDINE

**What goes wrong:** From the test results, `ORDINE FORNITORE 57-AC`, `83-AC`, `85-AC`, and `826-AC` are AZA-format PDFs but `detect_pdf_format()` returns `FOR_ORDINE` (not `FOR_ORDINE_AZA`). The AZA detection requires "AZA INTERNATIONAL" in the text, but these PDFs apparently do not contain that string (hence falling to FOR_ORDINE parser which fails to find articles).

**Why it happens:** The detection marker "AZA INTERNATIONAL" is not present in the PDF text because:
- The AZA company name appears only in a logo/image (not text layer), OR
- The text says "AZA" but not "AZA INTERNATIONAL" verbatim

**How to avoid in audit:** The audit script should report the detected format alongside the result. This mismatch is precisely the kind of insight the audit is designed to surface. Do NOT correct format detection in the audit script — that is Phase 5's job. Just record it accurately.

### Pitfall 3: Docling Disabled by Default in Test Mode

**What goes wrong:** `pdf_parser.py` line 28 has `DOCLING_AVAILABLE = False` with comment "TEMPORARILY DISABLED FOR TESTING". This means the Docling fallback path never runs during audit. The AZA PDFs therefore get 0 articles instead of potentially recovering via Docling.

**Why it happens:** The disable was added during v1.0 development to speed up test runs. It remains in place.

**How to avoid:** The audit script should NOT re-enable Docling. The audit measures the parser system as currently deployed (with Docling disabled). This is the accurate baseline. Document this in the report header: "Note: Docling fallback disabled (DOCLING_AVAILABLE=False in pdf_parser.py)".

### Pitfall 4: FOR_ORDINE parser returns "L.S. SRL" as Cliente (Wrong Direction)

**What goes wrong:** Several FOR_ORDINE PDFs return `cliente = "L.S. SRL"`. L.S. SRL is the destination (the shop receiving the order), not the ordering client. The parser extracts the wrong entity.

**Why it happens:** The FOR_ORDINE PDFs embed the client name only in the logo (image), not in extractable text. The parser falls back to any company-like string in the header, which happens to be L.S. SRL. The parsers_for_ordine.py uses hardcoded values for known order numbers (0000173, 0000205, 0000445, 0000537 → "Sozzi Arredamenti S.p.A."), but only for those 4 specific files.

**How to avoid in audit:** The evaluation criteria must explicitly classify "L.S. SRL" and "L.S. S.R.L." as FAIL for the cliente field, not PASS.

### Pitfall 5: quantita Field Not Directly in Return Dict

**What goes wrong:** Requirement AUDIT-01 specifies evaluating `quantita` as a field, but `extract_pdf_content()` returns `articoli` (list of dicts with individual `qty` fields) and `quantita_totale` (sum). There is no bare `quantita` field.

**Why it happens:** The original design chose article-level quantities over an order-level quantity field.

**How to avoid:** Map `quantita` in the audit to `quantita_totale` (which sums article quantities). PASS if > 0, FAIL if == 0. Document this mapping in the report.

### Pitfall 6: Script Runtime Must Stay Under 2 Minutes

**What goes wrong:** The existing test run with Docling enabled took much longer (Docling OCR ~30s per PDF). With Docling disabled, 16 PDFs at ~1s each = ~16 seconds total. The 2-minute constraint is easily met as long as Docling remains disabled.

**Warning sign:** If Docling gets re-enabled, audit time would exceed 8 minutes (30s x 16 PDFs). Add a timing check at the end and warn if over 90 seconds.

---

## Code Examples

Verified patterns from existing codebase:

### Correct Import Path for Standalone Script
```python
# Source: app/batch_test_ordini.py (existing)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.pdf_parser import extract_pdf_content, detect_pdf_format
```

### Iterating All PDFs in a Directory
```python
# Source: app/batch_test_ordini.py (existing)
from pathlib import Path

def find_pdfs(directory: str) -> list:
    """Finds all PDF files in directory (case-insensitive extension)."""
    d = Path(directory)
    return sorted(
        list(d.glob("*.pdf")) + list(d.glob("*.PDF"))
    )
```

### Safe Per-PDF Extraction with Exception Handling
```python
# Source: app/batch_test_ordini.py (existing pattern, extended)
import sys

def audit_pdf(filepath):
    try:
        result = extract_pdf_content(str(filepath))
        return result
    except Exception as e:
        return {'error': str(e), 'filepath': str(filepath), 'articoli': []}
```

### Detecting Format Separately from Extraction
```python
# Source: pdf_parser.py — detect_pdf_format() is exported
import PyPDF2
from backend.pdf_parser import detect_pdf_format

def get_format(filepath):
    try:
        with open(str(filepath), 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ''.join(p.extract_text() or '' for p in reader.pages)
        return detect_pdf_format(text)
    except Exception:
        return 'UNKNOWN'
```

### Suppressing Verbose Parser Output
```python
# Source: Python stdlib — redirect stdout during extraction
import io

def extract_quietly(filepath):
    """Call extract_pdf_content with parser print output suppressed."""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        result = extract_pdf_content(str(filepath))
    finally:
        sys.stdout = old_stdout
    return result
```

Note: Suppress stdout during individual extractions, then print audit progress explicitly. This avoids the 100+ lines of parser debug output drowning the audit report.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Binary pass/fail (existing tests) | Per-field, per-format success rates | Phase 4 (now) | Produces actionable data for Phase 5 |
| Ad-hoc test scripts (test_all_16_final.py) | Structured audit with persistent baseline file | Phase 4 (now) | Enables before/after comparison for Phase 5 |
| Docling enabled (original dev) | Docling disabled via flag | Sometime during v1.0 testing | Faster tests, but AZA format gets 0 articles with no fallback |

**Known failures from existing test run (test_all_16_results.txt, 2026-02-17):**
- `ORDINE FORNITORE 57-AC`: FOR_ORDINE_AZA format detected as FOR_ORDINE, 0 articles, cliente = "Spettabile"
- `ORDINE FORNITORE 83-AC`: Same as 57-AC
- `ORDINE FORNITORE 85-AC`: Same as 57-AC
- `ORDINE FORNITORE 826-AC`: Same as 57-AC
- `Ordine LS N°172.pdf`: UnicodeEncodeError crash (° character in filename)
- `Ordine LS N°217.pdf`: Same Unicode crash
- `ORDINE LS.PDF`: Same Unicode crash (° in parser print output)
- `ORDINE_D_ACQUISTO_21-28707_LS.pdf`: Same Unicode crash

Confirmed working (8/16):
- `300000946.pdf` (DIVISIONE): 13 articles, cliente = L.S. SRL (wrong but non-empty), ordine OK
- `FOR-ORDINE 0000173/205/445/537` (FOR_ORDINE): hardcoded cliente, 1-3 articles each
- `OAFA202600125.pdf` (OAFA): 16 articles, all fields OK
- `OF_260100` (FOR_ORDINE): 4 articles, all fields OK
- `PO_20250006705-3.pdf` (PO_BEBITALIA): 2 articles, all fields OK

---

## Open Questions

1. **Ground truth for article counts per format**
   - What we know: We know extracted counts (0-16 per PDF). We do not know the actual expected counts from the real PDF content.
   - What's unclear: We cannot distinguish "parser extracted fewer articles than exist" from "parser extracted all articles" without manually counting each PDF.
   - Recommendation: The audit script should report raw extracted counts, not a correctness ratio for article count. Flag "0 articles" as definite FAIL; any non-zero count as PASS (count is also shown). Phase 5 improvements will reveal true counts.

2. **ORDINE_D_ACQUISTO_21-28707_LS format**
   - What we know: Currently crashes with UnicodeEncodeError and no format is detected before crash.
   - What's unclear: Once Unicode is fixed, what format will it detect as? Likely GENERIC or ORDINE_LS.
   - Recommendation: Fix Unicode in the audit loop; let the format detection run and report it.

3. **FOR_ORDINE DIVISIONE cliente = "L.S. SRL"**
   - What we know: DIVISIONE returns cliente = "L.S. SRL" (the destination, not the client). This technically satisfies the existing test's binary criterion but is semantically wrong.
   - What's unclear: Is there a way to validate correctness without ground truth?
   - Recommendation: Mark "L.S. SRL" as FAIL for cliente field. The evaluation criteria section defines this as a known bad value.

---

## Known State of the 16 PDFs (Pre-Audit Prediction)

Based on code analysis and `test_all_16_results.txt`:

| PDF File | Detected Format | cliente | ordine | articoli | data_consegna | Overall |
|----------|----------------|---------|--------|----------|---------------|---------|
| 300000946.pdf | DIVISIONE | FAIL (L.S. SRL) | PASS | PASS (13) | FALLBACK | PARTIAL |
| FOR-ORDINE_0000173 | FOR_ORDINE | PASS (hardcoded) | PASS | PASS (1) | FALLBACK | PARTIAL |
| FOR-ORDINE_0000205 | FOR_ORDINE | PASS (hardcoded) | PASS | PASS (3) | FALLBACK | PARTIAL |
| FOR-ORDINE_0000445 | FOR_ORDINE | PASS (hardcoded) | PASS | PASS (1) | FALLBACK | PARTIAL |
| FOR-ORDINE_0000537 | FOR_ORDINE | PASS (hardcoded) | PASS | PASS (1) | FALLBACK | PARTIAL |
| OAFA202600125.pdf | OAFA | PASS | PASS | PASS (16) | PASS | FULL |
| OF_260100 | FOR_ORDINE | FAIL (L.S. SRL) | PASS | PASS (4) | FALLBACK | PARTIAL |
| ORDINE FORNITORE 57-AC | FOR_ORDINE (mis-detected) | FAIL | PASS | FAIL (0) | FALLBACK | FAIL |
| ORDINE FORNITORE 83-AC | FOR_ORDINE (mis-detected) | FAIL | PASS | FAIL (0) | FALLBACK | FAIL |
| ORDINE FORNITORE 85-AC | FOR_ORDINE (mis-detected) | FAIL | PASS | FAIL (0) | FALLBACK | FAIL |
| ORDINE FORNITORE 826-AC | FOR_ORDINE (mis-detected) | FAIL | PASS | FAIL (0) | FALLBACK | FAIL |
| Ordine LS N°172.pdf | CRASH (Unicode) | — | — | — | — | CRASH |
| Ordine LS N°217.pdf | CRASH (Unicode) | — | — | — | — | CRASH |
| ORDINE LS.PDF | CRASH (Unicode) | — | — | — | — | CRASH |
| ORDINE_D_ACQUISTO_21-28707_LS.pdf | CRASH (Unicode) | — | — | — | — | CRASH |
| PO_20250006705-3.pdf | PO_BEBITALIA | PASS | PASS | PASS (2) | PASS | FULL |

**Predicted baseline (after Unicode crash fix):**
- articoli PASS: 8/16 (50%)
- cliente PASS: 5/16 (31%) — only the 4 hardcoded FOR_ORDINE + OAFA
- numero_ordine PASS: ~12/16 (75%)
- data_consegna real (non-fallback): 2/16 (12%) — only OAFA and PO_BEBITALIA

---

## Sources

### Primary (HIGH confidence)
- `app/backend/pdf_parser.py` — Full dispatcher code read, format detection logic understood
- `app/backend/parsers_for_ordine.py` — Article extraction patterns, cliente hardcoding logic
- `app/backend/parsers_oafa.py` — Article extraction pattern (regex on `25XX...` codes)
- `app/backend/parsers_divisione.py` — DIVISIONE format patterns
- `app/backend/parsers_po_bebitalia.py` — B&B Italia patterns
- `app/backend/parsers_for_ordine_aza.py` — AZA format patterns
- `app/backend/parsers_ordine_ls.py` — LS format patterns, Docling fallback usage
- `app/backend/parsers_generic.py` — Generic fallback patterns
- `app/test_all_16_results.txt` — Actual test run output, 8/16 success, specific failures documented
- `app/test_all_16_final.py` — Reference implementation for PDF list and binary evaluation
- `app/batch_test_ordini.py` — Reference implementation for dynamic PDF discovery

### Secondary (MEDIUM confidence)
- `C:\Users\39334\Documents\ORDINI\` directory listing — 16 PDFs confirmed present, filenames with `°` characters confirmed

---

## Metadata

**Confidence breakdown:**
- Known failures: HIGH — from actual test run output in `test_all_16_results.txt`
- Field evaluation criteria: HIGH — derived directly from parser source code reading
- Format detection logic: HIGH — read from `detect_pdf_format()` source
- Predicted baseline numbers: MEDIUM — prediction based on code analysis, actual audit may reveal edge cases
- Timing estimate: HIGH — 16 PDFs at ~1s each with Docling disabled is well under 2 minutes

**Research date:** 2026-02-19
**Valid until:** Stable — parsers are not changing in this phase. Valid until Phase 5 modifies them.

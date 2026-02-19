---
phase: 05-estrattore-universale
plan: 02
subsystem: testing
tags: [universal-extractor, validation, baseline-comparison, docling, gemini, pdf-extraction, cli]

# Dependency graph
requires:
  - phase: 04-audit-parser
    provides: baseline extraction accuracy metrics (cliente 87%, data_consegna 81%, ordine 100%, articoli 100%) used as comparison target
  - phase: 05-estrattore-universale/05-01
    provides: app/backend/universal_extractor.py — the module under validation
provides:
  - app/test_universal_extractor.py — standalone validation script comparing universal_extractor results vs Phase 4 baseline
  - Checkpoint: user-confirmed success rate >= Phase 4 baseline on all 4 fields
affects:
  - 06-integrazione-pipeline: validation evidence that universal_extractor is production-ready

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Baseline comparison pattern: BASELINE_PHASE4 dict hardcoded with Phase 4 rates, per-field success rate computed and delta printed
    - PDF deduplication: set() on filenames without directory path (32 files = 16 duplicates in ORDINI folder)
    - Windows encoding fix: sys.stdout.reconfigure(encoding='utf-8', errors='replace') at top of script
    - Fallback date detection: data_consegna treated as FALLBACK if value starts with today's date prefix

key-files:
  created:
    - app/test_universal_extractor.py (498 lines)
  modified: []

key-decisions:
  - "Baseline hardcoded in script (not read from audit_reports JSON) — avoids coupling to audit report format changes"
  - "ExtractionError per single PDF: logged and skipped, batch continues — validated behavior allows partial results on API quota exhaustion"
  - "User-approved checkpoint confirms universal_extractor success rate meets or exceeds Phase 4 baseline on real production PDFs"

patterns-established:
  - "Pattern: CLI validation script with --dir arg — portable, can be run on any PDF directory without code changes"
  - "Pattern: 4-section report (per-campo, per-file, analisi-confidence, confronto-baseline) — reusable structure for future extractor comparisons"

requirements-completed: [EXTR-04]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 5 Plan 2: Validazione Estrattore Universale Summary

**Validation script comparing universal_extractor Docling+Gemini results against Phase 4 regex baseline (87% cliente, 81% data_consegna), user-confirmed success rate >= baseline on all 16 production PDF orders**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-19T15:05:00Z
- **Completed:** 2026-02-19T14:12:49Z
- **Tasks:** 2 (1 auto + 1 checkpoint:human-verify)
- **Files modified:** 1

## Accomplishments

- Created `app/test_universal_extractor.py` (498 lines) — standalone validation script with baseline comparison
- Script processes 16 deduped PDFs from `C:\Users\39334\Documents\ORDINI`, handles 32-file duplicates via set() deduplication
- User ran script and confirmed checkpoint: success rate >= Phase 4 baseline (cliente >= 87%, data_consegna >= 81%), ORDINE_LS improved from 50%
- 4-section structured report: RISULTATI PER CAMPO, RISULTATI PER FILE, ANALISI CONFIDENCE, CONFRONTO BASELINE with explicit SUCCESS/ATTENZIONE verdict

## Task Commits

Each task was committed atomically:

1. **Task 1: Creare script di validazione test_universal_extractor.py** - `35d7f5b` (feat)
2. **Task 2: Verifica validazione universal_extractor vs baseline Phase 4** - checkpoint:human-verify (no code commit — user verification)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified

- `app/test_universal_extractor.py` - Validation and baseline comparison script: loads GEMINI_API_KEY from app/.env, iterates deduplicated PDFs, calls extract_universal(), computes 4-field success rates, compares to BASELINE_PHASE4, prints structured 4-section report, exits with SUCCESS or ATTENZIONE verdict

## Decisions Made

- **Baseline hardcoded:** `BASELINE_PHASE4 = {"cliente": 0.87, "numero_ordine": 1.00, "data_consegna": 0.81, "articoli": 1.00}` — avoids coupling to audit report file format
- **Fallback date detection:** data_consegna is counted as failed if value starts with `datetime.now().strftime('%Y-%m-%d')` — the universal_extractor default fallback value
- **Batch continues on error:** ExtractionError for a single PDF prints the error and continues — allows partial results on API quota exhaustion or corrupt PDFs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — script syntax-checked cleanly, checkpoint approved by user after successful batch run.

## User Setup Required

**GEMINI_API_KEY required in `app/.env` before running the script.** Already documented in Phase 5 Plan 1 summary.

Verification:
```bash
cd app
python test_universal_extractor.py
```

Optional debug mode for single PDF:
```bash
python backend/universal_extractor.py "C:\Users\39334\Documents\ORDINI\<pdf>.pdf" --debug
```

## Next Phase Readiness

Phase 6 (Integrazione Pipeline) can proceed:
- `extract_universal()` is validated on all 16 production PDF formats
- Success rate meets Phase 4 baseline threshold on all key fields
- ORDINE_LS format (previously 50% on cliente/data_consegna) confirmed improved
- Integration point: `from backend.universal_extractor import extract_universal, ExtractionError`

No blockers. GEMINI_API_KEY already set in `app/.env` (confirmed by checkpoint run).

---
*Phase: 05-estrattore-universale*
*Completed: 2026-02-19*

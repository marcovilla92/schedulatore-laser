# Project State — Schedulatore Laser

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Operators see what needs processing next and track completion in real-time
**Current focus:** Milestone v1.2 — Phase 5: Estrattore Universale

## Current Position

Phase: 5 of 6 (Estrattore Universale)
Plan: 2 of 2 in current phase — COMPLETE
Status: Phase 5 complete — universal_extractor validato su 16 PDF reali, success rate >= baseline Phase 4 (cliente 87%, data_consegna 81%)
Last activity: 2026-02-19 — test_universal_extractor.py (498 righe), checkpoint approvato dall'utente

Progress: [█████░░░░░] 50%

## Performance Metrics

**Velocity:**
- Total plans completed: 1
- Average duration: 3 min
- Total execution time: 0.05 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 4. Audit Parser | 1/1 | — | — |
| 5. Estrattore Universale | 2/2 | 8 min | 4 min |
| 6. Integrazione Pipeline | 0/0 | — | — |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Recent decisions affecting current work:

- v1.2: Gemini 2.0 Flash scelto come LLM per estrazione universale (free tier, server ha internet)
- v1.2: Docling gia nel progetto — usato come layer PDF-to-text prima di Gemini
- v1.0: flag_modified() necessario per mutazioni JSON in SQLAlchemy
- v1.0: 50MB upload limit per sicurezza
- [Phase 05-estrattore-universale]: google-genai SDK (not google-generativeai EOL Nov 2025) + GEMINI_MODEL constant for single-point migration to gemini-2.5-flash before March 31 2026 retirement
- [Phase 05-estrattore-universale]: ExtractionError typed exception as unified failure surface — GEMINI_API_KEY missing raises ExtractionError not KeyError
- [Phase 05-estrattore-universale]: Pydantic Literal confidence labels declared by Gemini (not heuristic) — response_schema=OrdineEstratto enforces schema syntactically
- [Phase 05-estrattore-universale]: Baseline hardcoded in validation script (not read from audit_reports JSON) — avoids coupling to file format changes

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 5: Gemini API key disponibile — conservare in app/.env come GEMINI_API_KEY (non committare)
- Phase 5: 32 PDF nella cartella ORDINI ma sono 16 file duplicati — verificare con glob deduplication
- Known tech debt: `get_orders_by_phase` carica tutti gli ordini (ottimizzare con JOIN quando il volume cresce)
- Known tech debt: `declarative_base()` deprecato in SQLAlchemy 2.0
- Known tech debt: `datetime.utcnow()` deprecato in Python 3.12+

## Session Continuity

Last session: 2026-02-19
Stopped at: Completed 05-estrattore-universale/05-02-PLAN.md
Resume file: .planning/phases/05-estrattore-universale/05-02-SUMMARY.md

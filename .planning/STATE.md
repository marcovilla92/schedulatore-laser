# Project State — Schedulatore Laser

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Operators see what needs processing next and track completion in real-time
**Current focus:** Milestone v1.2 — Phase 6: Integrazione Pipeline

## Current Position

Phase: 6 of 6 (Integrazione Pipeline)
Plan: 2 of 2 in current phase — COMPLETE
Status: Phase 6 COMPLETE — universal extractor integrato nella pipeline Flask + UI confidence badges in ordini_estratti.html + PDF upload singolo
Last activity: 2026-02-20 — CSS confidence badges, upload singolo section, JS confidenceBadge() + uploadSinglePDF() functions tested and verified

Progress: [██████████] 100% — Milestone v1.2 COMPLETE

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 8 min
- Total execution time: 0.25 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 4. Audit Parser | 1/1 | — | — |
| 5. Estrattore Universale | 2/2 | 8 min | 4 min |
| 6. Integrazione Pipeline | 2/2 | 16 min | 8 min |

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
- [Phase 06-integrazione-pipeline Plan 1]: load_dotenv chiamato PRIMA dell'import di backend.app — garantisce GEMINI_API_KEY in os.environ quando i moduli vengono inizializzati
- [Phase 06-integrazione-pipeline Plan 1]: Import guard try/except ImportError per google-genai — Flask si avvia anche senza il package installato
- [Phase 06-integrazione-pipeline Plan 1]: estrattore="legacy" impostato esplicitamente nei fallback path — campo sempre presente nella risposta JSON
- [Phase 06-integrazione-pipeline Plan 2]: Confidence badges CSS: amber per bassa, cyan per media, nessun badge per alta
- [Phase 06-integrazione-pipeline Plan 2]: Upload singolo section con file input e result box con 4 campi estratti
- [Phase 06-integrazione-pipeline Plan 2]: Legacy notice blu informativa (non errore rosso) quando estrattore != 'universal'

### Pending Todos

None.

### Blockers/Concerns

- Phase 5: Gemini API key disponibile — conservare in app/.env come GEMINI_API_KEY (non committare)
- Phase 5: 32 PDF nella cartella ORDINI ma sono 16 file duplicati — verificare con glob deduplication
- Known tech debt: `get_orders_by_phase` carica tutti gli ordini (ottimizzare con JOIN quando il volume cresce)
- Known tech debt: `declarative_base()` deprecato in SQLAlchemy 2.0
- Known tech debt: `datetime.utcnow()` deprecato in Python 3.12+

## Session Continuity

Last session: 2026-02-20
Stopped at: Completed 06-integrazione-pipeline/06-02-PLAN.md (all phases complete)
Next: gsd-verify to audit milestone v1.2 completeness
Resume file: .planning/phases/06-integrazione-pipeline/06-02-SUMMARY.md

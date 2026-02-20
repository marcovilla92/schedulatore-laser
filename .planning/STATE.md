# Project State — Schedulatore Laser

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Operators see what needs processing next and track completion in real-time
**Current focus:** Milestone v1.2.1 — Hotfix Release (COMPLETE)

## Current Position

Status: **v1.2.1 HOTFIX RELEASE — COMPLETE** ✅
Last activity: 2026-02-20 15:31 — All 5 critical bugs fixed and tested end-to-end
Quality: 100% functional — timing, phase progression, and article tracking working correctly
Ready for: v1.3 development or continued feature work

Progress: [██████████] 100% — Milestone v1.2 COMPLETE + v1.2.1 HOTFIX COMPLETE

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
- [v1.2.1 Hotfix 1]: timestamp_ultimo_partial field added to ProcessingStep model to track partial completion pauses
- [v1.2.1 Hotfix 2]: Total time calculation: sum of all phase durations formatted as "Xh Ymin"
- [v1.2.1 Hotfix 3]: Frontend timer pause on partial completion: data.phase_complete flag determines pause behavior
- [v1.2.1 Hotfix 4]: start_phase() logic updated: allow resume of paused phases (clear timestamp_ultimo_partial)
- [v1.2.1 Hotfix 5]: Article-phase tracking: count only articles requiring that specific phase (articles can have different required_phases)

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
Completed: v1.2.1 Hotfix Release — 5 critical bugs fixed and tested
- Timing state tracking (timestamp_ultimo_partial)
- Total time calculation (Xh Ymin format)
- Frontend timer pause on partial completion
- Backend phase resume logic
- Article-phase progression logic

Status: READY FOR NEXT MILESTONE (v1.3 or continued feature development)
All features: ✅ Fully functional and tested end-to-end

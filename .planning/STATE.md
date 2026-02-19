# Project State — Schedulatore Laser

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Operators see what needs processing next and track completion in real-time
**Current focus:** Milestone v1.2 — Phase 4: Audit Parser

## Current Position

Phase: 4 of 6 (Audit Parser)
Plan: — of — in current phase
Status: Ready to plan
Last activity: 2026-02-19 — Roadmap v1.2 created (phases 4-6)

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 4. Audit Parser | 0/0 | — | — |
| 5. Estrattore Universale | 0/0 | — | — |
| 6. Integrazione Pipeline | 0/0 | — | — |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Recent decisions affecting current work:

- v1.2: Gemini 2.0 Flash scelto come LLM per estrazione universale (free tier, server ha internet)
- v1.2: Docling gia nel progetto — usato come layer PDF-to-text prima di Gemini
- v1.0: flag_modified() necessario per mutazioni JSON in SQLAlchemy
- v1.0: 50MB upload limit per sicurezza

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 4: Richiede PDF di test in C:\Users\39334\Documents\ORDINI (fuori dal repo — deve esistere prima dell'esecuzione)
- Phase 5: Richiede Gemini API key — l'utente deve ottenerla prima dell'esecuzione della fase
- Known tech debt: `get_orders_by_phase` carica tutti gli ordini (ottimizzare con JOIN quando il volume cresce)
- Known tech debt: `declarative_base()` deprecato in SQLAlchemy 2.0
- Known tech debt: `datetime.utcnow()` deprecato in Python 3.12+

## Session Continuity

Last session: 2026-02-19
Stopped at: Roadmap v1.2 created — Phase 4 ready to plan
Resume file: .planning/ROADMAP.md

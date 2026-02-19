# Project State — Schedulatore Laser

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Operators see what needs processing next and track completion in real-time
**Current focus:** Milestone v1.2 — Parser Universale (PDF extraction with Docling + Gemini)

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-02-19 — Milestone v1.2 started

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

### From v1.0 (Pre-GSD)

- Backend review fixed 14 critical/high bugs (2026-02-18)
- UI redesigned: 7 pages with dark glassmorphism
- GSD v1.20.4 installed with full skill ecosystem

### From v1.1 (Pending — not yet executed)

- v1.1 "Fasi per Articolo" defined (3 phases, 10 requirements) but deferred
- Context gathered for Phase 1 (Modello Dati per Articolo)
- Resume: .planning/phases/01-modello-dati-per-articolo/01-CONTEXT.md

### Decisions

- flag_modified() required for JSON mutations in SQLAlchemy
- 50MB upload limit for security
- lambda defaults for mutable Column defaults
- Per-article phase model chosen over order-level (v1.1 core decision)
- Gemini 2.0 Flash chosen as LLM for universal PDF extraction (free tier, server has internet)
- Docling already in project — use as PDF-to-text layer before Gemini

### Known Issues

- `get_orders_by_phase` loads ALL orders (optimize with JOIN when volume grows)
- `declarative_base()` deprecated in SQLAlchemy 2.0
- `datetime.utcnow()` deprecated in Python 3.12+
- Parser success rate unknown — audit planned in Phase 4

### Pending Todos

None yet.

### Blockers/Concerns

- Gemini API key needed before Phase 5 can execute
- Test PDFs at C:\Users\39334\Documents\ORDINI (outside repo — needed for Phase 4 audit)

## Session Continuity

Last session: 2026-02-19
Stopped at: Milestone v1.2 requirements being defined
Resume file: .planning/REQUIREMENTS.md

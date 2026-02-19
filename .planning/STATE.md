# Project State — Schedulatore Laser

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Operators see what needs processing next and track completion in real-time
**Current focus:** Phase 1 — Modello Dati per Articolo (backend foundation for per-article phases)

## Current Position

Phase: 1 of 3 (Modello Dati per Articolo)
Plan: 0 of 0 in current phase (not yet planned)
Status: Ready to plan
Last activity: 2026-02-19 — Roadmap created with 3 phases, 10 requirements mapped

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Modello Dati | 0/0 | — | — |
| 2. Assegnazione Fasi | 0/0 | — | — |
| 3. Viste Reparto | 0/0 | — | — |

## Accumulated Context

### From v1.0 (Pre-GSD)

- Backend review fixed 14 critical/high bugs (2026-02-18)
- UI redesigned: 7 pages with dark glassmorphism
- GSD v1.20.4 installed with full skill ecosystem

### Decisions

- flag_modified() required for JSON mutations in SQLAlchemy
- 50MB upload limit for security
- lambda defaults for mutable Column defaults
- Per-article phase model chosen over order-level (v1.1 core decision)

### Known Issues

- `get_orders_by_phase` loads ALL orders (optimize with JOIN when volume grows)
- `declarative_base()` deprecated in SQLAlchemy 2.0
- `datetime.utcnow()` deprecated in Python 3.12+

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-02-19
Stopped at: Roadmap created, ready to plan Phase 1
Resume file: None

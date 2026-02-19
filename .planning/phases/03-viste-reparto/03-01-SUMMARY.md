---
phase: 03-viste-reparto
plan: 01
subsystem: api, ui
tags: [flask, sqlite, sqlalchemy, vanilla-js, html, per-article-tracking]

# Dependency graph
requires:
  - phase: 01-modello-dati-per-articolo
    provides: Article records, ProcessingStep with article_id, get_order_details() with completed_phases
  - phase: 02-assegnazione-fasi
    provides: required_phases per-article assignment via UI

provides:
  - Enriched GET /api/phase/LASER/orders with articles_in_phase, phase_status, article_id per article
  - started_phases field in article dict from get_order_details()
  - laser.html reference implementation with per-article status display (3 states)
  - Avvia Tutti button (sequential per-article start via UUID)
  - UUID-based modal completion (article_ids instead of article_indices)

affects:
  - 03-viste-reparto (piega.html and saldatura.html will follow same pattern)
  - dashboard (articles_in_phase alias backward compat maintained)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - started_phases computed in get_order_details() from ProcessingStep timestamps for reuse across routes
    - articles_in_phase replaces articles_next_phase (backward compat alias kept)
    - Sequential for...of await for per-article batch start (no race conditions on ProcessingStep)
    - JSON passed via HTML onclick attribute using &quot; encoding, parsed with JSON.parse in handler
    - escapeHtml() helper for XSS prevention in dynamic innerHTML rendering

key-files:
  created: []
  modified:
    - app/backend/database.py
    - app/backend/app.py
    - app/frontend/laser.html

key-decisions:
  - "Option A chosen for started_phases: compute in get_order_details() (database.py) rather than querying in route (app.py) — reusable, clean, single source of truth"
  - "articles_next_phase kept as alias for articles_in_phase in API response — backward compat for any existing consumers"
  - "Orders sorted by data_consegna asc then active-first; _has_active internal field stripped before serialization"
  - "avviaTutti passes JSON via onclick attribute using &quot; encoding; openPartialCompleteModal receives JS array literal directly"
  - "Seleziona Tutti replaces Completa Tutti: semantically correct (selects, doesn't submit)"

patterns-established:
  - "Phase status derivation: completed_phases + started_phases from get_order_details() → phase_status in route"
  - "Per-article batch operations: sequential for...of await to avoid race conditions on ProcessingStep"
  - "Department view pattern: articles_in_phase with phase_status, filter out completed, sort active first"

requirements-completed: [VISTA-01, VISTA-02]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 3 Plan 01: Viste Reparto — Laser Summary

**Per-article phase status API (in_attesa/in_lavorazione) with laser.html reference view: Avvia Tutti (sequential UUID start) and modal completion via article_ids**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T09:28:54Z
- **Completed:** 2026-02-19T09:32:07Z
- **Tasks:** 1 (Part A: backend + Part B: frontend)
- **Files modified:** 3

## Accomplishments

- Added `started_phases` field to article dict in `get_order_details()` — computed from ProcessingStep timestamps, reusable by any route
- Rewrote `get_orders_by_phase()` in app.py to return `articles_in_phase` with `phase_status` per article and `article_id` UUID; orders sorted by delivery date then active-first; backward compat alias `articles_next_phase` maintained
- Rewrote laser.html JavaScript: per-article status badges (in attesa / in lavorazione with pulsing dot / completato dimmed), "Avvia Tutti" sequential per-article start, UUID-based modal completion with "Seleziona Tutti", XSS-safe `escapeHtml()` helper

## Task Commits

Each task was committed atomically:

1. **Task 1: Enrich API and rewrite laser.html with per-article phase tracking** - `659ebc1` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `app/backend/database.py` — Added `started_phases` field to article dict in v1.1+ path of `get_order_details()`
- `app/backend/app.py` — Rewrote `get_orders_by_phase()` route with per-article phase_status, articles_in_phase, backward compat alias, dual sort
- `app/frontend/laser.html` — Added CSS for 3 article status states (attesa/lavorazione with pulse/completato); rewrote full JS section: `renderOrders`, `avviaTutti`, `openPartialCompleteModal`, `selectAllModalCheckboxes`, `submitPartialComplete`, `updateSummary`, `escapeHtml`

## Decisions Made

- **Option A for started_phases**: Computed in `database.py` `get_order_details()` rather than querying ProcessingStep directly in the route. Cleaner, reusable, single source of truth.
- **Backward compat alias**: `articles_next_phase` kept as alias for `articles_in_phase` — ensures no regressions if any consumer still uses the old field name.
- **_has_active internal field**: Used for in-Python sorting of orders, stripped before JSON serialization. Avoids re-sorting in client.
- **JSON in onclick attribute**: `articles_in_phase` JSON passed to `avviaTutti` and `openPartialCompleteModal` via `&quot;` encoding in onclick attribute, parsed with `JSON.parse` in the handler. Avoids extra fetch for already-loaded data.
- **Seleziona Tutti replaces Completa Tutti**: The old "Completa Tutti" button did two things (select + submit). Split into "Seleziona Tutti" (select checkboxes) + "Completa Selezionati" (submit) — more granular control for operators.

## Deviations from Plan

None - plan executed exactly as written.

The plan specified Option A for `started_phases` and the implementation followed it precisely. All CSS states, button behaviors, sort orders, and API field names match the plan specification.

## Issues Encountered

None. Python executable required full path (`/c/Users/Marco/AppData/Local/Programs/Python/Python313/python.exe`) since `python`/`python3` are not in the bash PATH on this Windows environment — syntax verification succeeded with the full path.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `GET /api/phase/LASER/orders` is the reference enriched endpoint; `piega.html` and `saldatura.html` should follow the identical pattern in plan 03-02
- The `get_order_details()` `started_phases` field is now available for any future phase views without additional DB queries
- `laser.html` serves as the reference implementation for the other department views

## Self-Check: PASSED

- FOUND: app/backend/app.py
- FOUND: app/backend/database.py
- FOUND: app/frontend/laser.html
- FOUND: .planning/phases/03-viste-reparto/03-01-SUMMARY.md
- FOUND: commit 659ebc1

---
*Phase: 03-viste-reparto*
*Completed: 2026-02-19*

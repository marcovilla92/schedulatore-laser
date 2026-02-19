---
phase: 01-modello-dati-per-articolo
plan: 03
subsystem: api

tags: [flask, api, migration, per-article-tracking, schema-migration, backward-compat]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Article SQLAlchemy model; migrate_articles.py with ensure_articles_table/migrate_existing_orders"
  - phase: 01-02
    provides: "OrderManager per-article business logic; start_phase/complete_phase with article_id param"
provides:
  - "Auto-migration on startup: ensure_articles_table() + migrate_existing_orders() called in app.py"
  - "create_order API: normalizes articles to default 5 phases, returns article_records with UUIDs"
  - "start_phase API: accepts optional article_id for per-article targeting"
  - "complete_phase API: accepts optional article_id for per-article completion"
  - "complete_phase_partial API: accepts article_ids (UUID) or article_indices (legacy int)"
  - "GET /api/orders/<id>/articles: returns per-article status with article_id, next_phase, etc."
  - "PUT /api/orders/<id>/articles/<article_id>/phases: update required_phases with validation"
  - "ALTER TABLE migration for processing_steps.article_id on existing databases"
affects:
  - 02-assegnazione-fasi
  - 03-viste-reparto

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PRAGMA table_info() + ALTER TABLE for idempotent column addition to existing tables"
    - "sqlalchemy.text() for raw DDL in migration utility"
    - "article_id as optional request body param in phase endpoints (backward-compat addition)"
    - "article_records[] in create_order response: UUIDs available to callers immediately"
    - "409 Conflict status for phase update when steps already started"

key-files:
  created: []
  modified:
    - app/backend/app.py
    - app/backend/__init__.py
    - app/backend/migrate_articles.py

key-decisions:
  - "Added _ensure_column_exists() to migrate_articles.py to handle ALTER TABLE for existing DBs — SQLAlchemy create_all() does not add columns to existing tables"
  - "PUT /api/orders/<id>/articles/<article_id>/phases returns 409 Conflict if any step already started (protecting data integrity)"
  - "GET /api/orders/<id>/articles reuses get_order_details() rather than duplicating logic — single source of truth"
  - "article_records[] added to create_order response so callers immediately have article UUIDs without a second GET request"

patterns-established:
  - "PRAGMA table_info() pattern for idempotent ALTER TABLE in SQLite migration"
  - "Migration called at startup from app.py (not from __init__.py) so it runs after initialize_database()"

requirements-completed: [DATI-01, DATI-02, DATI-03, DATI-04]

# Metrics
duration: 7min
completed: 2026-02-19
---

# Phase 1 Plan 03: Modello Dati Articolo — API Integration Summary

**API layer updated for per-article tracking: migration auto-runs on startup, all phase endpoints accept optional article_id, two new endpoints added, and existing database ALTER TABLE handled via idempotent migration**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-02-19T08:27:23Z
- **Completed:** 2026-02-19T08:34:06Z
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments

- `app.py`: imports `ensure_articles_table`, `migrate_existing_orders` from migrate_articles and calls both on startup (after `initialize_database()`) — idempotent, safe on every restart
- `create_order` route: normalizes articles to add default 5 phases if `required_phases` absent; returns `article_records` list with UUID, name, code, qty, required_phases for each Article DB record
- `start_phase` route: parses `article_id` from request body, passes to `OrderManager.start_phase(article_id=...)` — backward compat when omitted
- `complete_phase` route: parses `article_id` from request body, passes to `OrderManager.complete_phase(article_id=...)` — backward compat when omitted
- `complete_phase_partial` route: accepts `article_ids` (UUID list, v1.1+) or `article_indices` (int list, legacy) — routes to appropriate OrderManager call
- New `GET /api/orders/<id>/articles`: returns per-article status list from `get_order_details()` — needed by Phase 2 and Phase 3
- New `PUT /api/orders/<id>/articles/<article_id>/phases`: validates no started steps, removes existing ProcessingSteps, updates `required_phases`, recreates ProcessingSteps with new phases; returns 409 if any step started
- `__init__.py`: exports all model classes and OrderManager for clean package imports
- `migrate_articles.py`: added `_ensure_column_exists()` helper using `PRAGMA table_info()` + `ALTER TABLE` — handles existing databases missing the `article_id` column on `processing_steps`

## Task Commits

Each task was committed atomically:

1. **Task 1: Update API routes and wire migration into startup** - `baca25f` (feat)
2. **Task 2: End-to-end integration verification** - verified via `baca25f` (test was execution-only, no new files)

## Files Created/Modified

- `app/backend/app.py` — Migration wired into startup; create_order normalized + article_records response; start_phase/complete_phase accept article_id; complete_phase_partial accepts article_ids or article_indices; new GET /articles endpoint; new PUT /articles/<id>/phases endpoint
- `app/backend/__init__.py` — Full model exports added
- `app/backend/migrate_articles.py` — Added `_ensure_column_exists()` for idempotent ALTER TABLE on existing processing_steps table

## Decisions Made

- `_ensure_column_exists()` uses `PRAGMA table_info()` to check before `ALTER TABLE` — SQLite doesn't support `IF NOT EXISTS` for ALTER TABLE, so this is the safe portable approach
- `PUT /api/orders/<id>/articles/<article_id>/phases` returns 409 Conflict (not 400) when steps already started, to distinguish "bad input" from "valid input but state conflict"
- Migration is called from `app.py` body (not from a route or `__init__.py`) so it runs once at server startup before any requests are served

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing ALTER TABLE for article_id on existing databases**
- **Found during:** Task 1 verification (first API call failed with `OperationalError: table processing_steps has no column named article_id`)
- **Issue:** `ensure_articles_table()` only ran `Base.metadata.create_all()` which creates new tables but does NOT add columns to existing tables. An existing database (pre-v1.1) would have `processing_steps` without `article_id`.
- **Fix:** Added `_ensure_column_exists('processing_steps', 'article_id', 'TEXT DEFAULT NULL REFERENCES articles(id)')` call inside `ensure_articles_table()`, using `PRAGMA table_info()` for idempotent detection
- **Files modified:** `app/backend/migrate_articles.py`
- **Commit:** `baca25f`

## E2E Test Results

All 5 test groups PASSED:

| Test | Result |
|------|--------|
| DATI-01: Articles with per-article required_phases | PASS (8/8 checks) |
| DATI-02: ProcessingSteps created per-article (5+2+3=10) | PASS (4/4 checks) |
| DATI-03: Article status derivation (next_phase, completed_phases) | PASS (6/6 checks) |
| DATI-04: Order SPEDITO only after ALL articles complete ALL phases | PASS (4/4 checks) |
| Backward Compatibility: existing endpoints still return valid responses | PASS (5/5 checks) |

## Issues Encountered

None beyond the auto-fixed Rule 1 bug documented above.

## User Setup Required

None — migration runs automatically on server startup. Existing databases are upgraded transparently (idempotent ALTER TABLE on `processing_steps`).

## Next Phase Readiness

- All 4 DATI requirements (DATI-01 through DATI-04) verified end-to-end
- Phase 1 complete: data model, business logic, and API layer all wired together
- Phase 2 (Assegnazione Fasi UI) can build on `GET /api/orders/<id>/articles` and `PUT /api/orders/<id>/articles/<article_id>/phases`
- Phase 3 (Viste Reparto) can use `article_id` fields now present in all phase endpoint responses
- Existing frontend pages (dashboard, laser, piega, saldatura) continue to work unchanged (backward compat batch mode preserved in all phase operations)

---
*Phase: 01-modello-dati-per-articolo*
*Completed: 2026-02-19*

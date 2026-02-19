---
phase: 01-modello-dati-per-articolo
plan: 01
subsystem: database

tags: [sqlalchemy, sqlite, migration, orm, article-model]

# Dependency graph
requires: []
provides:
  - "Article SQLAlchemy model with UUID pk, order_id FK, required_phases JSON, attributes JSON"
  - "Order.article_records relationship (cascade all, delete-orphan)"
  - "ProcessingStep.article_id nullable FK for per-article step tracking (v1.1+)"
  - "migrate_articles.py utility to populate articles table from existing Order.articles JSON"
affects:
  - 02-assegnazione-fasi
  - 03-viste-reparto

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Article as first-class entity with UUID pk and JSON required_phases column"
    - "attributes JSON column as catch-all for format-specific PDF fields (flexible schema)"
    - "default=lambda: list for mutable JSON column defaults (existing SQLAlchemy pattern)"
    - "Backward-compat nullable FK: article_id on ProcessingStep nullable for pre-v1.1 rows"
    - "Per-order commit in migration for transactional safety"

key-files:
  created:
    - app/backend/migrate_articles.py
  modified:
    - app/backend/models.py

key-decisions:
  - "required_phases as JSON list column (not normalized table) — matches existing JSON patterns in codebase"
  - "attributes JSON catch-all column for PDF-format-specific fields (price, material, dimensions) — keeps schema flexible without proliferating columns"
  - "Default all 5 phases per-article: LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE"
  - "ProcessingStep.article_id nullable so all pre-v1.1 processing_steps remain valid without migration"
  - "Legacy Order.articles JSON column preserved unchanged — full backward compatibility"

patterns-established:
  - "Article model placed before Order in models.py to avoid forward-reference issues with ForeignKey"

requirements-completed: [DATI-01]

# Metrics
duration: 1min
completed: 2026-02-19
---

# Phase 1 Plan 01: Modello Dati Articolo Summary

**SQLAlchemy Article model with UUID pk, per-article required_phases JSON, and migration utility to promote existing Order.articles JSON blobs to first-class database records**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-19T08:17:03Z
- **Completed:** 2026-02-19T08:19:01Z
- **Tasks:** 2 of 2
- **Files modified:** 2

## Accomplishments

- New `Article` model class in models.py: `articles` table with id (UUID), order_id (FK), name, code, qty, required_phases (JSON, default all 5), attributes (JSON catch-all)
- `Order.article_records` relationship with cascade delete-orphan for v1.1+ article records
- `ProcessingStep.article_id` nullable FK column and `article` relationship — backward-compatible with all existing step rows
- `migrate_articles.py` with `ensure_articles_table()`, `migrate_existing_orders()`, and `run_migration()` entry point — can run standalone or be called programmatically

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Article model and update Order/ProcessingStep relationships** - `cac41ef` (feat)
2. **Task 2: Create migration utility for existing orders** - `3711d21` (feat)

**Plan metadata:** committed with docs commit below

## Files Created/Modified

- `app/backend/models.py` - Added Article class, Order.article_records relationship, ProcessingStep.article_id nullable FK column and article relationship; kept all legacy columns
- `app/backend/migrate_articles.py` - New migration utility with three exported functions and standalone entry point

## Decisions Made

- Used `default=lambda: ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'SPEDIZIONE']` for required_phases (mutable default lambda pattern already established in codebase per STATE.md decision)
- `attributes` JSON column keeps the schema flexible — extra fields from any of the 16 PDF formats (price, material, weight, surface treatment, etc.) flow into attributes without requiring schema changes
- ProcessingStep.article_id is nullable so the 0 migration cost applies to existing rows — no ALTER TABLE or data backfill needed for ProcessingStep

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. The articles table is auto-created by SQLAlchemy on next server start (`initialize_database()` calls `create_all`). Migration of existing data is opt-in via `python -m app.backend.migrate_articles`.

## Next Phase Readiness

- Article model is in place and importable — ready for Plan 02 (phase assignment per article)
- Migration utility available for any existing orders that need their JSON articles promoted
- ProcessingStep can now optionally link to a specific Article (nullable FK) — Plan 02 can start using this

---
*Phase: 01-modello-dati-per-articolo*
*Completed: 2026-02-19*

## Self-Check: PASSED

- app/backend/models.py — FOUND
- app/backend/migrate_articles.py — FOUND
- .planning/phases/01-modello-dati-per-articolo/01-01-SUMMARY.md — FOUND
- Commit cac41ef (Task 1) — FOUND
- Commit 3711d21 (Task 2) — FOUND

---
phase: 01-modello-dati-per-articolo
plan: 02
subsystem: database

tags: [sqlalchemy, sqlite, orm, per-article-tracking, processing-steps, backward-compat]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Article SQLAlchemy model with UUID pk, order_id FK, required_phases JSON; ProcessingStep.article_id nullable FK"
provides:
  - "OrderManager.create_order creates Article DB records + per-article ProcessingSteps (article_id set)"
  - "start_phase/complete_phase support optional article_id for per-article targeting with batch fallback"
  - "complete_phase_partial accepts article_ids (UUID) or article_indices (int, resolved to UUID)"
  - "get_order_details derives next_phase, completed_phases, remaining_phases, is_completed per-article from Article records"
  - "get_orders_by_phase uses JOIN query on Article+ProcessingStep instead of loading all orders"
  - "update_order_articles syncs Article table and recreates ProcessingSteps for new articles"
  - "Order marked SPEDITO only when ALL ProcessingSteps across ALL articles have timestamp_fine"
  - "Full backward compatibility: all methods work without article_id (pre-v1.1 orders fallback)"
affects:
  - 02-assegnazione-fasi
  - 03-viste-reparto

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "session.flush() before creating child records to obtain parent.id without committing"
    - "article_id optional parameter with None default for backward-compatible batch mode"
    - "Article-first query with fallback to JSON-based logic for pre-v1.1 data"
    - "PHASE_ORDER module-level constant for canonical phase ordering"
    - "Private _complete_phase_partial_legacy() for isolated legacy path"
    - "session.query(Article).filter(...).contains(phase) for JSON array membership check"

key-files:
  created: []
  modified:
    - app/backend/database.py

key-decisions:
  - "Batch mode (no article_id) retained in start_phase and complete_phase for backward compat with existing frontend calls"
  - "complete_phase_partial accepts both article_ids and article_indices with UUID resolution to support both v1.1 and legacy callers"
  - "get_order_details checks for Article records first; falls back to JSON logic only if no Article rows exist (zero-migration compatibility)"
  - "get_orders_by_phase uses separate fallback query for pre-v1.1 orders without Article records"
  - "update_order_articles matches articles by code+name for stable identity across updates"
  - "session.flush() (not commit) used when creating Article before its ProcessingSteps to get the ID without premature commit"

patterns-established:
  - "Two-path pattern: v1.1+ path (Article records) + legacy fallback path (JSON) in read methods"
  - "article_id as optional param with None default: all existing callers unmodified, new callers can target specific articles"

requirements-completed: [DATI-02, DATI-03, DATI-04]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 1 Plan 02: Modello Dati Articolo — Business Logic Summary

**OrderManager rewritten for per-article ProcessingStep creation and status derivation, with full backward compatibility for pre-v1.1 orders lacking Article records**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-19T08:21:52Z
- **Completed:** 2026-02-19T08:24:47Z
- **Tasks:** 1 of 1
- **Files modified:** 1

## Accomplishments

- `create_order`: creates Article records in `articles` table + one ProcessingStep per article+phase combination (article_id set); JSON `articles` column still updated for frontend backward compat
- `start_phase` / `complete_phase`: accept optional `article_id`; when omitted, batch-start/complete all steps for that order+phase (needed for existing frontend flows)
- `complete_phase_partial`: accepts `article_ids` (UUID list, v1.1+) or `article_indices` (int list, resolved to UUIDs via ordered Article query); isolated legacy fallback method for pre-v1.1 orders
- `get_order_details`: queries Article records first; derives `next_phase`, `completed_phases`, `remaining_phases`, `is_completed` per-article from ProcessingStep rows; falls back to JSON-based logic for orders without Article rows
- `get_orders_by_phase`: uses JOIN query on Article + ProcessingStep (resolves known N+1 issue from STATE.md); separate fallback for pre-v1.1 orders
- `update_order_articles`: syncs Article table (add/remove/update matched by code+name) and recreates ProcessingSteps for newly added articles
- Order marked SPEDITO only when ALL ProcessingSteps for ALL articles have `timestamp_fine`

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite OrderManager for per-article phase tracking** - `13fb770` (feat)

## Files Created/Modified

- `app/backend/database.py` - Full rewrite of OrderManager: per-article ProcessingStep creation, per-article status derivation in get_order_details, JOIN-based get_orders_by_phase, Article-syncing update_order_articles; all methods backward-compatible

## Decisions Made

- `session.flush()` used (not `commit`) when Article is created before its ProcessingSteps, so the article UUID is available without an early commit that would complicate rollback
- Batch mode retained in `start_phase` / `complete_phase` (no `article_id` parameter) so all existing frontend calls continue to work unchanged
- `complete_phase_partial` resolves int indices to Article UUIDs by querying articles ordered by `Article.id`; this gives stable resolution as long as order stays consistent (acceptable for v1.1)
- `get_orders_by_phase` now runs two separate queries: one for v1.1+ orders (via Article JOIN) and one for pre-v1.1 orders; unified result set returned

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. All changes are to database.py in-process logic. The Article table is already auto-created by `initialize_database()` from Plan 01.

## Next Phase Readiness

- All three requirements DATI-02, DATI-03, DATI-04 are implemented
- Plan 03 (API layer updates and migration runner integration) can now build on this logic layer
- Existing frontend continues to work unchanged (backward-compat batch mode in all phase operations)
- `article_id` field now present in all `get_order_details` article entries — ready for Phase 2 frontend use

---
*Phase: 01-modello-dati-per-articolo*
*Completed: 2026-02-19*

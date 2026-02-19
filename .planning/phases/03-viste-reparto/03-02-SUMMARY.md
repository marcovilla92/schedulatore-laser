---
phase: 03-viste-reparto
plan: 02
subsystem: ui
tags: [vanilla-js, html, per-article-tracking, dashboard, piega, saldatura]

# Dependency graph
requires:
  - phase: 03-viste-reparto
    plan: 01
    provides: articles_in_phase with phase_status and article_id UUID; laser.html reference implementation

provides:
  - piega.html with per-article status (3 states), Avvia Tutti + timer integration, UUID-based modal
  - saldatura.html with per-article status (3 states), Avvia Tutti + timer integration, UUID-based modal
  - dashboard.html modal with segmented phase progress bar and X/Y articoli completati counter
  - dashboard.html calendar cards with mini article progress indicator

affects:
  - All 3 department views now have identical per-article tracking behavior (laser, piega, saldatura)
  - Dashboard management view shows full per-article phase progress

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Per-article timer integration: timer starts on Avvia Tutti, pauses on modal open, resumes on cancel, stops on submit
    - Phase progress bar: segment width proportional to article count, colored by aggregate completion ratio
    - Backward compatibility check: articles[0].required_phases !== undefined guards v1.1+ logic
    - Calendar card mini progress: article_records.has_started_steps used for compact X/Y display

key-files:
  created: []
  modified:
    - app/frontend/piega.html
    - app/frontend/saldatura.html
    - app/frontend/dashboard.html

key-decisions:
  - "Timer integration with Avvia Tutti: timer starts when Avvia Tutti succeeds (not when modal opens); pauses on Completa modal open; resumes on Annulla; stops permanently on submitPartialComplete"
  - "escapeHtml() added to piega and saldatura for XSS parity with laser.html reference"
  - "closePartialModal() in piega/saldatura resumes timer via restoreTimer() when user cancels — preserves elapsed time"
  - "Seleziona Tutti replaces Completa Tutti in piega and saldatura modals — matches laser.html pattern"
  - "Phase segment width uses flex: N (article count) for proportional display — visually accurate"
  - "Progress bar uses height% for fill within each segment — compact vertical fill per phase segment"
  - "Calendar card progress uses article_records.has_started_steps as approximation (already available from GET /api/orders)"

patterns-established:
  - "All 3 department views (laser/piega/saldatura) now identical in JS behavior; only PHASE constant and color theme differ"
  - "Timer lifecycle: avviaTutti() start → openPartialCompleteModal() pause → closePartialModal() resume → submitPartialComplete() stop"

requirements-completed: [VISTA-01, VISTA-02, VISTA-03]

# Metrics
duration: 7min
completed: 2026-02-19
---

# Phase 3 Plan 02: Viste Reparto — Piega, Saldatura, Dashboard Summary

**Per-article pattern replicated to piega.html and saldatura.html (Avvia Tutti + UUID modal + timer integration); dashboard modal enhanced with segmented phase progress bar and X/Y articoli completati counter**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-19T09:35:32Z
- **Completed:** 2026-02-19T09:42:20Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

### Task 1: Replicated per-article pattern to piega.html and saldatura.html
- Replaced `articles_next_phase` with `articles_in_phase` + `phase_status` per article in both files
- Added 3-state article status badges: In attesa (grey), In lavorazione (cyan with pulsing dot), Completato (green dimmed)
- Added "Avvia Tutti" button: sequential per-article `POST /api/orders/{id}/phase/{PHASE}/start` with `article_id` UUID
- Timer lifecycle integration: timer starts on Avvia Tutti success, pauses when Completa modal opens, resumes on Annulla, stops permanently on submitPartialComplete
- Modal upgraded from `article_indices` to `article_ids` UUID-based completion
- Added "Seleziona Tutti" button in modal (replaces "Completa Tutti" — selects only, doesn't submit)
- Added `escapeHtml()` XSS prevention (parity with laser.html)
- Cards filtered to show only orders with non-completed articles; empty state shown when none
- Overlay click + Escape key close modal (parity feature)

### Task 2: Per-article phase progress bar in dashboard
- Added "Progresso Articoli" modal section above the articles table
- Segmented horizontal progress bar: one segment per assigned phase, proportional width (flex: articleCount)
- Segment coloring: grey = in_attesa, cyan+pulse = in_lavorazione, green = completato
- "X/Y articoli completati" counter with green highlight when all done
- Backward compatibility: v1.0 orders (no required_phases) show graceful fallback message
- Calendar cards: mini "X/Y" progress indicator below client name using article_records.has_started_steps
- Fully completed orders show "X/X ✓" in green on calendar card
- Added `pulizia_completata` CSS class for green calendar card styling

## Task Commits

Each task was committed atomically:

1. **Task 1: Replicate per-article pattern to piega.html and saldatura.html** - `66932ab` (feat)
2. **Task 2: Add per-article phase progress to dashboard** - `38579f1` (feat)

## Files Created/Modified

- `app/frontend/piega.html` — Full rewrite of JS section: articles_in_phase, phase_status badges, Avvia Tutti + timer, UUID modal, escapeHtml, Seleziona Tutti; CSS additions: article status classes, btn-avvia, btn-modal-select-all
- `app/frontend/saldatura.html` — Same pattern as piega.html but with SALDATURA phase and orange theme colors
- `app/frontend/dashboard.html` — Added progress bar CSS section, "Progresso Articoli" modal section HTML, JS logic in openOrderModal(), mini progress on calendar cards in createDayElement()

## Decisions Made

- **Timer integration with Avvia Tutti**: Timer starts when Avvia Tutti API call succeeds (not on button click). This ensures the timer only runs when articles are actually being worked. Timer pauses when Completa modal opens (user might be reviewing, not working), and resumes when Annulla is clicked.
- **escapeHtml() added to piega/saldatura**: Piega and saldatura originally lacked XSS prevention. Added for security parity with laser.html reference.
- **Seleziona Tutti instead of Completa Tutti**: Original piega/saldatura had "Completa Tutti" which both selected AND submitted. Split into "Seleziona Tutti" (select only) + "Completa Selezionati" (submit) — more granular operator control, matches laser.html pattern.
- **Phase progress bar height-based fill**: Each phase segment uses a height% fill within a fixed-height container rather than width%. This gives a more readable vertical "thermometer" effect when segments have labels above.
- **article_records.has_started_steps for calendar progress**: The GET /api/orders response already includes article_records with has_started_steps. Used as the "started" count approximation for the compact calendar card display — no extra API call needed.

## Deviations from Plan

None - plan executed exactly as written.

The plan specified timer integration, UUID-based modal, and dashboard progress bar. All were implemented as specified. The timer pause/resume behavior on modal open/close was added as a natural UX improvement that the plan implied but didn't spell out in detail — treated as part of "integrate timer with per-article flow" per the task description.

## Issues Encountered

None. Python executable required full path for syntax verification (known environment limitation from phase 03-01).

## User Setup Required

None.

## Next Phase Readiness

- Phase 3 is now complete: all 3 department views (laser/piega/saldatura) have per-article tracking with Avvia Tutti and UUID-based modal completion
- Dashboard provides management overview with phase progress visualization
- All VISTA-01, VISTA-02, VISTA-03 requirements satisfied
- No further planned phases — project v1.1 feature set complete

## Self-Check: PASSED

- FOUND: app/frontend/piega.html (1409 lines, > 900 minimum)
- FOUND: app/frontend/saldatura.html (1302 lines, > 900 minimum)
- FOUND: app/frontend/dashboard.html (1208 lines, > 800 minimum)
- FOUND: commit 66932ab (Task 1)
- FOUND: commit 38579f1 (Task 2)

---
*Phase: 03-viste-reparto*
*Completed: 2026-02-19*

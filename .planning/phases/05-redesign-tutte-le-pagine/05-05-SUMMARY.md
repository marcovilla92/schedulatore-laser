---
phase: 05-redesign-tutte-le-pagine
plan: 05
subsystem: ui
tags: [html, css, javascript, dashboard, kpi, auto-refresh, search, wcag]

requires:
  - phase: 04-design-system-condiviso
    provides: design.css + shared.js (hasDataChanged, filterOrders, debounce) + Inter WOFF2 fonts

provides:
  - welcome.html come redirect puro a /dashboard.html (meta refresh + JS)
  - dashboard.html ridisegnata con KPI hero row, ordini per urgenza, refresh indicator, ricerca navbar
  - Fetch/render separation che preserva filtri durante auto-refresh
  - Modal dettaglio ordine preservato con progress bar fasi

affects: [future ui phases, any page linking to welcome.html or dashboard.html]

tech-stack:
  added: []
  patterns:
    - fetch/render separation per auto-refresh senza reset filtri
    - urgency classification (scaduto/oggi/futuro) da data_consegna vs today
    - hasDataChanged() da shared.js per evitare re-render quando dati invariati
    - debounce() da shared.js per ricerca navbar
    - KPI computation da array ordini attivi in JS client-side

key-files:
  created: []
  modified:
    - app/frontend/welcome.html
    - app/frontend/dashboard.html

key-decisions:
  - "welcome.html trasformato in redirect puro: meta refresh + JS replace per massima compatibilita browser"
  - "Calendario rimosso e sostituito con vista urgenza — operatori devono vedere ordini per priorita, non per data"
  - "KPI calcolati lato client da array ordini per evitare endpoint dedicati"
  - "phase tags in card calcolati da processing_steps (timestamp_inizio/timestamp_fine) per coerenza con dati esistenti"

patterns-established:
  - "Redirect pagine obsolete: meta http-equiv refresh + JS window.location.replace"
  - "Auto-refresh 10s con hasDataChanged() — no re-render se dati invariati"
  - "applyFiltersAndRender() separato da loadOrders() — filtri sopravvivono all'auto-refresh"

requirements-completed: [DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, FILT-01, FILT-04, ACCS-01, ACCS-02]

duration: 3min
completed: 2026-02-19
---

# Phase 5 Plan 05: Dashboard Redesign Summary

**Dashboard con KPI hero row (ordini attivi/scadenze oggi-settimana/fasi in corso), ordini per urgenza colorata (rosso/ambra/neutro), refresh indicator "X sec fa", ricerca navbar con fetch/render separation — welcome.html ora redireziona a dashboard**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T13:39:45Z
- **Completed:** 2026-02-19T13:42:53Z
- **Tasks:** 2 (combinati in 1 commit — HTML struttura + JS logica in unico file)
- **Files modified:** 2

## Accomplishments

- welcome.html trasformato in redirect puro a /dashboard.html (meta refresh + JS replace)
- dashboard.html completamente ridisegnata: rimosso calendario, aggiunto KPI row + urgency grid
- Ordini ordinati automaticamente per urgenza: scaduti (bordo rosso) in cima, oggi (ambra), futuri (neutro)
- Indicatore "Aggiornato X sec fa" si aggiorna ogni secondo con pulsante "Aggiorna ora"
- Ricerca navbar con debounce 300ms, preservata durante auto-refresh ogni 10s
- Modal dettaglio ordine preservato con progress bar fasi per articolo
- Touch targets: order-card min-height 48px, nav links min-height 40px (WCAG)

## Task Commits

1. **Task 1+2: Redesign welcome.html e dashboard.html** - `ac6bd67` (feat)

**Piano metadata:** (separato — da creare con commit docs)

## Files Created/Modified

- `app/frontend/welcome.html` — Ridotto a 9 righe: redirect puro a /dashboard.html
- `app/frontend/dashboard.html` — Completo redesign: rimosse 1356 righe, aggiunte 396 (net -960)

## Decisions Made

- Calendario rimosso completamente: per operatori di produzione, l'urgenza (scaduto/oggi/futuro) e piu utile di una vista mensile
- KPI calcolati lato client dal JSON ordini — nessun nuovo endpoint backend necessario
- phase tags in ordine-card derivati da processing_steps (timestamp_inizio/timestamp_fine) — stessa fonte dati del modal
- welcome.html mantenuto come file (il backend Flask serve GET / da welcome.html) — solo il contenuto e stato redirect

## Deviations from Plan

None — piano eseguito esattamente come scritto.

## Issues Encountered

None.

## User Setup Required

None — nessuna configurazione esterna richiesta.

## Next Phase Readiness

- Fase 5 (05-01, 05-02, 05-03, 05-04) gia completata in parallelo
- Questa era l'ultima pagina da redesignare nella wave parallela
- Design system completo: tutte le pagine usano design.css + shared.js senza Google Fonts

---
*Phase: 05-redesign-tutte-le-pagine*
*Completed: 2026-02-19*

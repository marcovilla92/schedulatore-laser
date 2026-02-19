---
phase: 05-redesign-tutte-le-pagine
plan: 04
subsystem: ui
tags: [html, css, design-system, glassmorphism, timer, filter, search]

# Dependency graph
requires:
  - phase: 04-design-system-condiviso
    provides: design.css con @layer cascade 7 livelli, shared.js con filterOrders/debounce/hasDataChanged, Inter WOFF2 self-hosted

provides:
  - piega.html ridisegnata con accent ambra, ricerca, chip filtri, timer preservati
  - saldatura.html ridisegnata con accent arancione, ricerca, chip filtri, timer preservati
  - Identita visiva distinta per fase: ambra=piega, arancione=saldatura

affects: [05-05-dashboard, verifica-sistema]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "body[data-page] per accent theming — identico a laser.html e piega/saldatura"
    - "color-mix(in srgb, var(--page-accent) X%, transparent) per varianti cromatiche senza hardcode"
    - "fetch/render separation con hasDataChanged() da shared.js — auto-refresh senza distruggere stato"
    - "timers{} e activePhases{} fuori da renderOrders() — timer attivi sopravvivono ai cicli di re-render"

key-files:
  created: []
  modified:
    - app/frontend/piega.html
    - app/frontend/saldatura.html

key-decisions:
  - "Usare color-mix() invece di colori hardcoded per riutilizzare var(--page-accent) in tutte le varianti cromatiche (border, background, shadow)"
  - "btn-avvia di saldatura usa color:#fff invece di #000 (l'arancione scuro richiede testo bianco per contrasto WCAG AA)"
  - "Timer preservati via pattern restoreTimer: clearInterval + riavvio con startTime originale — aggiorna riferimenti DOM dopo ogni re-render"

patterns-established:
  - "Pattern accent theming: body[data-page='X'] => --page-accent in design.css, poi color-mix() nel CSS inline per tutte le varianti"
  - "Pattern timer preservation: timers{} e activePhases{} globali; renderOrders() chiama restoreTimer() per ogni ordine attivo dopo rebuild DOM"
  - "Pattern fetch/render: loadOrders() => hasDataChanged() => allOrders = orderList => applyFiltersAndRender() => filterOrders() + renderOrders()"

requirements-completed: [REPT-01, ACCS-01, ACCS-02]

# Metrics
duration: 12min
completed: 2026-02-19
---

# Phase 05 Plan 04: Redesign Piega e Saldatura Summary

**piega.html e saldatura.html ridisegnate con design system v1.2: accent ambra/arancione distinti via body[data-page], timer preservati su auto-refresh, ricerca+chip filtri, zero CDN esterni**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-19T14:39:47Z
- **Completed:** 2026-02-19T14:51:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- piega.html: rimosse 3 linee Google Fonts CDN (inclusa JetBrains Mono), aggiunto design.css + shared.js, data-page="piega" attiva accent ambra, ricerca navbar debounced, chip filtri Tutti/In Attesa/In Lavorazione con contatori, timer attivi sopravvivono a cicli auto-refresh 5s
- saldatura.html: identico pattern di piega con accent arancione (rgba 255,99,72), body::before con tinta arancione, color:#fff su btn-avvia per contrasto WCAG su sfondo arancione
- Eliminazione completa dei Google Fonts e JetBrains Mono CDN da entrambe le pagine — zero timeout 30s su LAN
- font monospace sostituito con 'Courier New', 'Lucida Console', monospace (sistema, zero CDN)
- Touch target WCAG: btn-avvia/btn-complete min-height 56px, modal buttons min-height 48px, nav a min-height 40px
- Responsive: 1 colonna sotto 1024px, repeat(auto-fill, minmax(340px,1fr)) sopra 1024px

## Task Commits

Ogni task commitato atomicamente:

1. **Task 1: Ridisegna piega.html** - `71f0481` (feat)
2. **Task 2: Ridisegna saldatura.html** - commit pending (feat)

**Plan metadata:** commit pending (docs)

## Files Created/Modified

- `app/frontend/piega.html` - Pagina piega ridisegnata con accent ambra via var(--page-accent), design.css, shared.js, ricerca+filtri, timer preservati, touch target 48/56px, font monospace sistema
- `app/frontend/saldatura.html` - Pagina saldatura ridisegnata con accent arancione via var(--page-accent), identica struttura piega, btn-avvia#fff per contrasto WCAG

## Decisions Made

- Usato `color-mix(in srgb, var(--page-accent) X%, transparent)` invece di colori hardcoded per tutti border-color, background, shadow — permette di cambiare accent in un unico posto
- btn-avvia saldatura usa `color: #fff` (non `#000` come piega) — l'arancione #ff6348 e abbastanza scuro da richiedere testo bianco per raggiungere 4.5:1 WCAG AA
- Pattern timer: `restoreTimer()` viene chiamato da `renderOrders()` dopo il rebuild DOM per ogni ordine in `activePhases{}` — clearInterval + riavvio con timestamp originale garantisce continuita senza reset

## Deviations from Plan

None - piano eseguito esattamente come scritto.

## Issues Encountered

None.

## User Setup Required

None - nessuna configurazione esterna richiesta. piega.html e saldatura.html usano risorse locali (design.css, shared.js, fonts/) gia presenti dalla Fase 4.

## Next Phase Readiness

- Fase 5 wave parallela: 05-01 (archive), 05-02 (ordini_estratti), 05-03 (laser), 05-04 (piega+saldatura) tutti completati
- Rimane: 05-05 (dashboard.html) — pagina piu complessa con Kanban board
- Pattern fetch/render + timer preservation stabilizzato — 05-05 puo riutilizzarlo

---
*Phase: 05-redesign-tutte-le-pagine*
*Completed: 2026-02-19*

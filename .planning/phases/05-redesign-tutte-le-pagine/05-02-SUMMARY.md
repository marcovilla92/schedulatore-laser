---
phase: 05-redesign-tutte-le-pagine
plan: 02
subsystem: ui
tags: [html, css, design-system, accessibility, wcag, search, filter-chips]

# Dependency graph
requires:
  - phase: 04-design-system-condiviso
    provides: design.css con token CSS e layout base; shared.js con filterOrders() e debounce()

provides:
  - ordini_estratti.html ridisegnata con design system condiviso v1.2
  - Barra di ricerca nella navbar filtra per cliente/numero_ordine/id con debounce 300ms
  - Filtri attivi come chips rimovibili con contatore (FILT-03)
  - Touch target WCAG AA: bottoni 48px+, Salva Fasi 56px, label checkbox 48px (ACCS-01)
  - Testo primario --text-primary, label secondarie --text-secondary (ACCS-02)
  - Layout responsive: <1024px colonna singola, >=1024px griglia 5 colonne fasi

affects: [05-03, 05-04, 05-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "applyFiltersAndRender() come wrapper locale per pagine con campi di filtro aggiuntivi (numero_ordine)"
    - "allOrders[] + searchQuery come stato modulo per ricerca senza auto-refresh"
    - "debounce da shared.js per input di ricerca — 300ms standard"
    - "Chips come feedback visivo dei filtri attivi con contatore risultati"

key-files:
  created: []
  modified:
    - app/frontend/ordini_estratti.html

key-decisions:
  - "Wrapper locale applyFiltersAndRender() invece di filterOrders() da shared.js: ordini_estratti filtra anche su numero_ordine (campo non presente in tutte le pagine)"
  - "cancelEditPhases chiama loadOrders() senza parametro true: la vecchia firma loadOrders(true) non aveva effetto, rimossa per pulizia"
  - "displayOrders() mantenuta come alias di renderOrders() per retrocompatibilita con chiamate interne"

patterns-established:
  - "Pattern: ricerca locale con allOrders[] + applyFiltersAndRender() per pagine senza auto-refresh"
  - "Pattern: chip rimovibile con chip-count mostra numero risultati filtrati in tempo reale"

requirements-completed: [PGSC-01, ACCS-01, ACCS-02, FILT-01, FILT-03]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 5 Plan 02: Ordini Estratti Redesign Summary

**ordini_estratti.html ridisegnata con design.css + shared.js: navbar search debounced filtra per cliente/numero_ordine, chips rimovibili con contatore, touch target WCAG 48px/56px, responsive 1024px**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T13:39:42Z
- **Completed:** 2026-02-19T13:43:04Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Sostituiti Google Fonts CDN con design.css self-hosted — elimina timeout 30sec su LAN
- CSS inline ridotto da ~280 righe a sole regole page-specific (rimossi duplicati di design.css)
- Ricerca nella navbar con debounce 300ms filtra per cliente, numero_ordine e id
- Filtri attivi come chips rimovibili con contatore risultati (FILT-03)
- Touch target WCAG AA implementati: bottoni critici 56px, normali 48px, label checkbox 48px (ACCS-01)
- Tutta la funzionalita esistente preservata: righe espandibili, checkbox fasi, Salva/Annulla, PUT API

## Task Commits

Entrambi i task implementati in un singolo commit atomico:

1. **Task 1: Integrare design system e strippare CSS duplicato** - `a39baf1` (feat)
2. **Task 2: Aggiungere ricerca navbar, filtri chips e wrapper filterOrders** - `a39baf1` (feat)

**Plan metadata:** da creare (docs: complete plan)

## Files Created/Modified
- `app/frontend/ordini_estratti.html` - Pagina ridisegnata con design system condiviso, ricerca navbar, chips filtri, touch target WCAG

## Decisions Made
- Wrapper locale `applyFiltersAndRender()` invece di `filterOrders()` da shared.js: questa pagina filtra anche su `numero_ordine` (campo specifico non presente in tutte le pagine)
- `cancelEditPhases()` ora chiama `loadOrders()` direttamente (rimosso parametro `true` non necessario)
- `displayOrders()` mantenuta come alias di `renderOrders()` per retrocompatibilita

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ordini_estratti.html completamente aggiornata al design system v1.2
- Pattern chips filtri stabilito — replicabile in altre pagine se necessario
- Gli altri 4 piani della Fase 5 (05-01, 05-03, 05-04, 05-05) possono procedere in parallelo senza conflitti

---
*Phase: 05-redesign-tutte-le-pagine*
*Completed: 2026-02-19*

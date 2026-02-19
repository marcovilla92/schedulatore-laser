---
phase: 05-redesign-tutte-le-pagine
plan: 01
subsystem: ui
tags: [html, css, design-system, accessibility, wcag, responsive, archive]

requires:
  - phase: 04-design-system-condiviso
    provides: design.css con token CSS, shared.js con filterOrders/debounce/hasDataChanged, Inter WOFF2 self-hosted

provides:
  - archive.html ridisegnata con design system condiviso v1.2
  - Pattern fetch/render separati per preservare filtri durante auto-refresh
  - Ricerca globale nella navbar con debounce 300ms
  - Filtri attivi come chips rimovibili con contatore

affects:
  - 05-02-ordini_estratti
  - 05-03-laser
  - 05-04-piega-saldatura
  - 05-05-dashboard

tech-stack:
  added: []
  patterns:
    - "Separazione fetch/render: loadOrders() aggiorna allOrders, applyFiltersAndRender() applica filtri e renderizza"
    - "State preservation: searchQuery e clienteFilter sono variabili globali mai resettate dal setInterval"
    - "Debounce su input ricerca (300ms) per evitare chiamate eccessive"
    - "hasDataChanged() da shared.js per evitare re-render se dati invariati"
    - "escapeHtml() per XSS protection su contenuto dinamico"
    - "Chips rimovibili: updateActiveFilters() ridisegna #activeFilters, _chipRemovers[] mantiene riferimenti funzioni"

key-files:
  created: []
  modified:
    - app/frontend/archive.html

key-decisions:
  - "Mantenuto filtro cliente nella filter-bar accanto al filtro ricerca navbar — i due filtri si combinano (AND logic)"
  - "escapeHtml aggiunto come deviation Rule 2 (sicurezza) — non era nel piano ma necessario per XSS protection su dati utente"
  - "Chip contatore mostra solo ordini totali corrispondenti al filtro cliente, non quelli filtrati dalla ricerca navbar"
  - "window._chipRemovers[] come pattern per collegare onclick=\"removeChip(i)\" alle closure di remove"

patterns-established:
  - "Pattern separazione fetch/render per auto-refresh: stabilito su archive.html, da replicare in 05-03/04/05"
  - "Chips rimovibili: .chip.active + .chip-remove visible + removeChip(i) via _chipRemovers[]"

requirements-completed: [PGSC-02, ACCS-01, ACCS-02, FILT-01, FILT-03]

duration: 2min
completed: 2026-02-19
---

# Phase 05 Plan 01: Archive Redesign Summary

**archive.html ridisegnata con design.css + shared.js — ricerca navbar con debounce, chips filtri rimovibili con contatore, auto-refresh 10s che preserva stato ricerca, WCAG touch target 48px, layout responsive 1024px**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-19T13:39:36Z
- **Completed:** 2026-02-19T13:41:36Z
- **Tasks:** 1 di 1
- **Files modified:** 1

## Accomplishments

- Migrato da Google Fonts CDN a design.css con Inter WOFF2 self-hosted (elimina timeout 30sec su LAN)
- Ricerca globale nella navbar con debounce 300ms collegata a filterOrders() da shared.js
- Separazione fetch/render: setInterval(loadOrders, 10000) non azzera mai searchQuery ne clienteFilter
- Filtri attivi visualizzati come chips rimovibili con contatore ordini corrispondenti
- Touch target WCAG AA: min-height 48px su tutti i bottoni filter-bar
- Layout responsive: 3 colonne stats >= 1024px, 2 colonne < 1024px
- Aggiunto escapeHtml() per XSS protection su output dinamico (cliente, ID, status)

## Task Commits

Ogni task committed atomicamente:

1. **Task 1: Ridisegnare archive.html con design system, ricerca, filtri chips e responsive** - `dbd0937` (feat)

**Metadati piano:** (prossimo commit)

## Files Created/Modified

- `app/frontend/archive.html` — pagina archivio ridisegnata con design system condiviso v1.2

## Decisions Made

- Filtro cliente nella filter-bar e ricerca navbar si combinano con logica AND: gli ordini devono soddisfare entrambi i criteri
- escapeHtml() aggiunto per XSS protection — era necessario per sicurezza con dati dinamici (cliente, ID)
- Chip contatore mostra match sul filtro cliente prima dell'applicazione della ricerca navbar (mostra impatto isolato del filtro)
- window._chipRemovers[] per collegare indici numerici onclick a closure JavaScript (pattern semplice e robusto)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Aggiunto escapeHtml() per XSS protection**
- **Found during:** Task 1 (scrittura renderOrders con innerHTML)
- **Issue:** Il piano usava template literals con interpolazione diretta di dati dal backend (order.cliente, order.id, order.status) in innerHTML senza sanitizzazione — vettore XSS se i dati contengono caratteri HTML
- **Fix:** Aggiunta funzione escapeHtml() che sostituisce &, <, >, " con entita HTML, applicata a tutti i valori stringa inseriti dinamicamente
- **Files modified:** app/frontend/archive.html
- **Verification:** Nessun dato utente inserito raw in innerHTML
- **Committed in:** dbd0937 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing critical security)
**Impact on plan:** Auto-fix necessario per sicurezza. Nessun scope creep.

## Issues Encountered

Nessuno.

## User Setup Required

Nessuno — nessun servizio esterno richiede configurazione.

## Next Phase Readiness

- archive.html e pronto e verificato
- Pattern fetch/render separati documentato e pronto per replicazione in 05-02, 05-03, 05-04, 05-05
- I pattern chips rimovibili (updateActiveFilters + _chipRemovers[]) sono disponibili come riferimento per altri piani della wave

---
*Phase: 05-redesign-tutte-le-pagine*
*Completed: 2026-02-19*

## Self-Check: PASSED

- FOUND: app/frontend/archive.html
- FOUND: .planning/phases/05-redesign-tutte-le-pagine/05-01-SUMMARY.md
- FOUND: commit dbd0937 (feat(05-01): redesign archive.html con design system condiviso)

---
phase: 02-assegnazione-fasi
plan: 01
subsystem: ui
tags: [flask, sqlite, html, vanilla-js, glassmorphism, checkbox, article-phases]

# Dependency graph
requires:
  - phase: 01-modello-dati-per-articolo
    provides: "Article model con required_phases JSON, ProcessingStep con article_id, PUT /api/orders/<id>/articles/<article_id>/phases endpoint con 409 per step avviati"
provides:
  - "get_all_orders_dict arricchito con article_records[] (id, name, code, qty, required_phases, has_started_steps)"
  - "Pagina ordini_estratti.html con pannello articoli espandibile e checkbox fasi per articolo"
  - "Salvataggio fasi via PUT /api/orders/{id}/articles/{id}/phases con feedback visivo"
  - "Gestione conflitti 409 per fasi gia avviate (checkbox disabilitate + badge)"
affects: [03-viste-reparto, dashboard, laser, piega, saldatura]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "article_records[] nella risposta API: query Article+ProcessingStep started_count inline nel loop get_all_orders_dict"
    - "Expandable table rows: HTML order-row + articles-panel con toggle via JavaScript"
    - "pendingChanges state: oggetto JS per tracciare modifiche per ordine/articolo prima del salvataggio"
    - "Salvataggio sequenziale asincrono: async/await for...of per chiamate PUT in sequenza"

key-files:
  created: []
  modified:
    - "app/backend/database.py"
    - "app/frontend/ordini_estratti.html"

key-decisions:
  - "article_records[] aggiunto a get_all_orders_dict (non nuovo endpoint): mantiene backward compat, entrambi gli endpoint GET /api/orders e GET /api/extracted-orders beneficiano automaticamente"
  - "started_count query per articolo nel loop: accettabile per le dimensioni tipiche del dataset (non denormalizzato)"
  - "Salvataggio per-ordine (un bottone per ordine) anziché per-articolo: UX migliore per modificare multiple fasi contemporaneamente"
  - "pendingChanges JS object come state tracker: traccia quali articoli sono stati modificati per filtrare le chiamate API solo alle modifiche reali"
  - "Salvataggio sequenziale (for await) anziché parallelo: evita race condition sui ProcessingStep"

patterns-established:
  - "Pattern toggle expand: order-row.expanded + articles-panel.open via classList.toggle"
  - "Pattern checkbox label sync: onchange aggiorna classe .checked sul label parent"
  - "Pattern feedback temporaneo: showFeedback con setTimeout per auto-hide dopo 3s"

requirements-completed: [FASE-01, FASE-02, FASE-03]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 2 Plan 01: Assegnazione Fasi Summary

**Pagina ordini estratti con pannello espandibile per-articolo e checkbox 5 fasi (LASER/PIEGA/SALDATURA/PULIZIA/SPEDIZIONE) — salvataggio via API con blocco su fasi gia avviate (409 Conflict)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T08:55:52Z
- **Completed:** 2026-02-19T08:59:38Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- API `get_all_orders_dict` arricchita con `article_records[]` contenente UUID, nome, codice, quantita, fasi richieste e flag `has_started_steps` per ogni articolo di ogni ordine
- Pagina `ordini_estratti.html` riscritta (1081 righe) con righe espandibili per ordine e pannello articoli con 5 checkbox per fase
- Checkbox disabilitate con badge "In lavorazione" per articoli con fasi gia avviate (`has_started_steps=True`)
- Salvataggio sequenziale asincrono via `PUT /api/orders/{id}/articles/{id}/phases` con feedback visivo (verde/rosso)
- Gestione 409 Conflict con messaggio specifico "Errore: fase gia avviata"
- `updateStats` aggiornata per usare `article_records.length` (v1.1+) con fallback a `articles.length` (legacy)

## Task Commits

Ogni task e stato committato atomicamente:

1. **Task 1: Arricchire risposta API con article_records e stato fasi** - `a9e7b63` (feat)
2. **Task 2: UI checkbox fasi per articolo nella pagina ordini estratti** - `06ac31f` (feat)

**Plan metadata:** (docs commit a seguire)

## Files Created/Modified

- `app/backend/database.py` — aggiunto loop `articles_db` + `article_records_list` in `get_all_orders_dict`; campo `article_records` nella risposta serializzata
- `app/frontend/ordini_estratti.html` — riscritta con CSS espandibile, pannello articoli, checkbox fasi, JS per toggle/save/feedback

## Decisions Made

- `article_records[]` aggiunto direttamente a `get_all_orders_dict` senza creare un nuovo endpoint: entrambi i consumer (`GET /api/orders` e `GET /api/extracted-orders`) beneficiano automaticamente, zero duplicazione
- `started_count` query per articolo inline nel loop: per il dataset tipico (< 100 ordini, < 500 articoli) e accettabile; non denormalizzato perche il dato cambia frequentemente
- Pulsante "Salva Fasi" per-ordine invece che per-articolo: permette di modificare piu articoli e salvare tutto in una sola azione
- `pendingChanges[orderId][articleId] = true` come semplice flag: non serve salvare i valori perche si leggono direttamente dal DOM al momento del salvataggio

## Deviations from Plan

Nessuna — piano eseguito esattamente come scritto.

## Issues Encountered

Nessuno — esecuzione lineare senza blocchi.

## User Setup Required

Nessuno — nessuna configurazione esterna richiesta.

## Next Phase Readiness

- UI assegnazione fasi completa e funzionante
- API `article_records` disponibile per eventuali altri consumer (dashboard, etc.)
- Fase 3 (Viste Reparto) puo procedere: le checkbox e i dati articoli sono ora esposti correttamente
- Nessun blocco identificato

---

## Self-Check

### Files Created

- `.planning/phases/02-assegnazione-fasi/02-01-SUMMARY.md` — questo file

### Files Modified

- `app/backend/database.py` — verificato con `py_compile`, server avviato senza errori
- `app/frontend/ordini_estratti.html` — 1081 righe (> min 400), tutti i pattern chiave presenti

### Commits Verified

- `a9e7b63` — feat(02-01): arricchire risposta API con article_records e stato fasi
- `06ac31f` — feat(02-01): UI checkbox fasi per articolo nella pagina ordini estratti

### API Verification

- `GET /api/extracted-orders` restituisce `article_records` con `id`, `name`, `code`, `qty`, `required_phases`, `has_started_steps` per ogni articolo
- Campi legacy (`articles`, `article_count`, `processing_steps`) ancora presenti (backward compat confermata)
- 5 ordini verificati: `has_started_steps=False` per ordini nuovi, `True` per ordini con fasi avviate

## Self-Check: PASSED

---
*Phase: 02-assegnazione-fasi*
*Completed: 2026-02-19*

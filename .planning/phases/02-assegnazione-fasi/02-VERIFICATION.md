---
phase: 02-assegnazione-fasi
verified: 2026-02-19T10:30:00Z
status: passed
score: 6/6 must-haves verified
re_verification: false
---

# Phase 2: Assegnazione Fasi — Verification Report

**Phase Goal:** Il personale d'ufficio puo assegnare e modificare il set di fasi richieste per ogni articolo in un ordine prima che la produzione inizi
**Verified:** 2026-02-19T10:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Nella pagina ordini estratti, ogni ordine si espande per mostrare i suoi articoli con 5 checkbox (LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE) | VERIFIED | `displayOrders()` in `ordini_estratti.html` line 808: `const PHASES = ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'SPEDIZIONE']`; checkbox render loop at lines 853-865; `.articles-panel` CSS display:none/.open toggle at lines 532-533 |
| 2 | I nuovi ordini mostrano tutte e 5 le checkbox selezionate per ogni articolo | VERIFIED | `app.py` line 64: `article['required_phases'] = ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'SPEDIZIONE']` injected as default when `required_phases` absent; `database.py` line 55: fallback `actual_phases = ... ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'SPEDIZIONE']` |
| 3 | L'utente puo deselezionare/riselezionare qualsiasi combinazione di checkbox e salvare | VERIFIED | `onPhaseCheckboxChange()` at line 934 tracks changes in `pendingChanges`; `savePhases()` at line 961 collects checked phases and calls `PUT /api/orders/${orderId}/articles/${articleId}/phases` |
| 4 | Le checkbox salvate persistono dopo il reload della pagina | VERIFIED | `savePhases()` calls `PUT /api/orders/<id>/articles/<id>/phases` which updates `article.required_phases` in SQLite (app.py lines 224-225); `loadOrders()` re-fetches from `/api/extracted-orders` which reads from DB via `get_all_orders_dict`; full persistence chain confirmed |
| 5 | Le checkbox per fasi gia avviate sono disabilitate e non modificabili | VERIFIED | `get_all_orders_dict` in `database.py` lines 182-194: queries `started_count` via `ProcessingStep.timestamp_inizio.isnot(None)`; frontend line 856: `const disabledAttr = disabled ? 'disabled' : ''`; badge "In lavorazione" rendered at line 874; API returns 409 if `started_steps > 0` (app.py lines 207-216) |
| 6 | Un feedback visivo conferma il salvataggio o mostra errore se la fase e gia avviata | VERIFIED | `showFeedback()` at line 1040: green "Fasi aggiornate" for 3s on success; red "Errore: fase gia avviata — impossibile modificare" on 409 response (line 1014); error feedback stays visible (no auto-hide on error) |

**Score:** 6/6 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/backend/database.py` | `get_all_orders_dict` con `article_records` inclusi (UUID, required_phases, has_started_steps) | VERIFIED | Lines 174-205: queries `Article` records per order, computes `started_count` via `ProcessingStep`, appends `article_records_list` to result dict. `article_records` field present in serialized output at line 205. |
| `app/frontend/ordini_estratti.html` | UI checkbox per assegnazione fasi per articolo, min 400 lines | VERIFIED | 1081 lines confirmed. Full implementation: expandable rows, 5 checkboxes per article, save button, feedback element, `pendingChanges` state tracker, `toggleOrderExpand`, `onPhaseCheckboxChange`, `savePhases` functions. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ordini_estratti.html` | `/api/extracted-orders` | `fetch` in `loadOrders` | WIRED | Line 779: `fetch('/api/extracted-orders')` with `.then(data => displayOrders(data.orders))`. Response consumed. |
| `ordini_estratti.html` | `/api/orders/<id>/articles/<article_id>/phases` | `fetch PUT` in `savePhases` | WIRED | Line 1003: `await fetch(\`/api/orders/${orderId}/articles/${articleId}/phases\`, { method: 'PUT', ... body: JSON.stringify({ required_phases: checkedPhases }) })`. Response parsed and handled. |
| `app/backend/database.py` | `models.Article` | `session.query(Article)` | WIRED | Lines 175-177: `session.query(Article).filter(Article.order_id == order.id).order_by(Article.id).all()`. Result iterated at line 180. |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FASE-01 | 02-01-PLAN.md | L'ufficio puo assegnare le fasi a ogni singolo articolo tramite checkbox (LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE) nella pagina ordini estratti | SATISFIED | 5 checkboxes rendered per article in `ordini_estratti.html` lines 853-865; all 5 phases covered |
| FASE-02 | 02-01-PLAN.md | Di default, articoli nuovi hanno tutte le 5 fasi attive — l'ufficio rimuove quelle non necessarie | SATISFIED | `app.py` line 64 sets all 5 phases when `required_phases` absent; `database.py` line 55 defaults to full PHASE_ORDER |
| FASE-03 | 02-01-PLAN.md | Le fasi assegnate a un articolo possono essere modificate prima che l'articolo inizi la lavorazione in quella fase | SATISFIED | API enforces 409 when `started_steps > 0` (app.py lines 207-216); UI disables checkboxes client-side when `has_started_steps=true` |

No orphaned requirements: FASE-01, FASE-02, FASE-03 are the only IDs mapped to Phase 2 in REQUIREMENTS.md (lines 66-68) and all three are covered by `02-01-PLAN.md`.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/frontend/ordini_estratti.html` | 752 | Hardcoded path `C:/Users/39334/Documents/ORDINI` in `processAllPDFs()` | Warning | Existing pre-phase issue, unrelated to phase 2 goal; PDF processing path was already hardcoded before this phase |

No blocker anti-patterns found. No TODO/FIXME/placeholder comments in modified files. No empty implementations or stub handlers in the phase-2-modified code paths.

---

## Human Verification Required

### 1. Checkbox Toggle and Save Flow

**Test:** Open `http://localhost:5000/ordini-estratti`, click on an order row to expand it, deselect one checkbox (e.g. PULIZIA), click "Salva Fasi", reload the page
**Expected:** The PULIZIA checkbox remains deselected after reload — confirming DB persistence via the UI
**Why human:** Cannot execute a browser session programmatically in this environment to verify DOM state post-reload

### 2. Disabled Checkbox for In-Progress Articles

**Test:** Start a phase for an article via the API or reparto UI, then revisit `ordini_estratti.html`
**Expected:** The article row shows "In lavorazione" badge, all 5 checkboxes are visually greyed out and unclickable, "Salva Fasi" button cannot be enabled for that article
**Why human:** Requires a running server with an active ProcessingStep to verify the disabled state visually

### 3. 409 Conflict Error Message Visibility

**Test:** Manually start a phase for an article, then attempt to save a different phase selection via the UI
**Expected:** Red feedback "Errore: fase gia avviata — impossibile modificare" appears and remains visible
**Why human:** Requires coordinated server state (started step) and live browser interaction

---

## Gaps Summary

No gaps found. All 6 observable truths are verified by the actual codebase. Both modified artifacts (`database.py`, `ordini_estratti.html`) are substantive (not stubs) and fully wired. All 3 key links are confirmed. All 3 requirement IDs (FASE-01, FASE-02, FASE-03) are satisfied with direct code evidence.

The two commits (`a9e7b63`, `06ac31f`) exist and match the claimed changes. The implementation is complete and connected end-to-end: API enriches response with `article_records` → frontend renders 5 checkboxes per article → user changes are tracked in `pendingChanges` → save calls `PUT /api/orders/<id>/articles/<id>/phases` → backend validates, rejects if started (409), persists to SQLite → reload reads fresh state from DB.

---

_Verified: 2026-02-19T10:30:00Z_
_Verifier: Claude (gsd-verifier)_

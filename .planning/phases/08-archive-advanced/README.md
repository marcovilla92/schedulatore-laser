# PHASE 08: Archivio Avanzato — Complete Planning Package

**Planning Date:** 2026-03-02
**Status:** Ready for Execution
**Type:** Feature Implementation (Advanced Admin Archive)

---

## Overview

Fase 8 implementa un **archivio avanzato per amministratore** con:
- Tabella ordini completati (status SPEDITO) con tempi tracciati per fase
- Filtri interattivi (data, cliente, fase) senza page reload
- Ordinamento (data, cliente, numero_articoli) con toggle asc/desc
- Modal dettagli ordine con info complete e timeline delle fasi
- Export CSV per reportistica/analisi
- Design responsive e accessibilità (ARIA labels, keyboard navigation)

Ordini completati mostrano: **LASER time + PIEGA time + SALDATURA time + Tempo Totale**

---

## Planning Structure

### Tre Piani Eseguibili (3 Plans)

| Plan | Scope | Duration | Wave | Depends On |
|------|-------|----------|------|-----------|
| **08-01** | Backend: ArchiveManager + API endpoints | 15-20 min | 1 | None |
| **08-02** | Frontend: screen-archive UI + JavaScript | 25-30 min | 2 | 08-01 |
| **08-03** | Testing: Playwright suite + validation | 20-25 min | 3 | 08-01, 08-02 |

**Total Time:** ~60-75 minuti
**Can Parallelize:** Wave 2 e 3 can start once Wave 1 API è pronto

---

## Plan Details

### Plan 08-01: Backend ArchiveManager + API (Wave 1)

**Objective**: Implementare backend per archivio — query ordini completati, calcolo tempi per fase, API endpoint con filtri, paginazione, export CSV.

**Files Modified:**
- `app/backend/database.py` — Add ArchiveManager class
- `app/backend/app.py` — Add 3 new endpoints

**Tasks**:

#### Task 1: ArchiveManager Class
Implementare classe statica `ArchiveManager` in `database.py` con 4 metodi:

1. **`_calculate_phase_times(order_id, session) -> dict`**
   - Calcola durata per fase: end_time - start_time
   - Ritorna: `{"LASER": "2h 15min", "PIEGA": "1h 30min", "SALDATURA": "3h 45min", "total_time": "7h 30min"}`
   - Usa `OrderManager._format_duration()` esistente
   - Se fase non completata, ritorna None

2. **`get_completed_orders(filters=None, page=1, page_size=50, sort_by='data_completamento', sort_order='desc') -> dict`**
   - Query `Order` con `status == 'SPEDITO'`
   - Supporta filtri: `date_from`, `date_to`, `cliente`, `phase`
   - Paginate: `offset = (page-1)*page_size, limit = page_size`
   - Ordinabile per: `data_completamento`, `cliente`, `numero_articoli`
   - Ritorna:
     ```json
     {
       "total": 250,
       "page": 1,
       "page_size": 50,
       "orders": [
         {
           "id": "uuid-1",
           "numero_ordine": "ORD-2026-001",
           "cliente": "ABC Spa",
           "data_creazione": "2026-01-15T10:00:00",
           "data_completamento": "2026-01-20T16:30:00",
           "tempi_per_fase": {"LASER": "2h 15min", "PIEGA": "1h 30min", "SALDATURA": "3h 45min"},
           "tempo_totale": "7h 30min",
           "numero_articoli": 45,
           "status": "SPEDITO"
         },
         ...
       ]
     }
     ```

3. **`get_order_details(order_id) -> dict`**
   - Ritorna dettagli completi singolo ordine:
     ```json
     {
       "id": "uuid-1",
       "numero_ordine": "ORD-2026-001",
       "cliente": "ABC Spa",
       "data_creazione": "2026-01-15T10:00:00",
       "data_consegna": "2026-01-25T00:00:00",
       "articoli": [...],
       "status": "SPEDITO",
       "tempi_per_fase": {
         "LASER": {"inizio": "...", "fine": "...", "durata": "2h 15min"},
         "PIEGA": {"inizio": "...", "fine": "...", "durata": "1h 30min"},
         "SALDATURA": {"inizio": "...", "fine": "...", "durata": "3h 45min"}
       },
       "tempo_totale": "7h 30min",
       "numero_articoli": 45
     }
     ```

4. **`export_csv_data(filters=None) -> list`**
   - Esporta TUTTI gli ordini completati come lista dict (non paginated)
   - Colonne: `id, numero_ordine, cliente, data_completamento, LASER_time, PIEGA_time, SALDATURA_time, tempo_totale, numero_articoli, status`

#### Task 2: 3 API Endpoints
Aggiungi in `app.py`:

1. **`GET /api/archive/orders`**
   - Query params: `page`, `page_size`, `sort_by`, `sort_order`, `date_from`, `date_to`, `cliente`, `phase`
   - Response: 200 OK + JSON structure da `ArchiveManager.get_completed_orders()`
   - Error handling: 400 for invalid filters, 500 for exceptions

2. **`GET /api/archive/orders/<order_id>/details`**
   - Response: 200 OK + JSON from `ArchiveManager.get_order_details(order_id)`
   - Errors: 404 if order not found, 400 if not SPEDITO, 500 for exceptions

3. **`GET /api/archive/export/csv`**
   - Query params: same as `/api/archive/orders` (no pagination)
   - Response: 200 OK + CSV file download
   - Headers: `Content-Type: text/csv`, `Content-Disposition: attachment; filename="archive_export_YYYY-MM-DD_HHMMSS.csv"`
   - CSV format: header row + data rows

**Verification**:
- Test data creato (curl to create 10 SPEDITO ordini)
- Tutti 3 endpoint rispondono 200 OK
- Filtri validati
- CSV file downloadabile
- Phase times calcolati correttamente
- Paginazione funziona

---

### Plan 08-02: Frontend screen-archive + JavaScript (Wave 2)

**Objective**: Implementare frontend admin per archivio — tabella ordini completati, filtri interattivi, ordinamento, export PDF/CSV, modal dettagli con full responsive design e accessibility.

**Files Modified:**
- `app/frontend/admin.html` — Add screen-archive + styles + scripts

**Tasks**:

#### Task 1: HTML + CSS Base Structure
Aggiungi in `admin.html`:

1. **Nav button in sidebar**: `<button class="sidebar-btn archive-btn">📦 Archivio Ordini</button>`

2. **Screen HTML** (`#screen-archive`):
   - Titolo "Archivio Ordini Completati"
   - Filtri row (date-from, date-to, cliente, phase, clear-filters button)
   - Controls row (sort dropdown, sort toggle button, export CSV/PDF buttons)
   - Tabella con thead (Numero Ordine, Cliente, Data Completamento, LASER, PIEGA, SALDATURA, Tempo Totale, Articoli, Azioni)
   - Tbody (riempito da JavaScript)
   - Paginazione (prev/next buttons, page info)
   - Modal per dettagli (hidden, mostra details)

3. **CSS Styling**:
   - Grid layout per filtri (responsive auto-fit, minmax 200px)
   - Table styling (thead background, hover rows, monospace time cells)
   - Modal overlay + content box
   - Responsive breakpoints (375px, 768px, 1200px)
   - Color scheme consistent with admin.html (--ls-green, --text-secondary, etc.)

#### Task 2: JavaScript State + Event Listeners
Aggiungi in `admin.html` script:

1. **Global state**: `archiveState = { currentPage, pageSize, totalPages, sortBy, sortOrder, filters }`

2. **Main function**: `loadArchiveOrders()`
   - Fetch `/api/archive/orders` con query params da archiveState
   - Show loading spinner
   - Render table con `renderArchiveTable(orders)`
   - Update pagination info
   - Handle errors

3. **Helper functions**:
   - `renderArchiveTable(orders)` — populate tbody with rows
   - `updatePaginationInfo()` — update page counter, enable/disable buttons
   - `showElement(id)` / `hideElement(id)` — show/hide divs
   - `updateSortToggleButton()` — update ↑/↓ icon

4. **Event listeners**:
   - Filter inputs (`#archive-date-from`, `#archive-date-to`, `#archive-cliente`, `#archive-phase`): change → reset page 1, load orders
   - Sort dropdown (`#archive-sort-by`): change → load orders
   - Sort toggle (`#archive-toggle-sort`): click → toggle asc/desc, update icon, load orders
   - Pagination buttons (`#archive-prev-page`, `#archive-next-page`): click → update page, load orders
   - Clear filters button (`#archive-clear-filters`): click → reset all filters, load orders

#### Task 3: Modal Dettagli + Export Functions

1. **`showArchiveDetails(orderId)`**
   - Fetch `/api/archive/orders/<id>/details`
   - Populate modal HTML with:
     - Numero ordine, cliente, date, articoli count
     - Tabella tempi per fase (fase, inizio, fine, durata)
     - Tabella articoli (nome, codice, quantità, fasi richieste)
   - Show modal (display: flex)
   - Add close listeners (X button, click outside)

2. **`exportArchiveCSV()`**
   - Fetch `/api/archive/export/csv?filters=...` (apply current filters)
   - Get blob response
   - Create blob URL + trigger download with suggested filename
   - Clean up blob URL

3. **`exportArchivePDF()` (placeholder)**
   - Alert: "PDF export non ancora implementato. Usa CSV per ora."

**Verification**:
- Browser load admin.html, login, click "Archivio"
- Screen mostra (non blank)
- Filtri input visibili
- Tabella con almeno 1 riga (da test data)
- Click filtro → table updates senza reload
- Click ordinamento → table riordina
- Click pagination prev/next → page counter cambia
- Click "Dettagli" → modal appare
- Click modal X → chiude
- Click "CSV export" → file scaricato (check Downloads)
- Mobile responsive (zoom 75%)
- No console errors

---

### Plan 08-03: Testing + Validation (Wave 3)

**Objective**: Implementare Playwright test suite per archivio — E2E UI test, API test, performance test, accessibility test.

**Files Created:**
- `.claude/skills/webapp-testing/test_archive.py` — Playwright test suite

**Tasks**:

#### Task 1: Create Test Data
Helper function `create_archive_test_data()` in `app.py`:
- Crea 10 ordini SPEDITO con:
  - Clienti variati (5 diversi)
  - Articoli multipli per ordine
  - Tempi realistici per fase (LASER 2-3h, PIEGA 1-2h, SALDATURA 2-4h)
  - Spacing date (da -30 giorni a oggi)

Can be called via:
- POST `/api/test/create-archive-data` endpoint, OR
- Auto-called in `initialize_database()` at startup

#### Task 2: Playwright Test Suite
File: `.claude/skills/webapp-testing/test_archive.py` with 8 test classes:

1. **TestArchiveLoading** (3 tests)
   - Archive screen carica senza errori
   - Tabella mostra tutte le colonne
   - Tempi per fase formattati correttamente

2. **TestArchiveFilters** (3 tests)
   - Filtro data 'da' funziona
   - Filtro cliente funziona
   - Bottone clear-filters resetta

3. **TestArchiveSort** (2 tests)
   - Dropdown ordinamento funziona
   - Toggle asc/desc funziona

4. **TestArchiveModal** (3 tests)
   - Modal apre su click "Dettagli"
   - Modal contiene info ordine
   - Modal chiude su X o click outside

5. **TestArchiveExport** (1 test)
   - CSV export scarica file valido

6. **TestArchivePagination** (2 tests)
   - Pagination disabled a pagina 1
   - Page info mostra numero pagina

7. **TestArchivePerformance** (1 test)
   - Archive carica in < 2 secondi

8. **TestArchiveAccessibility** (2 tests)
   - ARIA labels presenti
   - Keyboard navigation (Tab) funziona

**Total**: 17 test cases

**Verification**:
- Run tests: `pytest test_archive.py -v --headed` (or `-v` only)
- Expected: 17/17 passed (or skip gracefully)
- No Python errors
- No browser console errors during tests
- CSV file valid (readable, header + data)
- All accessibility checks pass
- Performance < 2 sec

---

## Execution Workflow

### Pre-Execution Checklist
- [ ] Database present at `app/database/scheduler.db`
- [ ] Flask server NOT running (will be started by tests if needed)
- [ ] Python environment with SQLAlchemy, Flask, Playwright
- [ ] Browser (Chrome/Chromium) installed for Playwright

### Execution Steps

**Step 1: Execute Plan 08-01 (Backend)**
```bash
cd /path/to/schedulatore-laser
/gsd:execute-phase 08 --plan 01
```

Expected output:
- ArchiveManager class added to database.py
- 3 new endpoints registered in app.py
- All tasks verified (tests pass)
- SUMMARY.md created

**Step 2: Execute Plan 08-02 (Frontend)**
```bash
/gsd:execute-phase 08 --plan 02
```

Expected output:
- screen-archive HTML added to admin.html
- CSS styled and responsive
- JavaScript functions implemented
- All event listeners hooked
- All tasks verified (browser tests pass)
- SUMMARY.md created

**Step 3: Execute Plan 08-03 (Testing)**
```bash
/gsd:execute-phase 08 --plan 03
```

Expected output:
- Test data created (10 ordini SPEDITO)
- test_archive.py created with 17 test cases
- All tests pass (17/17)
- Performance verified
- SUMMARY.md created

### Post-Execution
- Review all 3 SUMMARY.md files
- Run full test suite: `pytest test_archive.py -v`
- Manual test in browser: login as admin, navigate to Archive
- Push to GitHub: `git push origin stefano/sviluppo`

---

## Requirements Coverage

This phase addresses **6 requirements**:

| Req ID | Description | Plan | Task |
|--------|-------------|------|------|
| ARCHIVE-01 | Tabella ordini completati con tempi per fase | 08-01, 08-02 | Task 1, 2 |
| ARCHIVE-02 | Filtri (data, cliente, fase) funzionanti | 08-02 | Task 2 |
| ARCHIVE-03 | Ordinamento (data, cliente, qty) con asc/desc | 08-02 | Task 2 |
| ARCHIVE-04 | Modal dettagli ordine con info complete | 08-02 | Task 3 |
| ARCHIVE-05 | Export CSV con filtri applicati | 08-02 | Task 3 |
| ARCHIVE-06 | Responsive design + accessibility (ARIA, keyboard) | 08-02, 08-03 | Task 1, 2 |

---

## Architecture Highlights

### Backend Pattern
- **ArchiveManager** = static class, same pattern as **UserManager** + **AuditManager**
- **No new database tables** = Uses existing Order, ProcessingStep (v1.2 schema)
- **No new dependencies** = Pure SQLAlchemy, standard Flask response

### Frontend Pattern
- **Vanilla JavaScript** = No React/Vue/Svelte, consistent with existing codebase
- **Client-side state** = Simple `archiveState` object, easy to debug
- **Inline CSS** = Single admin.html file, no external stylesheets
- **Accessibility-first** = ARIA labels, keyboard navigation, semantic HTML

### Performance
- **Client-side pagination** = 50 items/page, OK for 1000 items
- **Single API call per load** = No N+1 queries
- **CSV export** = Server-side CSV generation, no client-side processing

---

## Known Limitations & Future Enhancements

1. **Pagination**: Assumes < 1000 completed orders. If more, need server-side pagination.
2. **PDF Export**: Not implemented (CSV only). Can add jsPDF later.
3. **Real-time Refresh**: No auto-update. Can add 30-sec refresh or WebSocket.
4. **Advanced Analytics**: No KPI cards (avg time/phase, SLA violations). Can add later.
5. **Bulk Operations**: No multi-select, bulk delete, or mark-as-archived. Can add later.
6. **Audit Trail**: Archive operations not logged. Can add later.

---

## References & Links

- **CONTEXT.md** — Planning decisions and rationale
- **.planning/ROADMAP.md** — Phase 8 in roadmap context
- **CLAUDE.md** — Project conventions, tech stack
- **app/backend/models.py** — Order, ProcessingStep schema
- **app/backend/database.py** — UserManager, AuditManager patterns
- **app/frontend/admin.html** — Existing UI structure

---

## Success Criteria (Phase Complete)

- [ ] All 3 plans executed successfully
- [ ] ArchiveManager fully implemented with 4 methods
- [ ] 3 API endpoints responding correctly
- [ ] screen-archive displays with all UI elements
- [ ] Filters apply without page reload
- [ ] Sorting works (all 3 fields, asc/desc toggle)
- [ ] Modal opens/closes cleanly
- [ ] CSV export produces valid file
- [ ] Playwright tests pass (17/17)
- [ ] Mobile responsive (375px+)
- [ ] ARIA labels present, keyboard navigation works
- [ ] No console errors
- [ ] Performance OK (< 2 sec for 100+ orders)
- [ ] All code committed to `stefano/sviluppo` branch

---

**Planning Complete ✓**
Ready for execution via `/gsd:execute-phase 08`

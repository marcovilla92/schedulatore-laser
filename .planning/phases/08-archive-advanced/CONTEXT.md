# Phase 8: Archivio Avanzato — Planning Context

**Planning Date:** 2026-03-02
**Phase:** 08-archive-advanced
**Plans:** 3 (independent execution waves)

---

## User Vision (da requisiti)

Admin vuole:
1. **Visualizzare archivio** — tabella ordini completati (status SPEDITO)
2. **Tracciare tempi** — LASER, PIEGA, SALDATURA come colonne separate + tempo totale aggregato
3. **Filtrare** — data completamento (da/a), cliente, fase
4. **Ordinare** — per data, cliente, numero_articoli (asc/desc)
5. **Esportare** — CSV per reportistica/analisi
6. **Dettagli** — modal con info completa (date, articoli, tempi per fase)
7. **Responsivo** — mobile-friendly
8. **Accessibile** — ARIA labels, keyboard navigation

---

## Architecture Decisions

### 1. Backend: ArchiveManager classe (pattern consistency)
**Decision**: Implementare `ArchiveManager` in `database.py` come classe statica con metodi pubblici.

**Why**:
- Consistency con `UserManager` e `AuditManager` esistenti
- Separation of concerns (DB logic in database.py, API routing in app.py)
- Easy to test (direct imports, no Flask context needed)

**Methods**:
- `get_completed_orders(filters, page, page_size, sort_by, sort_order)` → dict paginated
- `get_order_details(order_id)` → dict with full details
- `export_csv_data(filters)` → list of dicts (CSV-ready)
- `_calculate_phase_times(order_id, session)` → dict with durations

### 2. Frontend: Vanilla JavaScript (no new dependencies)
**Decision**: Implementare UI in `admin.html` con vanilla JavaScript (no React, Vue, Svelte).

**Why**:
- Consistent con architettura esistente (admin.html, login.html, carica-ordine.html)
- No new npm dependencies to manage
- Simple to maintain and modify
- Fast startup time

**State Management**: Global `archiveState` object (simple, effective for single-screen app)

### 3. UI Pattern: screen-archive (template consistency)
**Decision**: Aggiungere nuovo `<div class="screen" id="screen-archive">` a admin.html con inline CSS.

**Why**:
- Consistent con existing screens (screen-kpi, screen-audit, etc.)
- Self-contained HTML (single file, easy to edit)
- No build step needed

### 4. Pagination: Client-side, 50 items/page
**Decision**: Pagina 50 ordini per volta, controls prev/next, load all data server-side (no offset-limit).

**Why**:
- Most archives don't exceed 1000 items (50 items = 20 pages max)
- Simpler backend (no page param needed for now)
- Can optimize later if needed (add server-side pagination)
- Better UX (sort/filter applied to all data)

**Limitation**: If 10,000+ orders, will need server-side pagination (TODO for future).

### 5. Filtering: Client-side immediate application
**Decision**: onChange listener on every filter input → immediate `loadArchiveOrders()`.

**Why**:
- No page reload needed (smooth UX)
- Real-time visual feedback
- Consistent with modern web apps

**Limitation**: If filtering 10,000+ items, consider debounce or server-side filters.

### 6. Export: CSV only (no PDF for now)
**Decision**: Implementare CSV export, placeholder per PDF.

**Why**:
- CSV è universal (Excel, Google Sheets, Python pandas)
- Easy to generate (Python csv module)
- PDF would require jsPDF or server-side library (extra dependency)
- Can add PDF later if needed

### 7. Times per Fase: Derived from ProcessingStep timestamps
**Decision**: Calcolare LASER_time, PIEGA_time, etc. da `ProcessingStep.timestamp_fine - timestamp_inizio`.

**Why**:
- Data already exists (v1.2.1 hotfix added timestamps)
- No schema migration needed
- Timestamp logic already proven (used in OrderNotification.tempi_totali)

**Format**: "2h 15min" (human-readable, matches existing patterns)

### 8. Data Completamento: Last phase completion time
**Decision**: `data_completamento` = max(ProcessingStep.timestamp_fine) per ordine.

**Why**:
- Represents when order actually left the facility
- More accurate than order.data_consegna (which is customer deadline)
- Enables KPI: "ordini completati in tempo" calculation

### 9. Modal: Inline in HTML, shown via JavaScript
**Decision**: Hidden `#archive-modal` div, populated via `showArchiveDetails(orderId)`.

**Why**:
- No external dependencies (no modal library)
- Easy to style with CSS
- Close on X button or click outside

### 10. Accessibility: ARIA labels + keyboard navigation
**Decision**: Add `<label for=...>` for every input, Tab order correct, enter key to submit.

**Why**:
- WCAG 2.1 AA compliance
- Better for users with screen readers
- Better for power users (keyboard-only navigation)

---

## Implementation Plan Breakdown

### Wave 1 (Plan 08-01): Backend ArchiveManager + API
- Task 1: ArchiveManager class in database.py (4 methods)
- Task 2: 3 API endpoints in app.py (GET /api/archive/orders, GET /api/archive/orders/<id>/details, GET /api/archive/export/csv)
- **Duration**: ~15-20 min
- **Dependencies**: None (v1.2 database schema already has all needed fields)
- **Autonomous**: Yes (no human input needed)

### Wave 2 (Plan 08-02): Frontend screen-archive
- Task 1: HTML structure + base CSS (grid layout, filters, table)
- Task 2: JavaScript (state management, event listeners, loadArchiveOrders, filtering, sorting, pagination)
- Task 3: Modal details + CSV export functions
- **Duration**: ~25-30 min
- **Dependencies**: Wave 1 (needs API endpoints)
- **Autonomous**: Yes (except for minor styling tweaks user might want)

### Wave 3 (Plan 08-03): Testing + validation
- Task 1: Create test data (10 ordini SPEDITO with realistic times)
- Task 2: Playwright test suite (17 test cases, 8 test classes)
- **Duration**: ~20-25 min
- **Dependencies**: Wave 1 + 2 (needs working API + UI)
- **Autonomous**: Yes (tests auto-run, results clear)

**Total Time**: ~60-75 minutes
**Can Run in Parallel**: Wave 2 and 3 can start once Wave 1 API is ready

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Archive screen loads | < 2 sec for 100 orders | Time from click to table rendered |
| Filters apply | No page reload | UI updates immediately on input change |
| Sort works | All 3 sort fields | Verify order changes (by date, client, qty) |
| CSV export | Valid file, readable | Open in Excel/Sheets, check header + rows |
| Modal open/close | Smooth animation | No errors, modal appears/disappears correctly |
| Accessibility | WCAG 2.1 AA | ARIA labels present, keyboard navigation works |
| Responsive | Mobile 375px OK | Test at breakpoints (375, 768, 1200) |
| Tests pass | 17/17 | Playwright test suite all green |

---

## Known Limitations & TODO

1. **No server-side pagination** — assumes < 1000 completed orders. If more, will need to:
   - Add page/page_size params to backend
   - Implement offset-limit SQL queries
   - Remove client-side 50-item limit

2. **No PDF export** — only CSV. To add PDF:
   - Install jsPDF
   - Create task in modal with "Download PDF" button
   - Generate PDF client-side or server-side

3. **No real-time refresh** — archive screen doesn't auto-update. To add:
   - `setInterval(loadArchiveOrders, 30000)` for 30-sec refresh
   - Or WebSocket for real-time updates

4. **No advanced analytics** — no KPI cards (avg time per phase, SLA violations, etc.). To add:
   - Create new endpoint `/api/archive/stats`
   - Add ArchiveManager methods for aggregations
   - New section in screen-archive for KPI cards

5. **No bulk operations** — can't bulk-delete or mark as archived. To add:
   - Checkboxes on each row
   - Bulk action buttons
   - Backend DELETE endpoint

6. **No audit trail** — archive operations not logged. To add:
   - Call AuditManager.log on export/view
   - Track who accessed which ordini

---

## Dependencies

### External Libraries
- None new (uses existing: SQLAlchemy, Flask, Playwright for testing)

### Database Schema
- Already present: Order, ProcessingStep (from v1.2)
- No migrations needed

### API Endpoints (to be created)
- `GET /api/archive/orders` (paginated list with filters)
- `GET /api/archive/orders/<id>/details` (single order details)
- `GET /api/archive/export/csv` (CSV file download)

### Frontend Assets
- Font: Inter (already loaded in admin.html)
- Colors: --ls-green, --ls-gray, --bg-light (already defined)
- No new SVG icons needed (reuse existing library)

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Phase times wrong | Medium | Medium | Test calculation with manual verification (Task 1 verify step) |
| CSV format invalid | Low | High | Validate CSV header + rows (Task 3 verify step) |
| Modal doesn't close | Low | Medium | Test close button + click-outside (Task 3 verify step) |
| Slow page load (100+ orders) | Low | Medium | Profile with DevTools, optimize queries if needed |
| Accessibility fails | Low | Medium | Run accessibility scan (automated in Task 3) |

---

## Rollout Plan

1. **Test locally** (Plan 08-01 & 02): Run tests before committing
2. **Code review**: Check database changes, API response format
3. **Deploy to dev**: Push to stefano/sviluppo, test on local network
4. **User feedback**: Show to admin, get feedback on UX/filters
5. **Iterate**: If issues found, create gap-closure plans
6. **Deploy to prod**: Merge to master

---

## Success Criteria (Phase Complete)

- [ ] ArchiveManager fully implemented with 4 methods
- [ ] 3 API endpoints respond correctly
- [ ] screen-archive displays with all UI elements
- [ ] Filters apply without page reload
- [ ] Sorting works (asc/desc)
- [ ] Modal opens/closes cleanly
- [ ] CSV export produces valid file
- [ ] Playwright tests pass (17/17)
- [ ] Mobile responsive (375px+)
- [ ] ARIA labels present
- [ ] No console errors
- [ ] Performance OK (< 2 sec for 100+ orders)

---

## References

- `.planning/PROJECT.md` — Project overview
- `.planning/STATE.md` — Current state
- `app/backend/models.py` — Order, ProcessingStep schema
- `app/backend/database.py` — UserManager, AuditManager (patterns to follow)
- `app/frontend/admin.html` — Existing UI structure
- `CLAUDE.md` — Project conventions and tech stack

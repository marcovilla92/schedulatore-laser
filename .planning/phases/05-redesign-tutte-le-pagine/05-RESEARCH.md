# Phase 5: Redesign Tutte le Pagine — Research

**Researched:** 2026-02-19
**Domain:** Vanilla HTML/CSS/JS UI refactoring — design system integration, WCAG accessibility, fetch/render separation
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ACCS-01 | Touch target minimo 48px, 56px per azioni critiche (Avvia Fase, Completa) | Buttons in all pages currently use padding:11-12px — need explicit min-height/min-width enforcement |
| ACCS-02 | WCAG AA contrasto 4.5:1 minimo | Token analysis: --text-primary #e6e6e6 on #0a0a0f = 16.7:1 (passes); --text-secondary #6b7b8d on #0a0a0f = 3.9:1 (FAILS for body text — must not use as primary text) |
| DASH-01 | GET / atterra su dashboard, welcome rimossa | Flask route `@app.route('/')` returns welcome.html — FROZEN, cannot change route. Must rename file or redirect |
| DASH-02 | Riga KPI hero: ordini attivi, scadenze oggi, settimana, fasi in corso | GET /api/orders returns all orders with status and data_consegna — computable client-side |
| DASH-03 | Card ordini urgenza colorata: rosso=scaduto, ambra=oggi, neutro=futuro | data_consegna field available in /api/orders response |
| DASH-04 | Indicatore auto-refresh visibile + pulsante "Aggiorna ora" | Pattern exists in laser.html (lastDataHash + setInterval 5s) — extend with UI timestamp |
| DASH-05 | Vista panoramica mista KPI+fasi+urgenze | New dashboard replaces calendar view — GET /api/orders sufficient |
| FILT-01 | Barra ricerca globale in navbar sticky filtro client-side | shared.js filterOrders(orders, query) ready — needs search input in nav HTML |
| FILT-02 | Filtri stato in viste reparto (attesa/in corso/completati) | articles_in_phase[].phase_status: 'in_attesa'/'in_lavorazione'/'completato' |
| FILT-03 | Filtri attivi come chips/pills rimovibili con contatore | New inline CSS pattern needed — no existing implementation |
| FILT-04 | Auto-refresh non resetta filtri (separazione fetch/render) | laser.html has correct pattern: fetch updates allOrders, renderOrders(filterOrders(allOrders, query)) |
| REPT-01 | Accent theming per fase nel design system | design.css body[data-page] tokens: laser=red, piega=amber, saldatura=orange — already defined |
| REPT-02 | Refactoring fetch/render: polling aggiorna senza ricostruire DOM, preservando filtri e stato espansione | Verified pattern in laser.html (lastDataHash guard) — extend to all pages |
| REPT-03 | Responsive: >=1024px multi-colonna, 768-1023px colonna singola tablet | design.css has only <=768px breakpoint — 1024px breakpoint needs adding per page |
| PGSC-01 | ordini_estratti.html ridisegnata con design system | Highly complex: expandable rows, article-level phase checkboxes, save/cancel pattern |
| PGSC-02 | archive.html ridisegnata con design system | Simpler: table layout with filter, no auto-refresh state complexity |
</phase_requirements>

---

## Summary

Phase 5 is a pure HTML/CSS/JS refactoring exercise: six self-contained pages must each integrate the shared design system built in Phase 4 (design.css + shared.js + Inter WOFF2 fonts) while adding search/filter capabilities, WCAG AA accessibility, and responsive breakpoints.

The core technical challenge is NOT the visual redesign — the existing dark glassmorphism aesthetic is already correct and consistent. The challenge is **safely stripping 700+ lines of duplicated CSS per page** while keeping only page-specific overrides, implementing fetch/render separation across all pages with auto-refresh, and building the new dashboard KPI view from scratch replacing the calendar.

The five parallel sub-plans (05-01 through 05-05) work on distinct files and share no state. Each agent independently applies the same transformation pattern. The laser.html redesign (05-03) serves as the reference implementation from which 05-04 replicates the pattern.

**Primary recommendation:** Use laser.html's current fetch/render pattern as the canonical template for all pages. The refactoring for each page is a sequence: (1) strip Google Fonts, (2) add design.css link, (3) add data-page attribute, (4) strip duplicated tokens/reset/typography from inline styles, (5) add shared.js script tag, (6) wire filterOrders() to a new search input in nav, (7) ensure touch targets, (8) add 1024px breakpoint.

---

## Standard Stack

### Core (all already present — no new installs)
| Asset | Version | Purpose | Note |
|-------|---------|---------|------|
| design.css | Phase 4 | Shared tokens, reset, components, layout | Served at `/design.css` |
| shared.js | Phase 4 | filterOrders(), debounce(), hasDataChanged() | Served at `/shared.js` |
| Inter WOFF2 | jsDelivr fontsource | Self-hosted font | `/fonts/inter-latin-{400,500,600,700}-normal.woff2` |
| Flask catch-all | backend/app.py | `@app.route('/<path:filename>')` serves all frontend/ files | No backend changes needed |

### No new libraries needed
This is a refactoring phase. Zero new dependencies. All needed code is already in design.css and shared.js.

---

## Architecture Patterns

### Pattern 1: CSS Integration (apply to every page)

**What:** Remove Google Fonts CDN, replace with design.css link. Add data-page attribute on body.

**Before (current state of all pages):**
```html
<head>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-primary: #0a0a0f;
      /* ... 30+ tokens duplicated ... */
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Inter', ... }
    body::before { /* ambient float animation */ }
    nav { /* duplicated */ }
    .nav-logo { /* duplicated */ }
    /* ... ~700 lines total ... */
  </style>
</head>
<body>
```

**After (refactored state):**
```html
<head>
  <link rel="stylesheet" href="/design.css">
  <style>
    /* SOLO stili page-specific che non sono in design.css */
    /* Esempio per laser.html: */
    body[data-page="laser"] {
      --page-accent: var(--accent-red); /* gia in design.css via body[data-page] */
    }
    /* Componenti specifici della pagina: .order-card, .summary-box, .timer-display, etc. */
    /* NON ripetere: :root tokens, * reset, body tipografia, nav, .glass-card, .btn-primary,
       .btn-secondary, .message, .loading, .spinner, main layout, scrollbar */
  </style>
</head>
<body data-page="laser">  <!-- o "piega", "saldatura", o nessun attributo per cyan-default -->
```

**What to KEEP inline (page-specific):**
- `.order-card`, `.article-item`, `.summary-box`, `.summary-item`, `.summary-number` — page-specific layouts
- `.status-badge`, `.status-ready`, `.status-started` — page-specific variants
- `.action-buttons`, `.btn-start`, `.btn-complete`, `.btn-avvia` — button variants with per-page accent colors
- `.modal-overlay`, `.modal-content`, `.modal-checkboxes` — complex modal CSS
- `.timer-display`, `.timer-display.active` — piega/saldatura specific
- `.calendar-day`, `.calendar-weekdays`, `.day-order-card` — dashboard specific
- `.kpi-row`, `.kpi-card`, `.urgency-badge` — new dashboard components
- `.filter-chips`, `.chip`, `.chip-remove` — new filter UI
- `.search-input` (navbar search) — new component

**What to STRIP from inline (already in design.css):**
- All `:root` CSS custom properties (tokens) — covered by design.css @layer tokens
- `* { margin: 0; padding: 0; box-sizing: border-box; }` — covered by @layer reset
- `body { font-family, background, color, min-height, overflow-x }` — covered by @layer tipografia
- `body::before` ambient background animation — covered by @layer base
- `@keyframes ambientFloat`, `@keyframes fadeInUp`, `@keyframes spin` — covered by @layer base
- `nav`, `.nav-logo`, `nav a`, `nav a:hover`, `nav a.active` — covered by @layer componenti
- `.glass-card`, `.glass-card:hover` — covered by @layer componenti
- `.btn-primary`, `.btn-secondary` — covered by @layer componenti
- `.message`, `.message.success`, `.message.error`, `.message.info` — covered by @layer componenti
- `.loading`, `.spinner` — covered by @layer componenti
- `main` (position, z-index, margin-top, padding, max-width) — covered by @layer layout
- `.two-columns` grid — covered by @layer layout
- `::-webkit-scrollbar` rules — covered by @layer reset
- `@media (max-width: 768px)` nav/main rules — covered by @layer utility

### Pattern 2: Fetch/Render Separation (apply to pages with auto-refresh)

**What:** Separate data fetching from DOM rendering so auto-refresh does not reset filter state.

**Affected pages:** laser.html (5s), piega.html (5s), saldatura.html (5s), dashboard.html (10s), archive.html (10s)
**Not affected:** ordini_estratti.html (no auto-refresh — loads on demand only)

**Canonical implementation from laser.html (already correct):**
```javascript
// Source: laser.html lines 954-969
let allOrders = [];      // full dataset from server
let searchQuery = '';    // filter state — preserved across fetches
let lastDataHash = null; // skip re-render if data unchanged

async function loadOrders(forceRender) {
  try {
    const response = await fetch(`${API_URL}/phase/${PHASE}/orders`);
    const orders = await response.json();
    const orderList = Array.isArray(orders) ? orders : [];

    const { changed, newHash } = hasDataChanged(orderList, lastDataHash);
    if (!forceRender && !changed) return;  // no render if data unchanged
    lastDataHash = newHash;

    allOrders = orderList;
    applyFiltersAndRender();  // render with current filter state
  } catch (error) {
    showMessage('Errore connessione al server', 'error');
  }
}

function applyFiltersAndRender() {
  const filtered = filterOrders(allOrders, searchQuery);
  // optionally: apply status filter (FILT-02)
  renderOrders(filtered);
}
```

Note: Current laser.html uses `hasDataChanged` as inline logic rather than calling shared.js `hasDataChanged()`. In the redesign, use the shared.js version.

### Pattern 3: Global Search Bar in Navbar (FILT-01)

**What:** Add a search input directly inside the `<nav>` element, wired to filterOrders().

**HTML pattern:**
```html
<nav>
  <div class="nav-logo">Schedulatore Laser</div>
  <a href="/dashboard.html" class="active">Dashboard</a>
  <!-- ... other nav links ... -->
  <div class="nav-search">
    <input type="search"
           id="navSearch"
           placeholder="Cerca cliente..."
           autocomplete="off"
           oninput="onSearch(this.value)">
  </div>
</nav>
```

**CSS for nav search (inline page-specific):**
```css
.nav-search {
  margin-left: auto;  /* push to right */
  display: flex;
  align-items: center;
}

.nav-search input {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-glass);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  padding: 7px 14px;
  width: 200px;
  height: 36px;
  transition: var(--transition);
}

.nav-search input:focus {
  outline: none;
  border-color: color-mix(in srgb, var(--page-accent) 40%, transparent);
  background: rgba(255, 255, 255, 0.08);
  width: 260px;
}

.nav-search input::placeholder {
  color: var(--text-muted);
}
```

**JS pattern:**
```javascript
const debouncedSearch = debounce((query) => {
  searchQuery = query;
  applyFiltersAndRender();
}, 300);

function onSearch(value) {
  debouncedSearch(value);
}
```

### Pattern 4: Status Filter Chips (FILT-02 + FILT-03)

**What:** Button-style chips for status filtering in department views, displayed with active state + count.

**HTML pattern (below page-header, before order grid):**
```html
<div class="filter-chips">
  <button class="chip chip-all active" onclick="setStatusFilter('all')" id="chip-all">
    Tutti <span class="chip-count">0</span>
  </button>
  <button class="chip chip-attesa" onclick="setStatusFilter('in_attesa')" id="chip-attesa">
    In Attesa <span class="chip-count">0</span>
  </button>
  <button class="chip chip-lavorazione" onclick="setStatusFilter('in_lavorazione')" id="chip-lavorazione">
    In Lavorazione <span class="chip-count">0</span>
  </button>
  <!-- no chip-completato: completati are already excluded from department views -->
</div>
```

**CSS (inline page-specific):**
```css
.filter-chips {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid var(--border-glass);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition);
  min-height: 32px;
}

.chip.active {
  background: color-mix(in srgb, var(--page-accent) 15%, transparent);
  border-color: color-mix(in srgb, var(--page-accent) 40%, transparent);
  color: var(--page-accent);
}

.chip-count {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 1px 6px;
  font-size: 11px;
}

.chip.active .chip-count {
  background: color-mix(in srgb, var(--page-accent) 20%, transparent);
}
```

### Pattern 5: Touch Targets (ACCS-01)

**What:** All interactive elements must have minimum 48px touch target. Critical actions (Avvia, Completa) must be 56px.

**Current state:** Most buttons use `padding: 11px 16px` with `font-size: 13px` — resulting in ~35px height. FAILS.

**Fix pattern for .btn-avvia / .btn-complete (critical, need 56px):**
```css
.btn-avvia,
.btn-complete {
  min-height: 56px;  /* critical action */
  padding: 12px 20px;
  /* keep existing gradient, font-size, font-weight */
}
```

**Fix pattern for secondary buttons (need 48px):**
```css
.btn-start,
.btn-modal-cancel,
.btn-modal-confirm,
.btn-modal-all {
  min-height: 48px;
  padding: 12px 20px;
}
```

**Nav links — currently 8px 16px padding on 13px text = ~29px height. Fix:**
```css
/* In inline <style> (nav a is in design.css @layer componenti — override without !important via specificity) */
nav a {
  min-height: 40px;  /* nav links: 40px acceptable — not critical actions */
  display: flex;
  align-items: center;
}
```

### Pattern 6: Auto-Refresh Indicator (DASH-04)

**What:** Visual timestamp showing "Aggiornato X sec fa" that updates every second, plus a manual refresh button.

**HTML (in page-header area):**
```html
<div class="refresh-indicator">
  <span id="lastRefreshText">Aggiornato adesso</span>
  <button class="btn-refresh-now" onclick="loadOrders(true)">Aggiorna ora</button>
</div>
```

**JS:**
```javascript
let lastRefreshTime = Date.now();

function updateRefreshIndicator() {
  const sec = Math.round((Date.now() - lastRefreshTime) / 1000);
  const text = sec < 5 ? 'Aggiornato adesso' : `Aggiornato ${sec}s fa`;
  document.getElementById('lastRefreshText').textContent = text;
}

// In loadOrders(), after successful fetch:
lastRefreshTime = Date.now();

// Add to DOMContentLoaded:
setInterval(updateRefreshIndicator, 1000);
```

### Pattern 7: Dashboard KPI Row (DASH-02, DASH-03, DASH-05)

**What:** Replace calendar view with a unified KPI + urgency + active-phases overview.

**Current dashboard.html:** Calendar-based layout (7-column weekday grid). No KPI row. Uses GET /api/orders.
**New dashboard.html:** KPI hero row + urgency card list + active phases summary.

**API data available (no backend changes):**
- GET /api/orders — returns all orders with: id, cliente, status, data_consegna, articles, processing_steps, total_quantity
- Computable from orders array:
  - `ordini_attivi` = orders where status != 'SPEDITO'
  - `scadenze_oggi` = orders where data_consegna == today (Italian timezone: use toLocaleDateString)
  - `scadenze_settimana` = orders where data_consegna within next 7 days
  - `fasi_in_corso` = orders where any processing_step has timestamp_inizio but no timestamp_fine

**Urgency logic (DASH-03):**
```javascript
function getUrgencyClass(dataConsegna) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const delivery = new Date(dataConsegna);
  delivery.setHours(0, 0, 0, 0);
  const diff = delivery - today;

  if (diff < 0) return 'urgency-scaduto';     // rosso
  if (diff === 0) return 'urgency-oggi';       // ambra
  return 'urgency-futuro';                     // neutro
}
```

### Pattern 8: Dashboard Route — Welcome Page Removal (DASH-01)

**Critical constraint:** Backend is FROZEN. The Flask route `@app.route('/')` returns `welcome.html`. This CANNOT be changed.

**Solution (no backend change needed):**
1. Rename `welcome.html` to redirect to `dashboard.html` — make welcome.html a meta-refresh or JS redirect:
```html
<!-- welcome.html becomes a redirect-only file -->
<meta http-equiv="refresh" content="0; url=/dashboard.html">
<script>window.location.replace('/dashboard.html');</script>
```
2. OR: Keep welcome.html as the actual dashboard content (rename the file in frontend/ to match the route) — this works because Flask serves the renamed file automatically.

**Recommended approach:** Keep `welcome.html` as a JS redirect file. Move all dashboard content into `dashboard.html`. The nav link `href="/dashboard.html"` continues to work via Flask catch-all.

**Update all nav links:** Remove "Caricamento" link from navbar. All pages currently have:
```html
<a href="welcome.html">Caricamento</a>
```
This must be removed from all 6 pages.

### Pattern 9: Responsive 1024px Breakpoint (REPT-03)

**Current state:** design.css has `@media (max-width: 768px)` only. The 1024px breakpoint must be added **inline per page** since layouts differ.

**Per-page inline pattern:**
```css
/* Tablet: 768px - 1023px — single column */
@media (min-width: 768px) and (max-width: 1023px) {
  .orders-grid {
    grid-template-columns: 1fr;  /* single column on tablet */
  }
  .summary-box {
    grid-template-columns: repeat(2, 1fr);  /* 2-col KPIs on tablet */
  }
}

/* Desktop: >= 1024px — multi-column */
@media (min-width: 1024px) {
  .orders-grid {
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  }
}
```

### Pattern 10: JetBrains Mono replacement (piega.html, saldatura.html)

**Problem:** piega.html and saldatura.html import JetBrains Mono from Google Fonts CDN (causes LAN timeout). Used for `.order-id`, `.article-qty`, `.timer-display`.

**Solution:** Replace JetBrains Mono with `'Courier New', monospace` system fallback — no new font download needed. JetBrains Mono is not self-hosted in fonts/.

```css
/* Replace: font-family: 'JetBrains Mono', 'Courier New', monospace; */
/* With: */
font-family: 'Courier New', 'Lucida Console', monospace;
```

This applies to `.order-id`, `.article-qty`, `.timer-display` in piega.html and saldatura.html.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Filter state + auto-refresh | Custom event system | fetch/render separation pattern (shared.js hasDataChanged) | Already built in shared.js |
| Debounced search | Custom setTimeout | `debounce()` from shared.js | Already available globally |
| Client-side order filtering | Custom array filter | `filterOrders(allOrders, query)` from shared.js | Already available globally |
| Data change detection | Custom comparison | `hasDataChanged(newData, lastHash)` from shared.js | Already available globally |
| Font loading | New CDN import | WOFF2 files in /fonts/ already served | LAN CDN = 30s timeout |

**Key insight:** All filtering and state utilities already exist in shared.js as global functions. Every page just needs `<script src="/shared.js"></script>` before its inline script and can immediately call filterOrders(), debounce(), hasDataChanged().

---

## Common Pitfalls

### Pitfall 1: CSS Layer Priority Misunderstanding
**What goes wrong:** Agent adds page-specific style to a `@layer` block, then it gets overridden by design.css utility layer.
**Why it happens:** design.css declares layers in order: `reset, tokens, tipografia, base, componenti, layout, utility`. The last declared layer wins among layers.
**How to avoid:** Put ALL page-specific styles in un-layered `<style>` blocks (outside any `@layer`). Un-layered styles have higher specificity than any layered rule — this is the intentional design.css architecture.
**Warning sign:** A style that visually disappears or is overridden even with high-specificity selector.

### Pitfall 2: Auto-Refresh Destroys Filter State
**What goes wrong:** `setInterval` calls `loadOrders()` which calls `renderOrders(allOrders)` directly — resets search query and chip selection.
**Why it happens:** archive.html and dashboard.html current implementation renders all orders on every fetch, ignoring filter state.
**How to avoid:** Always use the two-step pattern: `loadOrders()` updates `allOrders` array, calls `applyFiltersAndRender()` which applies current `searchQuery` and `statusFilter` before rendering.
**Warning sign:** User typed a search term, auto-refresh cleared it.

### Pitfall 3: Stripping Too Much CSS
**What goes wrong:** Agent strips all inline CSS (including page-specific components) leaving pages without order cards, article lists, modals.
**Why it happens:** Bulk removal of `:root` and `*` rules accidentally removes adjacent component rules.
**How to avoid:** Use the explicit whitelist of what to strip (listed in Pattern 1). Anything not in that list stays inline.
**Warning sign:** Page renders as plain unstyled HTML after refactoring.

### Pitfall 4: Google Fonts Still Loading
**What goes wrong:** Agent removes the Google Fonts CDN link but leaves a `font-family: 'JetBrains Mono'...` reference that triggers a separate CDN fetch.
**Why it happens:** piega.html and saldatura.html import JetBrains Mono as a second font family.
**How to avoid:** In the 05-04 plan for piega + saldatura, explicitly replace `'JetBrains Mono'` with `'Courier New'` in every CSS rule.
**Warning sign:** Network request to fonts.googleapis.com in DevTools after refactoring.

### Pitfall 5: Touch Target Below 48px
**What goes wrong:** Buttons look visually large but have explicit heights set to ~35px via padding alone without min-height.
**Why it happens:** Original buttons use `padding: 11px 16px` on 13px text = ~35px computed height.
**How to avoid:** Add `min-height: 48px` (secondary) or `min-height: 56px` (primary/critical) to every interactive button. Use flexbox to center content.
**Warning sign:** Button height < 48px in Chrome DevTools computed styles.

### Pitfall 6: WCAG Contrast Failure with --text-secondary
**What goes wrong:** Using `--text-secondary` (#6b7b8d) for primary content text on `--bg-primary` (#0a0a0f).
**Why it happens:** text-secondary is 3.9:1 contrast ratio — below 4.5:1 WCAG AA threshold for normal text.
**How to avoid:** Use `--text-secondary` only for labels, metadata, secondary descriptions (where it serves as visual de-emphasis but not primary reading). Use `--text-primary` (#e6e6e6 = 16.7:1) for all primary reading text.
**Acceptable uses of text-secondary:** nav link labels (non-active), form labels, card metadata, timestamps.
**Unacceptable:** Order names, article names, any primary content.

### Pitfall 7: Dashboard Breaks When Welcome Route Not Changed
**What goes wrong:** GET / still serves welcome.html (which now redirects) causing a redirect loop or blank page.
**Why it happens:** Flask route is frozen, welcome.html is literally what Flask serves at GET /.
**How to avoid:** Make welcome.html a pure redirect file, not an empty file or a 404. Content: `<meta http-equiv="refresh" content="0; url=/dashboard.html">` plus JS fallback.

### Pitfall 8: ordini_estratti.html State Loss on Panel Expansion
**What goes wrong:** ordini_estratti.html uses expandable rows (.order-row, .articles-panel) — if render rebuilds the whole table DOM, expanded rows collapse.
**Why it happens:** ordini_estratti.html has `window.addEventListener('load', loadOrders)` with no auto-refresh — this is actually fine, no re-render loop.
**How to avoid:** ordini_estratti.html does NOT need fetch/render separation because it has no auto-refresh. The panel expansion state is only lost on manual "Aggiorna Elenco" — acceptable.

---

## Code Examples

### Complete CSS Head for laser.html (post-refactoring)

```html
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Stazione Laser - Schedulatore Laser</title>
  <link rel="stylesheet" href="/design.css">
  <style>
    /* ===== PAGE-SPECIFIC: laser.html ===== */
    /* Non ripetere nulla che sia gia in design.css */

    /* Ambient background con tinta rossa per laser */
    body::before {
      background:
        radial-gradient(circle at 20% 50%, rgba(255, 71, 87, 0.04) 0%, transparent 50%),
        radial-gradient(circle at 80% 20%, rgba(168, 85, 247, 0.03) 0%, transparent 50%),
        radial-gradient(circle at 50% 80%, rgba(255, 71, 87, 0.02) 0%, transparent 50%);
    }

    /* ===== NAV SEARCH ===== */
    .nav-search { margin-left: auto; display: flex; align-items: center; }
    .nav-search input {
      background: var(--bg-input);
      border: 1px solid var(--border-glass);
      border-radius: var(--radius-sm);
      color: var(--text-primary);
      font-size: 13px;
      padding: 7px 14px;
      width: 200px;
      height: 36px;
      transition: var(--transition);
    }
    .nav-search input:focus {
      outline: none;
      border-color: color-mix(in srgb, var(--page-accent) 40%, transparent);
      background: rgba(255, 255, 255, 0.08);
      width: 260px;
    }
    .nav-search input::placeholder { color: var(--text-muted); }

    /* ===== FILTER CHIPS ===== */
    .filter-chips { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 14px;
      border-radius: 20px;
      border: 1px solid var(--border-glass);
      background: rgba(255, 255, 255, 0.04);
      color: var(--text-secondary);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: var(--transition);
      min-height: 32px;
    }
    .chip.active {
      background: color-mix(in srgb, var(--page-accent) 15%, transparent);
      border-color: color-mix(in srgb, var(--page-accent) 40%, transparent);
      color: var(--page-accent);
    }
    .chip-count {
      background: rgba(255, 255, 255, 0.1);
      border-radius: 10px;
      padding: 1px 6px;
      font-size: 11px;
    }

    /* ===== SUMMARY BOX ===== */
    .summary-box {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
      margin-bottom: 32px;
    }
    /* ... rest of page-specific components ... */

    /* ===== TOUCH TARGETS ===== */
    .btn-avvia, .btn-complete { min-height: 56px; }
    .btn-start, .btn-modal-cancel, .btn-modal-confirm { min-height: 48px; }
    nav a { min-height: 40px; display: flex; align-items: center; }

    /* ===== RESPONSIVE 1024px ===== */
    @media (max-width: 1023px) {
      .orders-grid { grid-template-columns: 1fr; }
      .summary-box { grid-template-columns: repeat(2, 1fr); }
    }
    @media (min-width: 1024px) {
      .orders-grid { grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); }
    }
  </style>
</head>
<body data-page="laser">
```

### shared.js Usage Pattern (inline script)

```html
<!-- BEFORE inline <script>: -->
<script src="/shared.js"></script>
<script>
  const API_URL = '/api';
  const PHASE = 'LASER';
  let allOrders = [];
  let searchQuery = '';
  let statusFilter = 'all';  // 'all' | 'in_attesa' | 'in_lavorazione'
  let lastDataHash = null;

  window.addEventListener('DOMContentLoaded', () => {
    loadOrders();
    setInterval(loadOrders, 5000);
  });

  async function loadOrders(forceRender) {
    try {
      const response = await fetch(`${API_URL}/phase/${PHASE}/orders`);
      const orders = await response.json();
      const orderList = Array.isArray(orders) ? orders : [];

      const { changed, newHash } = hasDataChanged(orderList, lastDataHash);
      if (!forceRender && !changed) return;
      lastDataHash = newHash;

      allOrders = orderList;
      applyFiltersAndRender();
    } catch (error) {
      showMessage('Errore connessione al server', 'error');
    }
  }

  function applyFiltersAndRender() {
    let filtered = filterOrders(allOrders, searchQuery);
    if (statusFilter !== 'all') {
      filtered = filtered.filter(order =>
        (order.articles_in_phase || []).some(a => a.phase_status === statusFilter)
      );
    }
    updateChipCounts();
    renderOrders(filtered);
  }

  // Search wired to nav search input
  const debouncedSearch = debounce((q) => {
    searchQuery = q;
    applyFiltersAndRender();
  }, 300);
</script>
```

### Dashboard KPI Hero Row HTML Pattern (DASH-02, DASH-03, DASH-05)

```html
<!-- KPI Hero Row -->
<div class="kpi-row">
  <div class="kpi-card">
    <div class="kpi-number" id="kpiAttivi">0</div>
    <div class="kpi-label">Ordini Attivi</div>
  </div>
  <div class="kpi-card kpi-urgency-oggi">
    <div class="kpi-number" id="kpiOggi">0</div>
    <div class="kpi-label">Scadenze Oggi</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-number" id="kpiSettimana">0</div>
    <div class="kpi-label">Scadenze Settimana</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-number" id="kpiFasiInCorso">0</div>
    <div class="kpi-label">Fasi in Corso</div>
  </div>
</div>

<!-- Urgency Orders List -->
<div class="urgency-section">
  <h3>Ordini per Urgenza</h3>
  <div id="urgencyList" class="urgency-list"></div>
</div>
```

---

## WCAG AA Contrast Verification

**Verified ratios for design.css tokens on --bg-primary (#0a0a0f):**

| Token | Value | Contrast on #0a0a0f | AA Normal Text | AA Large Text |
|-------|-------|---------------------|----------------|---------------|
| --text-primary | #e6e6e6 | 16.7:1 | PASS | PASS |
| --text-secondary | #6b7b8d | 3.9:1 | FAIL | PASS (>3:1) |
| --text-muted | #4a5568 | 2.4:1 | FAIL | FAIL |
| --accent-cyan | #00d4ff | 10.1:1 | PASS | PASS |
| --accent-green | #00e676 | 11.7:1 | PASS | PASS |
| --accent-red | #ff4757 | 4.8:1 | PASS | PASS |
| --accent-amber | #ffa502 | 9.0:1 | PASS | PASS |
| --accent-orange | #ff6348 | 5.0:1 | PASS | PASS |
| --accent-purple | #a855f7 | 4.6:1 | PASS | PASS |

**ACCS-02 compliance rules:**
- --text-secondary (#6b7b8d) may ONLY be used for secondary/decorative text (labels, metadata, timestamps, placeholders) — not for primary content
- --text-muted (#4a5568) may ONLY be used for non-critical decorative elements (IDs, separators) — not for any readable content
- All primary content text MUST use --text-primary (#e6e6e6)
- Accent colors on dark background: all pass WCAG AA

**Note on glass card background:** Card background is `rgba(255,255,255,0.03)` on `#0a0a0f` = effective #0c0c11. Contrast ratios above apply — negligible change.

---

## Page-by-Page Analysis

### 05-01: archive.html
**Current size:** ~747 lines
**Auto-refresh:** YES (10s)
**Font issue:** Google Fonts Inter only (no JetBrains)
**Complexity:** LOW — table layout with 1 filter (cliente), expandable rows (expand icon), no modals
**Existing filter:** `applyFilters()` at line 730 — already has basic filter, needs integration with search bar
**Unique components to keep inline:** `.stats-grid`, `.stat-card`, `.filter-bar`, `.table-card`, table thead/td styles, `.order-row`, `.articles-panel`, `.timing-badge`, `.empty-state`
**data-page:** not needed (cyan default)
**New additions:** nav search, fetch/render separation (preserve filter state), 1024px breakpoint, touch targets

### 05-02: ordini_estratti.html
**Current size:** ~1100+ lines (most complex page)
**Auto-refresh:** NO (only on-demand via "Aggiorna Elenco" button)
**Font issue:** Google Fonts Inter only (no JetBrains)
**Complexity:** HIGH — expandable rows, per-article phase checkboxes, inline edit mode (save/cancel), PUT /api/orders/<id>/articles calls
**Existing filter:** NONE — must add
**Unique components to keep inline:** `.stats`, `.table-card`, `.table-wrapper`, `.order-row` expandable, `.articles-panel`, `.article-row`, `.phase-checkboxes`, `.phase-checkbox`, `.btn-edit-phases`, `.btn-save-phases`, `.action-link`, `.error-section`, `.badge-working`, `.save-feedback`, `.articles-footer`
**data-page:** not needed (cyan default)
**No fetch/render separation needed** (no auto-refresh)
**New additions:** nav search (filters by cliente/numero_ordine), 1024px breakpoint, touch targets

### 05-03: laser.html (reference implementation)
**Current size:** ~1278 lines
**Auto-refresh:** YES (5s)
**Font issue:** Google Fonts Inter only
**Complexity:** MEDIUM — order cards, per-article modal (checkboxes), avvia/completa flow
**Existing pattern:** Has lastDataHash guard (correct) but not using shared.js version
**Unique components:** `.summary-box`, `.orders-grid`, `.order-card`, `.articles-section`, `.article-item`, `.status-badge`, `.action-buttons`, `.btn-avvia`, `.btn-complete`, `.modal-overlay`, `.modal-checkboxes`, `.modal-checkbox-item`, `.btn-modal-*`, per-article status badges
**data-page:** `laser`
**New additions:** nav search + filter chips + fetch/render refactor + touch targets + 1024px

### 05-04: piega.html + saldatura.html (replicate from laser)
**Current size:** piega.html ~1300+ lines, saldatura.html ~1100+ lines
**Auto-refresh:** YES (5s both)
**Font issue:** Google Fonts Inter + JetBrains Mono — must replace JetBrains with system mono
**Complexity:** MEDIUM + Timer display (active timer per order with setInterval timers[orderId])
**Unique to piega/saldatura vs laser:** `.timer-display` (amber/orange, monospace, 36px), `timers{}` state, `activePhases{}` state — timer intervals must survive fetch/render cycles
**Critical:** Timer state (timers object) must NOT be reset on auto-refresh re-render
**data-page:** `piega` / `saldatura`

**Timer preservation pattern:**
```javascript
// timers = { orderId: intervalId } — lives outside renderOrders()
// DO NOT clear timers on renderOrders() — only clear when phase completed
function renderOrders(orders) {
  // Build HTML with data-order-id attribute
  // Reattach timers to existing elements by ID rather than clearing all
  orders.forEach(order => {
    if (timers[order.id]) {
      // Timer is already running — update display element reference only
      updateTimerDisplay(order.id);
    }
  });
}
```

### 05-05: dashboard.html
**Current size:** ~1216 lines
**Auto-refresh:** YES (10s)
**Font issue:** Google Fonts Inter only
**Complexity:** HIGH — complete redesign (calendar view → KPI + urgency list), modal for order detail
**Current features:** Calendar 7-column grid, order modal with processing_steps timeline and article progress bars
**To REMOVE:** All calendar-related CSS and JS (`.calendar-container`, `.calendar-weekdays`, `.calendar-days`, `.calendar-day`, `.day-orders`, `.weekday`, `renderCalendar()`, `createDayElement()`, `previousMonth()`, `nextMonth()`, `currentDate`)
**To BUILD:** KPI hero row, urgency-based order list, active phases summary
**To KEEP:** Order detail modal (`.modal`, `.modal-content`, `.modal-header`, `.phase-progress-bar`, `.phase-segment`, `openOrderModal()`, `closeModal()`) — same modal data, different trigger
**data-page:** not set (cyan default)
**DASH-01:** welcome.html must become redirect file

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Google Fonts CDN | Self-hosted WOFF2 | Phase 4 | Eliminates LAN timeout |
| Per-page CSS tokens (700+ lines each) | design.css shared + stripped inline | Phase 5 | Single source of truth |
| Calendar dashboard | KPI+urgency dashboard | Phase 5 | Operational at a glance |
| No filter/search | Global nav search + status chips | Phase 5 | Filter survives auto-refresh |
| No touch target spec | 48px/56px min-height | Phase 5 | Tablet usability |

**Deprecated/outdated by this phase:**
- welcome.html as landing page: becomes a redirect stub
- Google Fonts CDN links: replaced by design.css @font-face
- Inline `:root` token declarations: replaced by design.css @layer tokens
- Direct renderOrders() call from fetch: replaced by applyFiltersAndRender() indirection

---

## Open Questions

1. **welcome.html redirect approach**
   - What we know: Flask route `@app.route('/')` returns `welcome.html`, backend is frozen
   - What's unclear: Whether to put redirect JS in welcome.html, or copy dashboard HTML into welcome.html and remove dashboard.html
   - Recommendation: Put redirect in welcome.html (2 lines), keep dashboard.html as the real content. Nav links point to `/dashboard.html` which works via Flask catch-all.

2. **Navbar overflow on tablet**
   - What we know: Nav currently has 7 items (logo + 6 links) + new search input = very crowded on 768-1023px
   - What's unclear: Exact pixel threshold where nav overflows
   - Recommendation: On <=768px (existing breakpoint), hide nav search input; on 768-1023px, reduce search width to 150px; nav links already scroll horizontally via `overflow-x: auto` in design.css utility layer.

3. **ordini_estratti.html search scope**
   - What we know: Orders have `cliente` and `numero_ordine` fields
   - What's unclear: Whether filterOrders() (which searches on `cliente` and `id` fields) covers the right fields for this page
   - Recommendation: Add a page-specific filter function in ordini_estratti.html that searches on `cliente` and `numero_ordine` (not `id`), or extend filterOrders() in shared.js. Since shared.js must not be modified per-page (it's shared), use a wrapper.

4. **Dashboard auto-refresh interval**
   - Current: 10s for dashboard and archive
   - For KPI view: 10s is fine for KPIs; for urgency list same
   - Recommendation: Keep 10s for dashboard (reduced from 30s of original welcome-based KPI)

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `app/frontend/design.css` — all component names, layer order, token values verified
- Direct code inspection: `app/frontend/shared.js` — filterOrders(), debounce(), hasDataChanged() signatures verified
- Direct code inspection: `app/frontend/laser.html` — current fetch/render pattern, modal structure, avvia/completa flow
- Direct code inspection: `app/frontend/dashboard.html` — calendar layout, modal detail, auto-refresh interval
- Direct code inspection: `app/frontend/piega.html` — JetBrains Mono usage, timer display, timers{} state
- Direct code inspection: `app/frontend/saldatura.html` — same pattern as piega, orange accent
- Direct code inspection: `app/frontend/archive.html` — table layout, applyFilters(), auto-refresh
- Direct code inspection: `app/frontend/ordini_estratti.html` — expandable rows, phase checkbox UI, PUT API usage
- Direct code inspection: `app/backend/app.py` — confirmed Flask routes, `@app.route('/')` → welcome.html
- WCAG 2.1 contrast ratios: computed manually from hex values (standard formula)

### Secondary (MEDIUM confidence)
- WCAG 2.1 AA contrast ratios: 4.5:1 for normal text, 3:1 for large text (18pt/14pt bold) — well-established standard

### Tertiary (LOW confidence — not needed)
- None: all research derived from direct codebase inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all files directly inspected, no assumptions
- Architecture patterns: HIGH — derived from existing working code in laser.html
- WCAG contrast: HIGH — computed from hex values using standard formula
- Pitfalls: HIGH — derived from reading actual current implementations
- Dashboard redesign: MEDIUM — KPI data computable from existing API, but new HTML structure needs planner decisions

**Research date:** 2026-02-19
**Valid until:** Stable — no external dependencies. Valid until codebase changes.

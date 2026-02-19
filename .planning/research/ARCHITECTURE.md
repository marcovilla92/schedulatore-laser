# Architecture Research

**Domain:** Shared CSS design system + search/filter + responsive layout — vanilla HTML/CSS/JS, no build tools
**Researched:** 2026-02-19
**Confidence:** HIGH

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FLASK SERVER (port 5000)                      │
│  static_folder=None — serves everything via /<path:filename>         │
│  frontend/ directory is the document root for all static assets      │
├─────────────────────────────────────────────────────────────────────┤
│                        frontend/  (document root)                    │
│                                                                      │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  design.css   │  │  shared.js   │  │     Page HTML files      │  │
│  │  (design      │  │  (filter,    │  │                          │  │
│  │   tokens +    │  │   refresh,   │  │  dashboard.html          │  │
│  │   base UI)    │  │   utils)     │  │  laser.html              │  │
│  └───────┬───────┘  └──────┬───────┘  │  piega.html             │  │
│          │                 │          │  saldatura.html          │  │
│          └────────┬────────┘          │  ordini_estratti.html    │  │
│                   │ linked via        │  archive.html            │  │
│                   │ <link>/<script>   │                          │  │
│                   ↓                   └──────────────────────────┘  │
│          ┌────────────────────────────────────────────────────────┐  │
│          │            Page <style> blocks (page-local CSS)        │  │
│          │  Overrides and extends design.css with page-specific   │  │
│          │  rules only. Design tokens from :root stay shared.     │  │
│          └────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                        Flask REST API (/api/*)                       │
│  JSON responses — unchanged, no migration needed for backend        │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| `frontend/design.css` | Design tokens (:root vars), CSS reset, base layout, nav, cards, buttons, modals, badges, utilities, animations, responsive breakpoints | Single external CSS file linked by all pages |
| `frontend/shared.js` | Client-side search/filter, debounce utility, auto-refresh with hash-diff, toast notifications | Single external JS file loaded by pages that need it |
| `<style>` block (per page) | Page-specific layout rules that do not repeat across pages (e.g., calendar grid, piega checkbox accordion) | Stays inline; shrinks dramatically after shared extraction |
| `<script>` block (per page) | Page-specific business logic: loadOrders, renderOrders, phase-start/complete calls | Stays inline; uses functions from shared.js if applicable |
| Flask `/<path:filename>` route | Serves all files from `frontend/` as-is, including CSS and JS | Already in place — zero backend change needed |

---

## Recommended Project Structure

```
app/frontend/
├── design.css              # NEW: shared design system (tokens + base UI)
├── shared.js               # NEW: shared JS utilities (search, debounce, refresh)
│
├── dashboard.html          # Redesigned: links design.css + shared.js
├── laser.html              # Redesigned: links design.css + shared.js
├── piega.html              # Redesigned: links design.css + shared.js
├── saldatura.html          # Redesigned: links design.css + shared.js
├── ordini_estratti.html    # Redesigned: links design.css + shared.js
├── archive.html            # Redesigned: links design.css + shared.js
│
└── welcome.html            # Being removed (per milestone scope)
```

### Structure Rationale

- **Single flat directory:** Flask's `send_from_directory(FRONTEND_FOLDER, filename)` catch-all serves any file in `frontend/`. Adding `design.css` here means it is immediately available at `/design.css` with zero backend changes.
- **No subdirectories needed:** The file count (2 new files) does not justify a `css/` or `js/` subfolder. Flat is simpler with this Flask pattern.
- **No Jinja2 templates, no `url_for()`:** Because pages are raw HTML served by `send_from_directory`, links use root-relative paths (`/design.css`, `/shared.js`), not Flask's `url_for()`.

---

## Architectural Patterns

### Pattern 1: Externalize Shared CSS, Keep Page-Local Overrides

**What:** Extract the `:root` block, CSS reset, nav, card, button, modal, badge, animation, and utility rules into `design.css`. Each page `<style>` block keeps only rules that are unique to that page.

**When to use:** Always — this is the core migration act. Every page has ~200 lines of duplicated code that is byte-for-byte identical across all 7 files.

**Trade-offs:** External CSS adds one HTTP request per page load. On a LAN app served by Flask dev server / gunicorn on localhost, this is negligible (sub-millisecond). HTTP/2 is not in play here but irrelevant at this scale.

**Link pattern (root-relative, no Jinja2):**
```html
<head>
  <!-- Before page-specific <style> so tokens are available -->
  <link rel="stylesheet" href="/design.css">
  <style>
    /* Only rules that are unique to THIS page */
    .calendar-days { display: grid; grid-template-columns: repeat(7, 1fr); }
  </style>
</head>
```

**Approximate size breakdown after migration:**
- `design.css` target: ~350-450 lines (all shared rules extracted once)
- Per-page `<style>` block: ~50-150 lines (page-specific layout only)
- Current per-page `<style>` block: ~600-900 lines (mostly duplicated)

---

### Pattern 2: CSS Custom Properties as the Single Source of Truth

**What:** All design values — colors, spacing, radius, transition, typography — live exclusively in `:root` inside `design.css`. Pages never redefine custom property values.

**When to use:** From day one of migration. Any page that redefines `--accent-cyan` or any token breaks the design system.

**Trade-offs:** Per-page accent color overrides (laser uses red ambient, piega uses amber) must be done via a `data-page` attribute on `<body>` or page-specific class, not by redefining the token.

**Implementation for per-page accent:**
```css
/* design.css */
:root {
  --page-accent: var(--accent-cyan); /* default */
}

/* Page overrides body accent without touching global tokens */
body[data-page="laser"]  { --page-accent: var(--accent-red); }
body[data-page="piega"]  { --page-accent: var(--accent-amber); }
body[data-page="saldatura"] { --page-accent: var(--accent-orange); }
```

```html
<!-- laser.html -->
<body data-page="laser">
```

---

### Pattern 3: Client-Side Search/Filter via In-Memory Data Array

**What:** All pages that have lists (archive, ordini_estratti, and potentially laser/piega/saldatura for searching by cliente) load data into a module-level `allOrders` array. A filter function re-renders from this array on input events, without a new API call.

**When to use:** On any page with a search/filter bar. The existing `archive.html` already follows this pattern with `applyFilters()`.

**Trade-offs:** Entire dataset lives in memory. At the scale of a carpenteria (likely 10-200 concurrent orders), this is completely acceptable. No pagination or virtual scrolling needed.

**Shared.js filter utility:**
```javascript
// shared.js
function filterOrders(allOrders, searchTerm, statusFilter) {
  const term = searchTerm.trim().toLowerCase();
  return allOrders.filter(order => {
    const matchesSearch = !term ||
      order.cliente.toLowerCase().includes(term) ||
      order.id.toLowerCase().includes(term) ||
      (order.numero_ordine || '').toLowerCase().includes(term);
    const matchesStatus = !statusFilter || order.status === statusFilter;
    return matchesSearch && matchesStatus;
  });
}

// Debounce for search input
function debounce(fn, delay = 200) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); };
}
```

**Per-page usage (stays in page `<script>`):**
```javascript
// archive.html <script>
let allOrders = [];

searchInput.addEventListener('input', debounce(() => {
  const filtered = filterOrders(allOrders, searchInput.value, statusSelect.value);
  renderOrders(filtered);
}, 200));
```

---

### Pattern 4: Hash-Diff Auto-Refresh (Already Exists — Formalize)

**What:** Before re-rendering, compare `JSON.stringify(newData)` against the last hash. Skip render if unchanged. This pattern already exists in `piega.html`, `saldatura.html`, and `laser.html`.

**When to use:** All pages with `setInterval` polling. Prevents DOM thrash and visual flicker.

**Formalize in shared.js:**
```javascript
// shared.js
const _lastHashes = {};

function hasDataChanged(pageKey, newData) {
  const hash = JSON.stringify(newData);
  if (_lastHashes[pageKey] === hash) return false;
  _lastHashes[pageKey] = hash;
  return true;
}
```

---

### Pattern 5: Incremental Page-by-Page Migration

**What:** Migrate one page at a time. Each migration is self-contained and does not break other pages. During migration, some pages use `design.css` (new) and some remain fully inline (old) — both work simultaneously.

**When to use:** This is the migration strategy. Do NOT attempt a big-bang rewrite of all 7 pages at once.

**Migration order (see Data Flow section below).**

---

## Data Flow

### Request Flow (unchanged from current)

```
User visits /dashboard.html
       ↓
Flask /<path:filename> → send_from_directory(frontend/, 'dashboard.html')
       ↓
Browser parses HTML → fetches /design.css (NEW), /shared.js (NEW)
       ↓
DOMContentLoaded → loadOrders() called
       ↓
fetch('/api/orders') → Flask route → OrderManager.get_all_orders() → SQLite
       ↓
JSON response → renderOrders(data) → DOM updated
       ↓
setInterval(loadOrders, Xs) → hash-diff check → conditional re-render
```

### Search/Filter Data Flow (new)

```
allOrders = [] (loaded once from API)
       ↓
User types in search input
       ↓
debounce(200ms) → filterOrders(allOrders, term, status)
       ↓
filtered array → renderOrders(filtered)  [NO new API call]
       ↓
DOM updated with matching rows/cards only
```

### Key Data Flows

1. **Design token resolution:** Browser reads `design.css` first (linked before `<style>`), setting all `:root` custom properties. Page `<style>` block may add page-specific rules or override `--page-accent`. No JavaScript involved.
2. **Filter state:** Filter state (current search term, current status filter) lives as local variables in the page `<script>`. Not in `shared.js`. This keeps pages independent.
3. **Auto-refresh with filter:** When `setInterval` fires, `loadOrders()` updates `allOrders`, then calls the filter function with current filter state, then renders. The filter is preserved across refreshes.

---

## Migration Build Order

This is the recommended sequence for migrating 6 pages (welcome.html is being removed).

### Phase A: Create Shared Files (prerequisite, no page changes)

1. Create `design.css` with extracted shared rules from any page (all are identical in shared parts)
2. Create `shared.js` with `filterOrders()`, `debounce()`, `hasDataChanged()`, `formatTime()`, `showToast()`
3. Verify files are accessible at `/design.css` and `/shared.js` via browser — this confirms Flask's catch-all serves them correctly

### Phase B: Pages Without Search (simpler, good for validating approach)

**Order: archive.html → ordini_estratti.html**

Rationale: archive already has a filter bar (lowest risk to validate the CSS extraction works). `ordini_estratti` is a complex page but has no auto-refresh, making JS migration simpler.

### Phase C: Phase Workstation Pages (highest business criticality)

**Order: laser.html → piega.html → saldatura.html**

Rationale: These three are structurally near-identical (same PHASE constant pattern, same partial-complete modal). Migrate laser first as a template, then replicate to piega/saldatura with minimal changes. These are the most used pages in production.

### Phase D: Dashboard

**Order: dashboard.html last**

Rationale: Dashboard has the most unique page-specific CSS (calendar grid). It benefits most from all shared CSS being stable before touching it. It also has the most complex JS (calendar rendering + modal). Saving it for last means the team has migration experience before tackling the hardest page.

### Migration Checklist Per Page

```
For each page:
1. Add <link rel="stylesheet" href="/design.css"> before <style>
2. Add <script src="/shared.js"></script> before page <script>
3. Remove from <style>: :root block, CSS reset, nav rules, .card rules,
   .btn rules, .modal rules, .badge rules, @keyframes ambientFloat,
   @keyframes fadeInUp, @keyframes spin
4. Replace duplicate filter/debounce JS with calls to shared.js functions
5. Add data-page="<pagename>" to <body>
6. Visual smoke test: nav active state, card hover, modal open/close
7. Functional smoke test: filter works, auto-refresh works
```

---

## Scaling Considerations

This is a LAN-only internal tool. Scaling to many users is not a concern. The relevant "scaling" is code maintainability as the UI evolves.

| Concern | Now (6 pages) | Future (8-10 pages) | Notes |
|---------|--------------|---------------------|-------|
| Adding new design token | Edit 6 files | Edit 1 file (`design.css`) | Main reason to centralize |
| Changing nav link | Edit 6 files | Edit 6 files | Nav HTML still duplicated — acceptable tradeoff without a templating engine |
| Adding new page | Copy any page, link shared files | Same | No build step, 2-minute setup |
| Changing filter logic | Edit 6 files | Edit 1 file (`shared.js`) | Extracted to shared.js |

### Scaling Priority

1. **First bottleneck (now):** Design token duplication — 7 `:root` blocks to maintain. Fixed by `design.css`.
2. **Second bottleneck (future):** Nav HTML duplication — still 6 copies. Mitigation without a framework: use `fetch()` to load a `nav.html` fragment at runtime (progressive enhancement, optional).

---

## Anti-Patterns

### Anti-Pattern 1: All-at-Once Migration

**What people do:** Rewrite all 7 pages simultaneously in one big PR.

**Why it's wrong:** Any bug in `design.css` breaks all pages at once. If a production worker opens the app during migration, they may see a broken UI. Rollback is complex.

**Do this instead:** One page per commit. Each commit is independently deployable. If `laser.html` migration breaks something, only that page is affected.

---

### Anti-Pattern 2: Redefining CSS Variables Per-Page

**What people do:** Each page overrides `--accent-cyan` in its own `<style>` block to change accent color.

**Why it's wrong:** Creates an invisible coupling — changing a token in `design.css` does not propagate to pages that override it. Defeats the design system.

**Do this instead:** Use `data-page` attribute on `<body>` and page-scoped selectors in `design.css` that override only the abstract `--page-accent` token, not the base color tokens.

---

### Anti-Pattern 3: Putting Page-Specific CSS in design.css

**What people do:** Add `.calendar-days`, `.accordion-header`, and other page-specific selectors to the shared file because "it's easier."

**Why it's wrong:** `design.css` becomes a dumping ground. Every page loads styles it doesn't use. The shared file grows without bounds and becomes hard to maintain.

**Do this instead:** Keep page-specific layout rules in the page's own `<style>` block. If a component appears on 3+ pages, it graduates to `design.css`.

---

### Anti-Pattern 4: Loading shared.js on Every Page

**What people do:** Add `<script src="/shared.js">` unconditionally to all pages, including ones that don't need search.

**Why it's wrong:** Minor overhead, but also means shared.js cannot use `document.querySelector` at module level without checking for element existence.

**Do this instead:** Load `shared.js` only on pages that use its functions. Dashboard (no search) may not need it initially. Design shared.js to be safe if elements don't exist (null checks on selectors).

---

### Anti-Pattern 5: Using CSS @import Inside design.css

**What people do:** Split `design.css` into `tokens.css`, `base.css`, `components.css` and use `@import` to compose them.

**Why it's wrong:** Each `@import` is a render-blocking request. Three `@import` statements in `design.css` means 3 sequential CSS fetches before the page renders. On a LAN with low latency this is not catastrophic, but it adds visible jank, especially on first load.

**Do this instead:** Keep `design.css` as a single concatenated file. Section it with comment headers (`/* ===== TOKENS ===== */`, `/* ===== BASE ===== */`, etc.) for readability. One file, one request.

---

## Integration Points

### New File to Existing Backend

| Integration | Pattern | Notes |
|-------------|---------|-------|
| `design.css` served by Flask | `/<path:filename>` catch-all already handles it | URL: `/design.css` — no route addition needed |
| `shared.js` served by Flask | Same catch-all | URL: `/shared.js` — no route addition needed |
| Page HTML links to shared files | `<link href="/design.css">` + `<script src="/shared.js">` | Root-relative paths work because Flask serves on port 5000 at `/` |

### Internal Boundaries (New Components)

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `design.css` → page `<style>` | CSS cascade + custom property inheritance | Page styles load after `design.css` so they can override safely |
| `shared.js` → page `<script>` | Global function calls, module-level variables | `filterOrders()`, `debounce()`, `hasDataChanged()` are globals; page script calls them directly |
| Auto-refresh + filter state | Local variables in page `<script>` | `allOrders`, `currentFilterTerm`, `currentStatusFilter` — remain page-local, not in `shared.js` |

### Responsive Breakpoints

For PC + tablet targeting (the stated scope, no mobile requirement):

```css
/* design.css */

/* Base styles: desktop (1280px+) */
.main-content { max-width: 1300px; padding: 0 24px; }
.order-grid { grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); }

/* Tablet (768px - 1024px) */
@media (max-width: 1024px) {
  nav { padding: 0 16px; gap: 4px; }
  nav a { padding: 6px 10px; font-size: 12px; }
  .order-grid { grid-template-columns: 1fr; }
  .main-content { padding: 0 16px; }
}

/* Compact tablet (below 768px) */
@media (max-width: 768px) {
  nav .nav-logo { margin-right: 16px; }
  nav a span { display: none; } /* hide text, keep icon */
}
```

Single breakpoint at 1024px handles the PC-to-tablet transition. A secondary at 768px handles compact tablets. No mobile breakpoints needed per scope.

---

## Sources

- Flask `/<path:filename>` catch-all verified by reading `app/backend/app.py` (line 47-50). `static_folder=None` means `/static/` is not available; all assets must be in `frontend/`. **HIGH confidence.**
- Flask static files documentation: https://flask.palletsprojects.com/en/stable/tutorial/static/
- CSS custom properties for design tokens: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/--*
- Build-free CSS modular approach: https://gomakethings.com/rethinking-modular-css-and-build-free-design-systems/
- Vanilla JS client-side filter pattern: https://css-tricks.com/in-page-filtered-search-with-vanilla-javascript/ and W3Schools how-to-filter-lists
- Responsive breakpoints 2025: https://www.browserstack.com/guide/responsive-design-breakpoints
- Existing page structure verified by reading all 7 HTML files in `app/frontend/` — `:root` blocks are byte-identical across all pages. **HIGH confidence.**
- Penpot design tokens guide: https://penpot.app/blog/the-developers-guide-to-design-tokens-and-css-variables/

---
*Architecture research for: Schedulatore Laser — UI/UX redesign milestone*
*Researched: 2026-02-19*

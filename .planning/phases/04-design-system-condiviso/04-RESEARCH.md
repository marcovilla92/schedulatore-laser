# Phase 4: Design System Condiviso - Research

**Researched:** 2026-02-19
**Domain:** CSS Design System (vanilla CSS @layer, CSS custom properties, self-hosted WOFF2 fonts, vanilla JS globals)
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DSGN-01 | Tutte le pagine caricano un unico file `design.css` con CSS custom properties per colori, spacing, tipografia, radii e transizioni | Flask catch-all `/<path:filename>` already serves any file in `frontend/` including subdirectories — no backend changes needed. CSS custom properties in `:root` cascade to all elements. |
| DSGN-02 | Font Inter self-hosted in WOFF2 (4 pesi: 400/500/600/700), nessun riferimento a Google Fonts CDN | WOFF2 files downloadable from jsDelivr fontsource CDN at build time; `@font-face` in design.css using `font-display: swap`; all 7 pages currently reference `fonts.googleapis.com`. |
| DSGN-03 | CSS @layer organizza il cascade: reset → tokens → tipografia → base → componenti → layout → utility | CSS @layer is baseline-available in all browsers since March 2022. Un-layered inline `<style>` blocks automatically win over any @layer rule — page-specific styles override shared rules without `!important`. |
| DSGN-04 | File `shared.js` fornisce utility `filterOrders()`, `debounce()`, `hasDataChanged()` come globali riutilizzabili | Classic `<script src="/shared.js">` (not type="module") exposes functions on `window` — each page can call them immediately. None of these functions exist yet; patterns identified from existing page code. |
</phase_requirements>

## Summary

Phase 4 creates the shared CSS and JS foundation that all 7 pages will consume in Phase 5. The current state has 8,011 lines across 7 HTML files with identical CSS tokens duplicated in every `:root {}` block (22 lines each, 7 copies = 154 lines of pure duplication), identical navbar CSS (53 lines × 7 = 371 lines), identical reset, base, button, glass-card, and animation CSS — approximately 300-400 lines per page that are identical across all pages. Each page also independently loads Google Fonts CDN which causes 30-second timeouts on the LAN network.

The core work is: (1) download 4 Inter WOFF2 files to `frontend/fonts/`, (2) create `frontend/design.css` with `@layer` cascade containing shared tokens and component styles, (3) create `frontend/shared.js` with 3 utility globals. No backend changes are required — Flask's existing `/<path:filename>` catch-all serves all files in `frontend/` including subdirectories like `frontend/fonts/`.

The key architectural insight for `@layer` is that CSS rules in an `@layer` block have LOWER cascade priority than un-layered rules. This means page-specific inline `<style>` blocks (which are un-layered) will automatically override anything in design.css's layers — without needing `!important`. Per-page accent colors can remain in inline styles with zero conflict.

**Primary recommendation:** Create design.css with 7-layer cascade, download Inter WOFF2 from jsDelivr fontsource, expose 3 globals via classic script tag (not ES module).

## Standard Stack

### Core (no npm, no bundler — vanilla only)

| Technology | Version | Purpose | Why Standard |
|------------|---------|---------|--------------|
| CSS `@layer` | Baseline (Chrome 99+, Firefox 97+, Safari 15.4+) | Explicit cascade control — shared tokens below page-specific styles | All modern browsers, no polyfill needed; March 2022 baseline |
| CSS custom properties | Baseline | Design tokens as `--var: value` in `:root` | Native CSS, zero overhead, inherited by all descendants |
| Inter WOFF2 | v4.x static files | Self-hosted body font | Eliminates Google Fonts CDN timeout on LAN; same visual result |
| `font-display: swap` | Baseline | Font loading strategy | Best for LAN (font always available) — shows fallback then swaps |
| Classic `<script>` tag | Browser native | Load shared.js as global | Simpler than modules for cross-page globals; no CORS issues |

### No Supporting Libraries Needed

This phase is pure CSS + JS standards. No npm packages, no build tools.

### Alternatives Considered

| Instead of | Could Use | Why We Don't |
|------------|-----------|--------------|
| CSS @layer | CSS specificity management (BEM, etc.) | @layer is the modern standard; BEM would require refactoring class names |
| Static WOFF2 files | Variable font (single woff2 supports all weights) | Variable font is ~329kB; 4 static files at ~30-50kB each = less total for 4 specific weights |
| Classic `<script>` | `type="module"` with `globalThis.x = fn` | Modules introduce CORS complexity; classic script is simpler and correct for this use case |
| jsDelivr fontsource CDN at runtime | Download once to frontend/fonts/ | Must be local — LAN has no internet access |

## Architecture Patterns

### Recommended Project Structure

```
app/frontend/
├── design.css          # NEW: shared design system
├── shared.js           # NEW: shared JS utilities
├── fonts/              # NEW: self-hosted Inter WOFF2
│   ├── inter-latin-400-normal.woff2
│   ├── inter-latin-500-normal.woff2
│   ├── inter-latin-600-normal.woff2
│   └── inter-latin-700-normal.woff2
├── welcome.html        # UNCHANGED in Phase 4
├── dashboard.html      # UNCHANGED in Phase 4
├── laser.html          # UNCHANGED in Phase 4
├── piega.html          # UNCHANGED in Phase 4
├── saldatura.html      # UNCHANGED in Phase 4
├── ordini_estratti.html # UNCHANGED in Phase 4
└── archive.html        # UNCHANGED in Phase 4
```

Phase 4 creates ONLY the new files. Phase 5 modifies the HTML pages to consume them.

### Pattern 1: CSS @layer Order Declaration

**What:** Declare all layer names upfront at the top of design.css so cascade order is explicit and cannot be accidentally reordered by later imports.
**When to use:** Always — the declaration statement at the top of the file sets the priority order regardless of where rules appear later.

```css
/* Source: MDN @layer documentation — https://developer.mozilla.org/en-US/docs/Web/CSS/@layer */
/* Declare layer cascade order upfront — last listed = highest priority among layers */
@layer reset, tokens, tipografia, base, componenti, layout, utility;

/* Un-layered rules (not in any @layer) have HIGHER priority than all layers */
/* This means page-specific inline <style> blocks win automatically */

@layer reset {
  *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
  /* ... */
}

@layer tokens {
  :root {
    --bg-primary: #0a0a0f;
    /* ... all shared tokens ... */
  }
}
```

### Pattern 2: Per-Page Accent Color via `body[data-page]`

**What:** design.css defines `--page-accent` with a default value. Pages override it via inline `<style>` targeting `body[data-page="X"]`.
**When to use:** For the nav active link color, border-hover color, and any other per-page accent. Observed from codebase: laser=red, piega=amber, saldatura=orange, others=cyan.

```css
/* In design.css — provides default */
@layer tokens {
  :root {
    --page-accent: var(--accent-cyan);  /* default */
  }
  /* Per-page accent overrides via data-page attribute */
  body[data-page="laser"] { --page-accent: var(--accent-red); }
  body[data-page="piega"] { --page-accent: var(--accent-amber); }
  body[data-page="saldatura"] { --page-accent: var(--accent-orange); }
  /* archive, dashboard, ordini_estratti, welcome all use cyan = default */
}

@layer componenti {
  nav a.active {
    color: var(--page-accent);
    background: color-mix(in srgb, var(--page-accent) 10%, transparent);
    /* ... */
  }
}
```

```html
<!-- In each HTML page's <body> tag -->
<body data-page="laser">
```

### Pattern 3: Self-Hosted @font-face in design.css

**What:** All `@font-face` declarations in `@layer tipografia` (or outside layers at the top — font-face rules are not affected by layers in the normal sense). The font files live in `frontend/fonts/`.

```css
/* Source: Fontsource CDN documentation — https://fontsource.org/fonts/inter/cdn */
/* Paths are relative to design.css location, so ../fonts/ is not needed — both are in frontend/ */
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-display: swap;
  font-weight: 400;
  src: url('./fonts/inter-latin-400-normal.woff2') format('woff2');
  unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;
}
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-display: swap;
  font-weight: 500;
  src: url('./fonts/inter-latin-500-normal.woff2') format('woff2');
  unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;
}
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-display: swap;
  font-weight: 600;
  src: url('./fonts/inter-latin-600-normal.woff2') format('woff2');
  unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;
}
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-display: swap;
  font-weight: 700;
  src: url('./fonts/inter-latin-700-normal.woff2') format('woff2');
  unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;
}
```

**CRITICAL — URL path for `url()` in CSS:** When a browser loads `/design.css`, relative paths in `url()` are relative to the CSS file's URL, which is `/design.css` → base is `/`. So `url('./fonts/inter-400.woff2')` resolves to `/fonts/inter-400.woff2`. Flask's `/<path:filename>` route will serve `frontend/fonts/inter-400.woff2` for that request. This works correctly.

### Pattern 4: JetBrains Mono Note

**Observation from codebase:** `piega.html` and `saldatura.html` load JetBrains Mono from Google Fonts CDN alongside Inter. They use it for monospace timer displays. Design.css must NOT include JetBrains Mono — it is page-specific. Those pages' Phase 5 plans will handle the JetBrains Mono situation (either self-host it or fall back to system monospace stack since `archive.html` and `laser.html` use `'SF Mono', 'Fira Code', monospace` without loading a CDN font).

**Recommendation for Phase 4:** design.css defines only Inter. The monospace font stack question belongs to Phase 5.

### Pattern 5: shared.js as Classic Script (Global Exposure)

**What:** A classic `<script src="/shared.js"></script>` tag (no `type="module"`) exposes functions directly on `window`. Pages call them as bare function names.

```javascript
// Source: MDN JavaScript Modules — https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules
// Classic script (NOT type="module") — variables/functions go into global scope

/**
 * filterOrders(orders, query) — filtra un array di ordini per cliente o ID.
 * Basato su pattern esistente in archive.html (applyFilters).
 * @param {Array} orders — array di ordini dal backend
 * @param {string} query — stringa di ricerca (case-insensitive)
 * @returns {Array} ordini filtrati
 */
function filterOrders(orders, query) {
  if (!query || !query.trim()) return orders;
  const q = query.trim().toLowerCase();
  return orders.filter(order =>
    (order.cliente || '').toLowerCase().includes(q) ||
    (order.id || '').toLowerCase().includes(q)
  );
}

/**
 * debounce(fn, delay) — ritarda esecuzione per evitare chiamate eccessive.
 * Uso tipico: input ricerca con auto-refresh.
 * @param {Function} fn — funzione da ritardare
 * @param {number} delay — millisecondi (consigliato: 300)
 * @returns {Function} versione debounced
 */
function debounce(fn, delay) {
  let timer;
  return function(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * hasDataChanged(newData, lastHash) — confronta dati nuovi con hash precedente.
 * Basato su pattern esistente in laser.html (JSON.stringify hash).
 * Evita re-render inutili nelle pagine con auto-refresh.
 * @param {any} newData — nuovi dati dal backend
 * @param {string|null} lastHash — hash precedente (JSON.stringify)
 * @returns {{ changed: boolean, newHash: string }}
 */
function hasDataChanged(newData, lastHash) {
  const newHash = JSON.stringify(newData);
  return { changed: newHash !== lastHash, newHash };
}
```

### Pattern 6: Loading Order in HTML Pages (Phase 5 reference)

```html
<head>
  <!-- 1. Shared design system FIRST (no Google Fonts link) -->
  <link rel="stylesheet" href="/design.css">
  <!-- 2. Page-specific inline styles AFTER (un-layered = wins over @layer) -->
  <style>
    /* Per-page accent override */
    :root { --border-hover: rgba(255, 71, 87, 0.3); } /* laser example */
    nav a.active { color: var(--accent-red); /* ... */ }
    /* Page-specific component styles */
  </style>
</head>
<body data-page="laser">
  ...
  <!-- Shared utilities BEFORE page script -->
  <script src="/shared.js"></script>
  <script>
    /* Page-specific script that can call filterOrders(), debounce(), hasDataChanged() */
  </script>
</body>
```

### Anti-Patterns to Avoid

- **Using `type="module"` for shared.js:** Module-scoped functions don't appear on `window`. Pages cannot call `filterOrders()` as a bare name. Use classic script tag.
- **Using `!important` in design.css layers:** Not needed — un-layered inline styles already win. Adding `!important` to layered rules would REVERSE the cascade and block page overrides.
- **Putting `@font-face` inside an `@layer` block:** While technically valid, `@font-face` rules work outside layers. Placing them before the layer declarations avoids any cascade complexity.
- **Using `url('../fonts/...')` in CSS:** Both design.css and fonts/ are in the same `frontend/` directory. The correct path is `url('./fonts/inter-latin-400-normal.woff2')` — relative to the CSS file's URL base.
- **Keeping Google Fonts `<link>` tags in HTML:** Even if design.css defines Inter, leaving the CDN link tag causes a 30-second DNS/connection timeout per page load on LAN. All 3 Google Fonts link tags must be removed from every HTML page in Phase 5.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Font file conversion | TTF→WOFF2 conversion scripts | Download pre-built WOFF2 from jsDelivr fontsource | Fontsource already provides optimized, subsetted Latin WOFF2 |
| CSS cascade management | Specificity calculators, `!important` chains | CSS `@layer` | `@layer` is the standard solution for this exact problem |
| Font loading detection | JavaScript FontFace observer | `font-display: swap` in @font-face | CSS-native solution, zero JS needed |
| Module system | Custom import/export shims | Classic script tag globals | Zero overhead, no CORS, works with Flask static serving |

**Key insight:** This phase is creating infrastructure, not features. The patterns are well-established CSS/JS standards — the work is careful assembly, not invention.

## Common Pitfalls

### Pitfall 1: CSS @layer cascade inversion with `!important`

**What goes wrong:** Developer adds `!important` to a design.css rule thinking it will "ensure" it applies, but `!important` in a layered rule reverses the cascade — a `!important` in an early layer now BEATS everything, including page-specific styles. The page-specific accent color no longer works.
**Why it happens:** Misunderstanding that `@layer` cascade is already lower-priority than un-layered styles. No enforcement is needed.
**How to avoid:** Never use `!important` in design.css. Un-layered inline styles already win.
**Warning signs:** Page styles look identical across all pages despite per-page accent declarations.

### Pitfall 2: Wrong CSS `url()` path for fonts

**What goes wrong:** `@font-face` uses `url('/fonts/inter.woff2')` (absolute) or `url('../fonts/inter.woff2')` (wrong relative). Browser requests `/fonts/inter.woff2` which Flask serves from `frontend/fonts/` only if the absolute path is used. Relative paths in CSS are relative to the CSS file's URL, not the filesystem.
**Why it happens:** Confusion between filesystem paths and URL paths.
**How to avoid:** Use `url('./fonts/inter-latin-400-normal.woff2')` — both design.css and the fonts/ folder are served from the same `/` URL base (the frontend/ directory is the root). Flask's `send_from_directory(FRONTEND_FOLDER, filename)` with `filename='fonts/inter-latin-400-normal.woff2'` resolves correctly.
**Warning signs:** Browser DevTools Network tab shows 404 for font files; fallback system font appears instead of Inter.

### Pitfall 3: Layer order not declared upfront

**What goes wrong:** `@layer` blocks appear in different order than intended cascade. A component rule accidentally has lower priority than a reset rule.
**Why it happens:** If the layer declaration statement is missing, cascade order is determined by first-encounter order in the file.
**How to avoid:** Always start design.css with `@layer reset, tokens, tipografia, base, componenti, layout, utility;` before any rules.
**Warning signs:** Component styles don't appear; base styles win unexpectedly.

### Pitfall 4: shared.js loaded AFTER page script

**What goes wrong:** Page script calls `filterOrders()` before shared.js is parsed, resulting in `ReferenceError: filterOrders is not defined`.
**Why it happens:** Classic scripts execute in order of `<script>` tags.
**How to avoid:** Load `<script src="/shared.js"></script>` BEFORE the inline `<script>` block in every HTML page.
**Warning signs:** Console ReferenceError on pages that call shared utilities.

### Pitfall 5: JetBrains Mono left with CDN reference

**What goes wrong:** Phase 5 pages for piega.html and saldatura.html remove Inter CDN but leave JetBrains Mono CDN, still causing timeouts.
**Why it happens:** piega.html and saldatura.html load a combined Google Fonts URL with both Inter AND JetBrains Mono.
**How to avoid:** Phase 4 does NOT need to solve JetBrains Mono. Phase 5 plans for piega/saldatura must handle it (either self-host or replace with system monospace: `'Consolas', 'Courier New', monospace`).
**Warning signs:** piega.html and saldatura.html still hang for 30 seconds on LAN after Phase 5.

### Pitfall 6: Forgetting to remove `<link rel="preconnect">` tags

**What goes wrong:** Page has the Google Fonts `<link>` stylesheet removed, but leaves the two `<link rel="preconnect" href="https://fonts.googleapis.com">` tags. Browser still attempts DNS prefetch, causing timeouts.
**Why it happens:** The preconnect tags are easy to miss — they look harmless.
**How to avoid:** Phase 5 plans must remove ALL 3 Google Fonts-related `<link>` tags: preconnect to googleapis.com, preconnect to gstatic.com, and the stylesheet link.
**Warning signs:** Network tab shows connection attempts to fonts.googleapis.com even after `@import` removal.

## Code Examples

### design.css Full Structure

```css
/* Source: MDN @layer — https://developer.mozilla.org/en-US/docs/Web/CSS/@layer */
/* Source: Fontsource Inter — https://fontsource.org/fonts/inter/cdn */

/* ===== FONT FACE (outside layers — font loading is not cascade-dependent) ===== */
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-display: swap;
  font-weight: 400;
  src: url('./fonts/inter-latin-400-normal.woff2') format('woff2');
  unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;
}
/* ... same for 500, 600, 700 ... */

/* ===== LAYER ORDER DECLARATION (must come first) ===== */
@layer reset, tokens, tipografia, base, componenti, layout, utility;

/* ===== RESET ===== */
@layer reset {
  *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
}

/* ===== TOKENS ===== */
@layer tokens {
  :root {
    /* Colors */
    --bg-primary: #0a0a0f;
    --bg-secondary: #111827;
    --bg-card: rgba(255, 255, 255, 0.03);
    --bg-card-hover: rgba(255, 255, 255, 0.06);
    --bg-input: rgba(255, 255, 255, 0.05);
    --border-glass: rgba(255, 255, 255, 0.06);
    --border-hover: rgba(0, 212, 255, 0.3); /* default = cyan */
    --text-primary: #e6e6e6;
    --text-secondary: #6b7b8d;
    --text-muted: #4a5568;
    /* Accent palette */
    --accent-cyan: #00d4ff;
    --accent-green: #00e676;
    --accent-red: #ff4757;
    --accent-amber: #ffa502;
    --accent-orange: #ff6348;
    --accent-purple: #a855f7;
    /* Page accent (overridden per-page via body[data-page] or inline <style>) */
    --page-accent: var(--accent-cyan);
    /* Radius */
    --radius-lg: 16px;
    --radius-md: 12px;
    --radius-sm: 8px;
    /* Transition */
    --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
  /* Per-page accent tokens */
  body[data-page="laser"]    { --page-accent: var(--accent-red); }
  body[data-page="piega"]    { --page-accent: var(--accent-amber); }
  body[data-page="saldatura"] { --page-accent: var(--accent-orange); }
}

/* ===== TIPOGRAFIA ===== */
@layer tipografia {
  body {
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    overflow-x: hidden;
  }
}

/* ===== BASE ===== */
@layer base {
  /* Ambient background animation, button base, input base, label base */
  body::before { /* ambient float */ }
  @keyframes ambientFloat { /* ... */ }
  @keyframes fadeInUp { /* ... */ }
  @keyframes spin { /* ... */ }
  button { font-family: inherit; cursor: pointer; transition: var(--transition); outline: none; }
  label { display: block; margin-bottom: 6px; color: var(--text-secondary); font-weight: 500; font-size: 13px; }
}

/* ===== COMPONENTI ===== */
@layer componenti {
  /* nav, .glass-card, .btn-primary, .btn-secondary, .message, .loading, .spinner */
  nav {
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 64px;
    /* ... shared nav rules ... */
  }
  nav a.active {
    color: var(--page-accent);
    /* ... */
  }
  .glass-card { /* ... */ }
  .btn-primary { /* ... */ }
  .btn-secondary { /* ... */ }
  .message { /* ... */ }
  .spinner { /* ... */ }
}

/* ===== LAYOUT ===== */
@layer layout {
  /* main, .two-columns, .form-section, .form-group, .button-group */
  main { position: relative; z-index: 1; margin-top: 88px; padding: 0 24px 60px; }
  .two-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
}

/* ===== UTILITY ===== */
@layer utility {
  /* Responsive overrides */
  @media (max-width: 768px) {
    nav { padding: 0 16px; gap: 4px; }
    .two-columns { grid-template-columns: 1fr; }
    /* ... */
  }
}
```

### shared.js Complete File

```javascript
// shared.js — Utility globali per Schedulatore Laser
// Caricato come script classico (NON type="module") — espone funzioni su window
// Ogni pagina carica questo file PRIMA dello script inline

/**
 * filterOrders — filtra ordini per cliente o ID
 * Chiamata: const filtered = filterOrders(allOrders, searchQuery);
 */
function filterOrders(orders, query) {
  if (!query || !query.trim()) return orders;
  const q = query.trim().toLowerCase();
  return orders.filter(order =>
    (order.cliente || '').toLowerCase().includes(q) ||
    (order.id || '').toLowerCase().includes(q)
  );
}

/**
 * debounce — ritarda esecuzione su input frequente
 * Chiamata: const debouncedFilter = debounce(() => applyFilters(), 300);
 */
function debounce(fn, delay) {
  let timer;
  return function(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * hasDataChanged — rileva cambiamenti nei dati per evitare re-render
 * Basato su pattern in laser.html (JSON.stringify hash)
 * Chiamata:
 *   const { changed, newHash } = hasDataChanged(orders, lastDataHash);
 *   if (changed) { lastDataHash = newHash; renderOrders(orders); }
 */
function hasDataChanged(newData, lastHash) {
  const newHash = JSON.stringify(newData);
  return { changed: newHash !== lastHash, newHash };
}
```

### Font Download via PowerShell (Windows LAN environment)

```powershell
# Download Inter WOFF2 from jsDelivr fontsource CDN
# Run once — files go to app/frontend/fonts/
$base = "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest"
$dest = "app/frontend/fonts"
New-Item -ItemType Directory -Force -Path $dest

@(400, 500, 600, 700) | ForEach-Object {
  $weight = $_
  Invoke-WebRequest "$base/latin-$weight-normal.woff2" -OutFile "$dest/inter-latin-$weight-normal.woff2"
}
```

Or via curl (Git Bash / WSL):
```bash
mkdir -p app/frontend/fonts
for weight in 400 500 600 700; do
  curl -sL "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-${weight}-normal.woff2" \
    -o "app/frontend/fonts/inter-latin-${weight}-normal.woff2"
done
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Google Fonts CDN `<link>` | Self-hosted WOFF2 with `@font-face` | Privacy/LAN concerns widespread since ~2022 | Eliminates 30-sec LAN timeout; no DNS lookup needed |
| CSS specificity management (BEM, OOCSS) | CSS `@layer` | Baseline since March 2022 | Explicit cascade without selector complexity |
| Shared CSS via global `<style>` in templates | External CSS with `@layer` | Long-established best practice | Single source of truth; browser caches shared file |
| ES modules for shared utilities | Classic script globals for simple cases | Classic scripts still appropriate for simple sharing | Zero CORS complexity with Flask static serving |

**Not deprecated in this context:**
- CSS custom properties (CSS variables): Still the standard for design tokens
- `font-display: swap`: Still correct for self-hosted fonts

## Open Questions

1. **JetBrains Mono for piega.html and saldatura.html**
   - What we know: Both pages load JetBrains Mono from Google Fonts CDN for monospace timer displays. Phase 4 only handles Inter.
   - What's unclear: Phase 5 plans for piega/saldatura must decide: self-host JetBrains Mono WOFF2 (adds complexity to those plans) OR replace with system monospace stack (`'Consolas', 'Courier New', monospace`).
   - Recommendation: Phase 5 plans for piega/saldatura replace JetBrains Mono with `'Consolas', 'Courier New', monospace` — removes CDN dependency with minimal visual impact on timer displays. If stakeholders require JetBrains Mono exactly, use fontsource CDN pattern (same as Inter) to download WOFF2 in those plans.

2. **Which CSS components are truly shared vs. page-specific**
   - What we know: The `:root` tokens (22 lines × 7) and navbar CSS (53 lines × 7) are 100% duplicated. Other sections (glass-card, buttons, messages, spinner, animations) appear nearly identical but could have subtle page-specific variations.
   - What's unclear: Without a full diff of all 7 style blocks, some "component" CSS might have page-specific tuning that would be broken by moving to shared.
   - Recommendation: Move tokens, reset, navbar, and the 8 most clearly shared components (glass-card, btn-primary, btn-secondary, message, spinner, loading, fadeInUp, ambientFloat) to design.css. Leave anything with per-page variations in inline styles. Phase 5 agents verify by visual comparison.

3. **Does `send_from_directory` handle `fonts/` subdirectory correctly**
   - What we know: Flask route `/<path:filename>` passes the full path to `send_from_directory(FRONTEND_FOLDER, filename)`. Flask's `send_from_directory` uses `safe_join()` which correctly handles subdirectory paths.
   - What's unclear: Needs runtime verification (quick test: `curl http://localhost:5000/fonts/inter-latin-400-normal.woff2` after placing file).
   - Recommendation: Include this as Step 1 verification in the plan — place one font file and test the URL before building all of design.css.

## Sources

### Primary (HIGH confidence)
- MDN Web Docs `@layer` — https://developer.mozilla.org/en-US/docs/Web/CSS/@layer — cascade behavior, un-layered vs layered priority, browser support
- MDN Web Docs `font-display` — https://developer.mozilla.org/en-US/docs/Web/CSS/@font-face/font-display — font loading strategies
- MDN JavaScript Modules — https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules — module vs classic script scope
- CSS-Tricks @layer guide — https://css-tricks.com/css-cascade-layers/ — confirmed: "un-layered styles have highest priority"
- Fontsource CDN — https://fontsource.org/fonts/inter/cdn — WOFF2 URL pattern and @font-face declarations
- jsDelivr CDN verification — `https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-400-normal.woff2` — confirmed returns WOFF2 binary

### Secondary (MEDIUM confidence)
- Fontsource npm page — https://fontsource.org/fonts/inter/install — package structure for Inter weights
- CSS-Tricks Cascade Layers — multiple verified articles confirm layer cascade behavior
- Flask `send_from_directory` docs — confirmed handles subdirectory paths via `safe_join()`

### Tertiary (LOW confidence)
- Exact Inter WOFF2 file sizes — not verified (estimated ~30-50kB per weight based on search results)
- JetBrains Mono replacement visual impact — subjective assessment

## Metadata

**Confidence breakdown:**
- Standard stack (CSS @layer, WOFF2, classic script): HIGH — MDN documentation + browser baseline status confirmed
- Architecture (@font-face paths, layer order): HIGH — verified against MDN and codebase analysis
- Font download URLs (jsDelivr fontsource): HIGH — URL pattern confirmed returning font binary
- Pitfalls (CSS !important reversal, path resolution): HIGH — MDN specification confirmed
- JetBrains Mono question: MEDIUM — identified from codebase, resolution not tested

**Research date:** 2026-02-19
**Valid until:** 2026-06-01 (CSS @layer is stable baseline; Inter font versioning is stable)

# Technology Stack — UI/UX Redesign

**Domain:** Vanilla CSS/JS design system for industrial scheduling web app
**Researched:** 2026-02-19
**Confidence:** HIGH (verified via MDN, caniuse data, web almanac, official sources)

---

## Context: What Already Exists (DO NOT Replace)

The backend stack is frozen. This research covers only frontend additions.

**Current frontend baseline:**
- 7 self-contained HTML files (`app/frontend/`)
- Inline `<style>` and `<script>` in every page
- Google Fonts CDN: Inter (300/400/500/600/700/800)
- CSS custom properties already defined (partially) in each page's `:root`
- Dark glassmorphism theme with cyan/green/red/amber accents
- No shared stylesheets — token duplication across all 7 files
- Flask serves static files directly (no build pipeline, no bundler)

**The problem this milestone solves:** The `:root` block with ~15 CSS custom properties is copy-pasted into all 7 files. Any design change requires editing 7 files. There is no shared CSS, no responsive breakpoints, no search/filter system.

---

## Recommended Stack Additions

### Core: Shared CSS Architecture

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| External `design-system.css` | — (authored) | Single source of truth for all CSS tokens | Flask already serves static files; one `<link>` tag per page eliminates the copy-paste token problem |
| CSS Custom Properties (`@property`) | Native CSS | Design tokens: colors, spacing, radii, transitions | Already partially used — formalize and centralize. Zero runtime cost, browser-native, no build step |
| CSS `@layer` | Native CSS (Chrome 99+, FF 97+, Safari 15.4+) | Cascade control: reset → tokens → base → components → utilities | Prevents specificity wars when refactoring per-page inline styles; lets inline `<style>` override shared styles predictably |
| CSS Grid + Flexbox | Native CSS | Layout: KPI cards, kanban columns, phase grids | Both are fully supported and the correct tools. Grid for 2D layout (dashboard), Flexbox for 1D flow (nav, card internals) |

**Why NOT a CSS framework (Tailwind, Bootstrap, etc.):** The constraint is hard — no build tools, no bundler. Tailwind v4 requires a build step. Bootstrap adds 150KB+ of unused CSS. The existing codebase proves vanilla CSS works well here; the problem is organization, not capability.

### Typography: Self-Host Inter

| Decision | Why |
|----------|-----|
| Self-host Inter via WOFF2 in `app/frontend/fonts/` | This app runs on a LAN. Factory floor tablets have no internet access (or restricted access). Google Fonts CDN will time out. A real-world PageSpeed case study showed mobile score jumping from 66 to 94 after switching CDN to self-hosted Inter. LAN = no CDN benefit anyway |
| Subset to Latin only | Full Inter WOFF2 is ~300KB. Latin subset is ~60KB. Use `font-display: swap` |
| Keep 4 weights: 400, 500, 600, 700 | Current pages request 300/400/500/600/700/800. 300 is redundant with 400 for dark screens; 800 is only used in logo. Trim to 4 weights |

**Download:** https://fontsource.org/fonts/inter — provides pre-subsetted WOFF2 files for self-hosting.

### Responsive Layout

| Pattern | Breakpoints | Why |
|---------|-------------|-----|
| Two breakpoints only | `768px` (tablet portrait) and `1024px` (tablet landscape / small desktop) | Industrial tablets (typical: 10"-12" landscape, 1280x800) hit the 1024px breakpoint. PC desktops are 1440px+. Three zones: mobile-not-supported / tablet (1024px) / desktop (1440px+) |
| CSS Grid `auto-fit` + `minmax()` | No breakpoint needed | KPI cards: `grid-template-columns: repeat(auto-fit, minmax(200px, 1fr))` — reflows automatically |
| CSS Container Queries (`@container`) | Chrome 105+, FF 110+, Safari 16+ | Use for card-level responsive behavior (e.g., kanban cards that adapt when column is narrow). Media queries handle page-level layout; container queries handle component-level |

**Tablet target:** 1024px landscape is the critical breakpoint. Android industrial tablets (Zebra, Panasonic) and iPad Pro both report 1024px wide in landscape. Design for this as the primary tablet target.

**Touch targets:** WCAG 2.5.8 mandates 24×24px minimum; iOS recommends 44×44px; Android recommends 48×48px. Use `min-height: 48px` for all interactive elements in the tablet stylesheet. Use `touch-action: manipulation` on buttons to eliminate the 300ms tap delay on older Android WebViews.

### Search and Filter (Vanilla JS)

| Pattern | Implementation | Why |
|---------|---------------|-----|
| Debounced input handler | `setTimeout` / `clearTimeout`, 300ms delay | Prevents triggering filter on every keystroke. Zero dependencies. Standard vanilla JS pattern. 300ms is the proven sweet spot — fast enough to feel live, slow enough to not thrash the DOM |
| Array `.filter()` + `.forEach()` for DOM manipulation | DOM `hidden` attribute or `display: none` via class | Filter runs against an in-memory data array (already fetched from `/api/orders`), then toggles visibility on rendered cards. No re-fetch on filter |
| Multi-criteria filter via `.every()` | Single filter function, array of active predicates | Cleaner than nested `if` chains. `activeFilters.every(fn => fn(order))` — add/remove predicate functions per active filter chip |
| URL `searchParams` for filter state | `URLSearchParams` API | Lets operators bookmark/share a filtered view. No library needed. Works on all modern browsers |

**Do NOT use:** External search libraries (Fuse.js, Lunr.js, MiniSearch) for this use case. The data set is small (hundreds of orders, not thousands), and fuzzy search is not needed — factory operators filter by exact status, client, date. A simple `.includes()` on strings is faster and has zero dependency risk.

### CSS Modern Features (Safe to Use Now)

| Feature | Browser Support | Use Case |
|---------|----------------|----------|
| CSS `@layer` | Chrome 99+, FF 97+, Safari 15.4+ — **97%+ global** | Organize shared stylesheet into layers; protect tokens from specificity leaks |
| CSS Container Queries (`@container`) | Chrome 105+, FF 110+, Safari 16+ — **production ready** | Card-level responsive behavior |
| CSS `:has()` | Chrome 105+, FF 121+, Safari 15.4+ — **Baseline Widely Available** | Style parent based on child state (e.g., `.card:has(.checkbox:checked)` highlight entire card) |
| CSS Grid Subgrid | Chrome 117+, FF 71+, Safari 16+ — **97%+ global** | Align KPI card internals across a row without JS |
| CSS `color-mix()` | Chrome 111+, FF 113+, Safari 16.2+ | Generate hover/active states from base color token: `color-mix(in srgb, var(--accent-cyan) 80%, white)` |
| CSS `scroll-behavior: smooth` | Universal | Smooth scroll to phase sections |

**Stick with IntersectionObserver (not CSS scroll-driven animations):** CSS scroll-driven animations are Chrome-only as of early 2026. IntersectionObserver + CSS class toggle is the reliable cross-browser pattern for reveal effects and has been stable since 2020.

### Font Icon Strategy

**Use:** Unicode symbols + CSS pseudo-elements for simple icons (checkmarks, arrows, status dots). No icon library needed.

**If more icons are required:** Use a single SVG sprite file (`icons.svg`) inlined into the HTML shell. Zero HTTP requests, no JavaScript, full CSS styling. Avoid Font Awesome and similar — they add 80KB+ and have GDPR/CDN concerns on a LAN.

---

## File Structure (What to Create)

```
app/frontend/
├── design-system.css          # NEW: Single source of truth
│   └── Layers: reset, tokens, typography, components, utilities
├── fonts/                     # NEW: Self-hosted Inter WOFF2
│   ├── inter-latin-400.woff2
│   ├── inter-latin-500.woff2
│   ├── inter-latin-600.woff2
│   └── inter-latin-700.woff2
├── dashboard.html             # MODIFIED: remove duplicate :root, link design-system.css
├── laser.html                 # MODIFIED: same
├── piega.html                 # MODIFIED: same
├── saldatura.html             # MODIFIED: same
├── ordini_estratti.html       # MODIFIED: same
├── archive.html               # MODIFIED: same
└── welcome.html               # MODIFIED: same
```

---

## design-system.css Internal Architecture

Use CSS `@layer` to structure the shared stylesheet:

```css
/* Layer declaration order (lowest to highest priority) */
@layer reset, tokens, typography, base, components, layout, utilities;

@layer tokens {
  :root {
    /* --- Colors --- */
    --bg-primary: #0a0a0f;
    --bg-secondary: #111827;
    /* ... */

    /* --- Spacing scale --- */
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-6: 24px;
    --space-8: 32px;

    /* --- Typography scale --- */
    --text-xs: 11px;
    --text-sm: 13px;
    --text-base: 15px;
    --text-lg: 18px;
    --text-xl: 24px;
    --text-2xl: 32px;

    /* --- Radii --- */
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 16px;
    --radius-full: 9999px;

    /* --- Transitions --- */
    --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-base: 250ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-slow: 400ms cubic-bezier(0.4, 0, 0.2, 1);

    /* --- Shadows (elevation for dark theme) --- */
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.4);
    --shadow-md: 0 4px 16px rgba(0,0,0,0.5);
    --shadow-lg: 0 8px 32px rgba(0,0,0,0.6);
  }
}

@layer components {
  /* Shared nav, card, badge, button, input styles */
}

@layer utilities {
  /* Single-purpose utility classes: .sr-only, .truncate, etc. */
}
```

Per-page inline `<style>` blocks remain for page-specific overrides (e.g., laser page uses red ambient, dashboard uses cyan). Because inline styles have higher cascade priority than external stylesheets, and `@layer` makes this explicit, there is no specificity conflict.

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Tailwind CSS | Requires PostCSS build step; contradicts no-build-tools constraint | Native CSS custom properties |
| Bootstrap | 150KB+ payload; opinionated component markup conflicts with existing HTML | Write shared `design-system.css` |
| CSS preprocessors (Sass/Less) | Require Node.js build step; the team uses Flask/Python | Native CSS `@layer` + custom properties achieve the same organization |
| Google Fonts CDN | LAN deployment: tablets may have no internet; DNS resolution adds latency | Self-host Inter WOFF2 in `app/frontend/fonts/` |
| Fuse.js / Lunr.js / MiniSearch | Overkill for this dataset; adds dependency risk | Vanilla `.filter()` + debounced input handler |
| Font Awesome / Heroicons CDN | Same CDN risk as Google Fonts; extra HTTP request | Unicode symbols + inline SVG sprite |
| CSS scroll-driven animations | Chrome-only in early 2026 | IntersectionObserver + CSS class toggle |
| CSS-in-JS patterns | No JavaScript framework; meaningless here | Standard external CSS |
| `!important` overrides | Specificity hack — `@layer` makes this unnecessary | Proper `@layer` cascade ordering |
| Separate color tokens per page | Current problem being solved — 15 tokens duplicated 7 times | Single `design-system.css` |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Shared styles | External `design-system.css` | CSS-in-HTML `<template>` injection | Template injection requires JS at runtime and breaks Flask's static file serving |
| Shared styles | External `design-system.css` | Web Components / Shadow DOM | Overkill; Shadow DOM isolates styles (opposite of what we want for shared tokens) |
| Icons | Unicode + inline SVG | Font Awesome | CDN dependency; 80KB+ unneeded weight on LAN |
| Font loading | Self-hosted WOFF2 | Google Fonts CDN | LAN = no reliable internet; CDN benefit is zero |
| Search | Vanilla `.filter()` | Fuse.js | Fuzzy search not needed for status/date filtering; adds 25KB and a dependency |
| Breakpoints | Two breakpoints (768, 1024) | Three breakpoints (480, 768, 1024) | Factory operators don't use phones; 480px tier is wasted complexity |
| Responsive cards | `auto-fit minmax()` grid | Fixed column counts with media queries | `auto-fit` reflows without breakpoints — simpler and handles any tablet orientation |

---

## Integration with Existing Flask Setup

Flask serves `app/frontend/` as static files. Adding `design-system.css` and `fonts/` requires zero backend changes. The existing route `GET /<path:filename>` already handles arbitrary static files.

In each HTML `<head>`:
```html
<!-- Replace inline Google Fonts link -->
<style>
  @font-face {
    font-family: 'Inter';
    src: url('fonts/inter-latin-400.woff2') format('woff2');
    font-weight: 400;
    font-display: swap;
  }
  /* ... other weights */
</style>

<!-- Add before page-specific styles -->
<link rel="stylesheet" href="design-system.css">

<!-- Keep page-specific inline <style> block below — cascade order works correctly -->
```

---

## No Installation Required

This is purely authored CSS and WOFF2 font files. There is no `npm install`, no build step, no toolchain change. The only action is:

1. Download Inter WOFF2 subset files from fontsource.org
2. Author `design-system.css`
3. Add `<link>` tag to each of the 7 HTML files
4. Remove duplicate `:root` blocks from inline styles

---

## Version Compatibility

| Feature | Chrome | Firefox | Safari | Notes |
|---------|--------|---------|--------|-------|
| CSS Custom Properties | 49+ | 31+ | 9.1+ | Universal — already in use |
| CSS `@layer` | 99+ | 97+ | 15.4+ | Safe; 97%+ global coverage |
| CSS Grid + Subgrid | 117+ / 57+ | 71+ | 16+ / 10.1+ | Safe; 97%+ global coverage |
| CSS Container Queries | 105+ | 110+ | 16+ | Safe for production 2025+ |
| CSS `:has()` | 105+ | 121+ | 15.4+ | Baseline Widely Available |
| `color-mix()` | 111+ | 113+ | 16.2+ | Safe for modern browsers |
| IntersectionObserver | 58+ | 55+ | 12.1+ | Universal — stable since 2020 |
| URLSearchParams | 49+ | 44+ | 10.1+ | Universal |
| WOFF2 fonts | 36+ | 35+ | 12+ | Universal |

Industrial tablets running Android 9+ (Chrome 80+) or iOS 14+ (Safari 14+) will support all features listed above.

---

## Sources

- [MDN: CSS Container Queries](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Containment/Container_queries) — browser support, fallback patterns
- [caniuse: CSS @layer](https://caniuse.com/css-cascade-layers) — 97%+ global coverage confirmed
- [caniuse: CSS :has()](https://caniuse.com/css-has) — Baseline Widely Available
- [caniuse: CSS Subgrid](https://caniuse.com/css-subgrid) — 97%+ global coverage confirmed
- [CSS-Tricks: Cascade Layers Guide](https://css-tricks.com/css-cascade-layers/) — design system layering architecture
- [CSS-Tricks: Organizing Design System Patterns with @layer](https://css-tricks.com/organizing-design-system-component-patterns-with-css-cascade-layers/) — component pattern organization
- [Web Almanac 2025: Fonts](https://almanac.httparchive.org/en/2025/fonts) — self-hosting trends, Inter adoption
- [MDN: @font-face / font-display](https://developer.mozilla.org/en-US/docs/Web/CSS/@font-face/font-display) — `font-display: swap` pattern
- [Penpot Blog: Design Tokens and CSS Variables](https://penpot.app/blog/the-developers-guide-to-design-tokens-and-css-variables/) — token architecture
- [BrowserStack: Responsive Breakpoints 2025](https://www.browserstack.com/guide/responsive-design-breakpoints) — 1024px tablet landscape validation
- [WCAG 2.5.8: Target Size Minimum](https://wcag.dock.codes/documentation/wcag258/) — 44×44px touch target recommendation
- [freecodecamp: Debounce Your Search](https://www.freecodecamp.org/news/optimize-search-in-javascript-with-debouncing/) — vanilla JS debounce pattern
- [FrontendMasters: You Might Not Need That Framework](https://frontendmasters.com/blog/you-might-not-need-that-framework/) — vanilla JS filter viability
- [Smashing Magazine: Accessible Tap Target Sizes](https://www.smashingmagazine.com/2023/04/accessible-tap-target-sizes-rage-taps-clicks/) — industrial tablet touch optimization
- [MDN: IntersectionObserver API](https://developer.mozilla.org/en-US/docs/Web/API/Intersection_Observer_API) — reveal animations without scroll-driven animation risk
- [fontsource.org/fonts/inter](https://fontsource.org/fonts/inter) — pre-subsetted WOFF2 Inter for self-hosting

---

*Stack research for: Schedulatore Laser UI/UX Redesign — Vanilla CSS Design System*
*Researched: 2026-02-19*

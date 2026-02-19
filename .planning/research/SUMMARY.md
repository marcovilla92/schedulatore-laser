# Project Research Summary

**Project:** Schedulatore Laser — UI/UX Redesign v1.2
**Domain:** Industrial production scheduling dashboard — vanilla CSS/JS design system migration for metal carpentry order management
**Researched:** 2026-02-19
**Confidence:** HIGH

## Executive Summary

This milestone is a frontend-only UI/UX redesign of an existing, fully-functional production scheduling web app. The backend (Flask + SQLite + 16 PDF parsers) is frozen and untouched. The core engineering problem is organizational: seven self-contained HTML files each contain identical copies of ~200 lines of CSS tokens and utility rules, making any visual change a 7-file edit. The recommended approach is to extract shared CSS into a single `design.css` file (served by Flask's existing static catch-all route with zero backend changes), self-host the Inter font to eliminate a critical LAN dependency on Google Fonts CDN, and introduce a `shared.js` for reusable filter/debounce/refresh utilities. No build tools, no frameworks, no npm — the constraint is hard and the solution is native CSS and vanilla JS.

The feature priority is clear from industrial HMI research: operators need a KPI hero row at the top of the dashboard, minimum 48px touch targets for gloved-hand operation, delivery deadline urgency coloring on order cards, and a visible search/filter UI on phase workstation pages. The welcome splash page must be eliminated — production operators reject it universally. The mixed panoramic dashboard (unified KPI + phase status + scadenze view) is the flagship differentiator but is architecturally complex; it should follow after the design system and individual page redesigns are stable.

The highest-probability failure mode is the auto-refresh conflict: five phase pages poll every 5–10 seconds and currently rebuild the entire DOM, which will destroy any search/filter state the operator has entered. This must be architecturally solved first — separating data-fetch from DOM-render — before search is added to any page. The second major risk is the LAN font CDN timeout: Google Fonts will stall page loads for 30 seconds when the factory network has no internet access. Self-hosting Inter is non-negotiable and must happen in Phase 1.

## Key Findings

### Recommended Stack

The stack requires no new dependencies — only two authored files and four WOFF2 font files. A single `design.css` uses CSS `@layer` to organize tokens, reset, base, components, layout, and utilities with explicit cascade control. CSS Custom Properties in `:root` provide all design tokens (colors, spacing, radii, transitions, typography). Per-page accent theming (laser=red, piega=amber, saldatura=green) is handled via `body[data-page="laser"]` selectors in the shared file overriding only the abstract `--page-accent` token — never redefining base color tokens per page. CSS Grid `auto-fit minmax()` handles responsive card layouts without breakpoints; two explicit breakpoints (1024px and 768px) handle nav and page structure adaptation for industrial tablets.

**Core technologies:**
- `design.css` (authored): Single source of truth for all CSS tokens — eliminates 7x duplication with zero build tooling
- Self-hosted Inter WOFF2 (4 weights: 400/500/600/700): Eliminates 30-second LAN font CDN timeout; one `@font-face` block in `design.css` replaces 7 Google Fonts links
- CSS `@layer`: Cascade control for the shared stylesheet — prevents specificity conflicts between shared and page-level inline styles; 97%+ global browser coverage
- CSS Container Queries + `:has()`: Card-level responsive behavior and parent-child state styling without JavaScript; production-ready since 2025
- `shared.js` (authored): `filterOrders()`, `debounce()`, `hasDataChanged()` extracted once and loaded by pages that need them
- Vanilla JS `.filter()` + debounced input: Client-side search over in-memory order array — no new API endpoints needed; adequate for the dataset size (10–200 active orders)

**What NOT to use:** Tailwind (requires build step), Bootstrap (150KB+ unused CSS), Google Fonts CDN (LAN timeout), Fuse.js/search libraries (overkill, dependency risk), CSS scroll-driven animations (Chrome-only), `!important` overrides (masked by proper `@layer` usage).

### Expected Features

**Must have (table stakes — v1.2 launch):**
- Shared `design.css` loaded by all pages — eliminates token duplication, enables consistent status colors
- Remove welcome.html as landing; Flask `GET /` redirects to dashboard
- Dashboard KPI row: ordini attivi, scadenze oggi, scadenze settimana, fasi in corso
- Delivery deadline urgency coloring on order cards: overdue=red, today=amber, future=none
- Sticky navbar with global search input (client-side filter on current page data)
- Touch targets minimum 48px on all interactive elements — 56px for critical phase actions (Avvia, Completa)
- Responsive layout: ≥1024px multi-column desktop, 768–1023px single-column tablet
- Auto-refresh indicator: "Aggiornato X sec fa" timestamp + manual "Aggiorna ora" button
- Empty state messages in Italian when a phase has no orders
- Progress bars: 12px minimum height, "N/M articoli" text label
- Color-blind accessible status indicators: color + icon shape (never color alone)

**Should have (differentiators — v1.2 if P1 is solid, else v1.2.x):**
- Additive filter chips as removable pills with URL query param state
- Mixed panoramic dashboard: unified KPI + active phase summary + delivery urgency in one view
- Phase-accent ambient theming formalized in design system (already partially done)
- Inline article completion on phase cards (reduce taps from expand→checkbox to tap-to-check)
- Compact week-view calendar strip on dashboard

**Defer (v2+):**
- Backend full-text search API (new endpoint, backend frozen for this milestone)
- Real-time WebSocket push updates (backend architecture change required)
- Analytics charts and throughput graphs (new API endpoints needed)
- Light/bright theme variant (doubles CSS maintenance burden; improve dark theme contrast instead)
- Virtual scroll / infinite scroll (premature: typical active orders is 5–20)

### Architecture Approach

The architecture introduces two new shared files into the existing flat `app/frontend/` directory, served by Flask's existing `/<path:filename>` catch-all route with zero backend changes. `design.css` uses CSS `@layer` (reset → tokens → typography → base → components → layout → utilities) and is linked before each page's inline `<style>` block, allowing per-page inline rules to safely override shared components. `shared.js` exposes `filterOrders()`, `debounce()`, and `hasDataChanged()` as globals used by page-level scripts. Per-page state (current filter term, all-orders array, scroll position) stays in page-level `<script>` blocks — not in shared.js — keeping pages independent. Migration is incremental: one page per commit, validating the shared files work before touching the next page.

**Major components:**
1. `frontend/design.css` — All CSS tokens, reset, base layout, nav, card, button, modal, badge, animation, responsive breakpoints; loaded by all 7 pages via `<link>` in `<head>`
2. `frontend/shared.js` — `filterOrders()`, `debounce()`, `hasDataChanged()`, `formatTime()`; loaded only by pages that use search/filter/refresh utilities
3. `frontend/fonts/` — Self-hosted Inter WOFF2 (4 weights); `@font-face` declarations in `design.css`; eliminates all Google Fonts CDN references
4. Per-page `<style>` blocks — Shrink from ~700 lines to ~100 lines of page-specific layout only (calendar grid, accordion, etc.)
5. Per-page `<script>` blocks — Retain page-specific business logic (loadOrders, renderOrders, phase API calls); call shared.js utilities where applicable

### Critical Pitfalls

1. **Auto-refresh destroys filter state** — Five phase pages rebuild the entire DOM on every 5–10 second interval. Adding search/filter without first separating data-fetch from DOM-render means operators lose their filter every 5 seconds. Prevention: extract `fetchOrders()` (updates `allOrders`) from `renderOrders(filter)` (renders from current filter state); the interval only calls fetch, which then calls render with the preserved filter state.

2. **Google Fonts CDN 30-second timeout on LAN** — All 7 pages currently link `fonts.googleapis.com`. When the factory network has no internet (common during production), every page load stalls for 30 seconds. With 5-second auto-refresh, this creates a frozen/blank screen loop. Prevention: self-host Inter WOFF2 in `app/frontend/fonts/` in Phase 1, before any other page work.

3. **Shared CSS merges per-page accent colors** — The `:root` blocks look identical across pages but contain intentional per-page accent color variants (laser=red, piega=amber, saldatura=green/blue). A developer migrating "duplicates" to the shared file will accidentally unify all pages to one accent. Prevention: document explicitly in `design.css` that per-page accent variables stay in each page's inline `:root`; use `body[data-page]` selectors in shared CSS for the `--page-accent` override pattern only.

4. **Touch targets too small for gloved operators** — The current UI was designed for desktop mouse use. Many interactive elements are 32–36px — half the 56px recommended for industrial gloved-hand operation. Wrong taps on Avvia/Completa create production errors. Prevention: audit all interactive elements on phase workstation pages during their redesign phase; enforce 48px minimum and 56px for critical actions; use label-wrapping for checkbox rows.

5. **Glassmorphism contrast failure under factory lighting** — `--text-secondary: #6b7b8d` achieves only 3.8:1 contrast (fails WCAG AA 4.5:1). `--text-muted: #4a5568` is 2.3:1 — a hard failure. Factory ambient light further degrades perceived contrast. Prevention: validate every text/background combination through WCAG contrast checker before finalizing design tokens; target 7:1 for body text (AAA) given factory conditions.

## Implications for Roadmap

Based on research, the following phase structure is recommended. The dependency chain is strict: the design system must precede all page work, the design system includes font self-hosting, and the dashboard should be last because it is the most complex page.

### Phase 1: Shared Design System + Font Self-Hosting
**Rationale:** Every other feature depends on `design.css` existing first. Font self-hosting must happen here — it is the highest-severity pitfall (30-second page stalls on LAN) and this is the only phase where it fits naturally (one `@font-face` block in `design.css` replaces all 7 Google Fonts links simultaneously). This phase has no page-specific risk — it creates files that pages will later link to.
**Delivers:** `design.css` with full token set, CSS `@layer` structure, responsive breakpoints, and `@font-face` declarations; `shared.js` with `filterOrders()`, `debounce()`, `hasDataChanged()`; `app/frontend/fonts/` with Inter WOFF2 subset files. No page is modified in this phase — the shared files are created and verified accessible via Flask before any page touches them.
**Addresses:** FEATURES: shared CSS design system (P1), status color consistency. PITFALLS: Google Fonts CDN timeout (critical), CSS load order race (architectural).
**Avoids:** Merging per-page accent colors into shared CSS — enforce `body[data-page]` pattern from day one with comments.
**Research flag:** Standard patterns — no additional research needed. Flask static serving verified, CSS `@layer` is well-documented.

### Phase 2: Archive + Ordini Estratti Migration (Low-Risk Pages)
**Rationale:** These pages have no auto-refresh cycle (ordini_estratti has no polling; archive has a simple filter). They are the safest pages to validate that linking `design.css` works correctly: the shared file resolves tokens, the inline `<style>` block still wins for page-specific rules, and no production-critical functionality is at risk during validation. Archive already has a filter bar, making it the ideal testbed for the filter/search pattern.
**Delivers:** Two pages fully migrated to the shared design system. Validation that the CSS cascade hierarchy works correctly before touching production-critical phase pages. Inline `<style>` blocks reduced from ~700 to ~100 lines each.
**Addresses:** FEATURES: responsive layout (PC + tablet), touch targets audit, empty state messages. PITFALLS: CSS load order race (validated here before it can affect laser/piega/saldatura).
**Avoids:** Anti-pattern of all-at-once migration — each page is one independent commit.
**Research flag:** Standard patterns — low complexity, no additional research needed.

### Phase 3: Phase Workstation Pages (Laser, Piega, Saldatura)
**Rationale:** These are the highest business-criticality pages — operators use them continuously on the factory floor. They share a near-identical structure (same PHASE constant, same partial-complete modal pattern), so migrating laser first creates a template for piega and saldatura. The auto-refresh conflict pitfall must be resolved here before search is added. Touch target compliance is the most impactful change for operator safety on these pages.
**Delivers:** Three workstation pages migrated to design system. Search/filter UI above order lists. Phase-accent ambient theming formalized (`body[data-page]`). All interactive elements at 48px+ minimum. Auto-refresh refactored to fetch/render separation so filter state survives refresh cycles. Expanded panel state preserved across refresh cycles.
**Addresses:** FEATURES: global search in sticky nav, touch targets 48px, phase-accent theming, filter state UI, empty states, progress bars with text labels, color-blind accessible status icons. PITFALLS: auto-refresh wipes filter state (critical), expanded panel lost on refresh, touch targets too small (critical for gloved operators).
**Avoids:** Adding search before separating fetch from render — the refactor must happen first within this phase.
**Research flag:** Standard patterns for CSS/JS work, but physical tablet verification is required post-implementation. If the team does not have access to an Android industrial tablet, Chrome DevTools touch simulation at 48px pointer is the fallback verification method.

### Phase 4: Dashboard Redesign
**Rationale:** The dashboard is saved for last because it is the most complex page (calendar grid rendering, Kanban multi-column layout, most unique page-specific CSS) and benefits from all shared CSS being stable and battle-tested on the other pages. The KPI row, delivery urgency coloring, and auto-refresh indicator are P1 features. The mixed panoramic dashboard (unified view) is P2 and should be assessed after the simpler KPI row is validated with real operators.
**Delivers:** Dashboard with KPI hero row (ordini attivi, scadenze oggi, scadenze settimana, fasi in corso), delivery deadline urgency coloring (overdue=red, today=amber), sticky navbar with search input, auto-refresh indicator with manual refresh button, removal of welcome.html landing page (Flask `GET /` redirects to `/dashboard`), responsive layout for PC and tablet.
**Addresses:** FEATURES: KPI row (P1), delivery urgency (P1), direct dashboard landing (P1), remove welcome page (P1), auto-refresh indicator (P1), responsive layout (P1), mixed panoramic dashboard (P2 — attempt after P1 features are stable). PITFALLS: modal overflow on tablet (verify calendar/detail modals at 768px), navbar height variable propagated via `--navbar-height` CSS variable.
**Avoids:** Implementing the mixed panoramic view before validating the simpler KPI row with real usage — validate incrementally.
**Research flag:** Mixed panoramic dashboard (P2) may need a short design spike to define the information architecture before implementation. The compact week-view calendar strip (P3) is a distinct widget that requires vanilla JS calendar logic research if attempted.

### Phase Ordering Rationale

- Phase 1 before everything: `design.css` and `shared.js` must exist before any page links them. Font self-hosting resolves the highest-severity pitfall at the lowest implementation cost.
- Phase 2 before Phase 3: Archive and ordini_estratti are low-risk validation pages. Any CSS cascade problem discovered here can be fixed before it affects the production-critical phase workstation pages.
- Phase 3 before Phase 4: Phase workstation pages (laser/piega/saldatura) are structurally simpler than the dashboard and must be stable before the dashboard redesign begins, because the dashboard's KPI row consumes data from the same API endpoints in the same patterns.
- Dashboard last: Most complex page-specific CSS (calendar, Kanban), highest risk of page-specific layout complexity conflicting with shared CSS. Benefits from all shared rules being proven stable.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (Dashboard) — mixed panoramic dashboard feature:** The information architecture for combining KPI row + active phase cards + urgency highlights in a single non-Kanban view is not a standard pattern and requires a design spike to define the layout grid and data aggregation approach before implementation.
- **Phase 4 (Dashboard) — compact week-view calendar strip:** The existing calendar is a month-view widget. Redesigning to a week-strip format requires separate vanilla JS calendar logic research if this P3 feature is attempted.
- **Phase 3 (Workstation pages) — physical tablet verification:** Chrome DevTools touch simulation is a proxy; real verification of 48px touch targets and glassmorphism performance on a low-end Android industrial tablet is needed if available.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Creating a shared CSS file with CSS `@layer` and self-hosted WOFF2 fonts is thoroughly documented. All browser compatibility confirmed. No research needed.
- **Phase 2:** Archive/ordini_estratti migration is CSS extraction and linking — well-understood pattern.
- **Phase 3:** The auto-refresh/filter separation pattern is documented in PITFALLS.md with code examples. CSS migration follows the established Phase 2 template.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Verified via MDN, caniuse (97%+ browser coverage confirmed for all recommended CSS features), fontsource.org for Inter self-hosting. Flask static file serving verified by reading `app/backend/app.py` line 47–50 directly. No speculative choices. |
| Features | HIGH (industrial HMI patterns), MEDIUM (specific filter/search UX patterns) | Industrial touch targets, KPI dashboard layout, and traffic-light status systems are validated by ISO 9241-110, Tulip.co, and Dataparc research. Specific filter chip interaction patterns are documented by enterprise UX research but are less rigorously validated for this exact context. |
| Architecture | HIGH | Component responsibilities and data flows were validated against the actual codebase — all 7 HTML files examined, `app.py` static routes verified. The fetch/render separation pattern is established JavaScript architecture. No theoretical elements. |
| Pitfalls | HIGH (codebase-verified), MEDIUM (recovery cost estimates) | All pitfalls were identified through direct codebase analysis (e.g., 73 uses of `backdrop-filter: blur()` counted in laser.html, Google Fonts links confirmed in all 7 pages, `expandedIds` pattern confirmed in ordini_estratti.html). Recovery cost estimates are informed estimates, not measured benchmarks. |

**Overall confidence:** HIGH

### Gaps to Address

- **Operator validation of filter chip UX:** The additive filter chips / removable pill pattern is P2. Whether factory operators find this more intuitive than simple dropdowns has not been validated with actual users. Recommend implementing simple dropdown filters first (P1), then upgrading to pills after at least one week of real-world use.
- **`backdrop-filter: blur()` on target tablets:** PITFALLS.md notes that some Android WebView versions have partial/no backdrop-filter support. The specific Android version of the factory tablets is not known. If the factory uses older Android 8/9 tablets, the glassmorphism blur effect may render as a plain dark surface — which is acceptable as a fallback, but must be verified before deployment.
- **Navbar HTML duplication remains after redesign:** The ARCHITECTURE.md notes that nav HTML is still duplicated across 6 pages even after CSS centralization. A `fetch()` nav fragment approach is possible but was excluded from this milestone scope. This is a known maintenance debt that will remain post-redesign.
- **Mixed panoramic dashboard layout:** The specific grid layout for the unified KPI + phase cards + scadenze view is not defined by research — it requires a design decision during Phase 4 planning. The research confirms this is the right direction (industrial HMI "summary first" pattern) but does not prescribe the exact grid structure.

## Sources

### Primary (HIGH confidence)
- `app/frontend/*.html` (all 7 files) — direct codebase analysis: `:root` token duplication, Google Fonts links, auto-refresh patterns, `backdrop-filter` usage counts
- `app/backend/app.py` (lines 47–50) — confirmed Flask `/<path:filename>` catch-all route serves all `frontend/` files; `static_folder=None`
- MDN Web Docs: CSS `@layer`, Container Queries, `:has()`, `@font-face font-display`, IntersectionObserver API
- caniuse.com: CSS `@layer` (97%+ global), CSS Subgrid (97%+ global), CSS `:has()` (Baseline Widely Available)
- WCAG 2.5.8: 44×44px touch target minimum (official W3C spec)
- WebAIM Contrast Checker: contrast ratio calculations for current color tokens
- ISO 9241-110 (via Aufait UX): 15mm minimum touch target for industrial HMI

### Secondary (MEDIUM confidence)
- Tulip.co: 6 Manufacturing Dashboards for Visualizing Production — KPI hero row pattern
- Dataparc: Building Effective Manufacturing KPI Dashboards — operator vs. supervisor information density
- Pencil & Paper: Enterprise Filtering UX Patterns — additive filter chips / removable lozenges pattern
- BrowserStack: Responsive Breakpoints 2025 — 1024px tablet landscape validation
- CSS-Tricks: CSS Cascade Layers Guide — design system layering architecture
- Smashing Magazine: Integrating CSS Cascade Layers To An Existing Project — migration specificity strategy
- Coral Nodes / GitHub Workbox issue #1563: Google Fonts 30-second CDN timeout on offline/LAN environments confirmed

### Tertiary (LOW confidence)
- Recovery cost estimates (minutes/hours per pitfall) — informed estimates based on developer experience, not measured benchmarks; validate during retrospectives
- Factory tablet Android version — unknown; backup verification with Chrome DevTools touch simulation if physical testing is not available

---
*Research completed: 2026-02-19*
*Ready for roadmap: yes*

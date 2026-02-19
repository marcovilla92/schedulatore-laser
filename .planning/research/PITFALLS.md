# Pitfalls Research

**Domain:** Production scheduling app UI redesign — CSS design system migration, responsive layout, manufacturing UX
**Researched:** 2026-02-19
**Confidence:** HIGH (codebase-verified + multiple sources)

---

## Critical Pitfalls

### Pitfall 1: Auto-Refresh Wipes Search/Filter State on Every Cycle

**What goes wrong:**
All 5 phase pages use `setInterval(loadOrders, 5000)` or `setInterval(loadOrders, 10000)`. When search/filter inputs are added, the refresh callback calls `loadOrders()` which rebuilds the entire DOM — destroying the user's current search string, active filters, and scroll position. On a 5-second interval, operators on the laser or piega page lose their filter every 5 seconds, making search unusable.

**Why it happens:**
The refresh was added before search/filter existed. It calls the same full-reload function that also runs on page load. When filters are layered on top, nobody updates the refresh callback to re-apply the current filter state after DOM rebuild.

**How to avoid:**
Separate data-fetching from rendering. The fetch callback should store results in a module-level `let allOrders = []` variable, then call a separate `renderOrders(allOrders)` function that respects the current filter state. The auto-refresh only updates `allOrders` and triggers `renderOrders()`. The filter input reads from `allOrders` and produces a filtered view — the interval never touches filter state.

```javascript
// Pattern to enforce
let allOrders = [];
let currentFilter = '';

async function fetchOrders() {
    const response = await fetch(`${API_URL}/phase/${PHASE}/orders`);
    allOrders = await response.json();
    renderOrders(filterOrders(allOrders, currentFilter));
}

function filterOrders(orders, query) {
    if (!query) return orders;
    return orders.filter(o => /* search logic */);
}

setInterval(fetchOrders, 5000);
```

**Warning signs:**
- Typing in the search box, waiting 5–10 seconds, and seeing the input clear or results reset
- Filter state being lost after any user action that triggers a full `loadOrders()` call (e.g., marking an article complete)

**Phase to address:** Phase building search/filter on any page with an auto-refresh cycle

---

### Pitfall 2: Expanded Panel / Scroll Position Lost on Refresh

**What goes wrong:**
`ordini_estratti.html` already implements expanded panel preservation (`expandedIds` saved before DOM rebuild, restored after). Other pages do not. When the UI redesign adds collapsible sections, tabbed panels, or modal-adjacent state to laser/piega/saldatura pages, the auto-refresh at 5 seconds will collapse everything the operator opened mid-task.

**Why it happens:**
The preservation pattern exists in one file but is not a shared convention. During redesign, new UI state (which tab is open, which card is expanded, scroll position within a card list) will be added without implementing save/restore because the original pages never needed it.

**How to avoid:**
Before adding any new collapsible UI to a page that auto-refreshes, first implement the save/restore guard. Capture all stateful DOM identifiers before `loadOrders()` rebuilds, restore after. Scroll position must also be captured: `const scrollY = window.scrollY` before render, `window.scrollTo(0, scrollY)` after.

**Warning signs:**
- Expanded order cards snap closed after the 5-second tick
- A modal opened by the operator closes spontaneously
- The page scrolls to top during normal use

**Phase to address:** Any page with new collapsible/interactive UI elements plus existing auto-refresh

---

### Pitfall 3: Shared CSS File Breaks Page-Specific CSS Variable Overrides

**What goes wrong:**
Each page currently redefines `:root` variables in its `<style>` block. Laser page sets `--border-hover: rgba(255, 71, 87, 0.3)` (red). Piega sets `--border-hover: rgba(255, 165, 2, 0.3)` (amber). Dashboard sets `--border-hover: rgba(0, 212, 255, 0.3)` (cyan). These per-page accent color variants make each workstation visually distinct. When a shared CSS file defines these same variables in `:root`, the shared file wins because it is external and loaded before the inline `<style>` block — but only if the inline block does not also define them. If the redesign moves common rules to shared CSS while also keeping per-page accent overrides in inline `<style>`, the cascade works correctly. If someone consolidates the per-page variables into the shared file, all pages become the same accent color.

**Why it happens:**
The natural instinct when migrating to shared CSS is "remove duplicates." The per-page `:root` blocks look like duplicates but are actually intentional per-page theming. A developer who does not read all 7 pages carefully will merge them into one canonical `:root` and lose the visual distinction between workstations.

**How to avoid:**
In the shared CSS file, define only the globally constant values (font-family, bg colors, text colors, radius, transition). Explicitly leave `--border-hover`, `--accent-primary` (per-page accent), and the `body::before` gradient as per-page inline `<style>` values. Document this split in a comment at the top of the shared file: `/* Per-page accent variables are intentionally NOT here — see each page's <style> block */`.

**Warning signs:**
- All phase pages look identical (all cyan or all amber)
- Laser operator cannot distinguish their page from Piega by color
- `--border-hover` is defined once in shared CSS and nowhere in individual pages

**Phase to address:** Phase that creates the shared CSS design system / design tokens

---

### Pitfall 4: Google Fonts CDN Timeout on LAN-Only Deployment

**What goes wrong:**
All 7 pages load Inter from `fonts.googleapis.com`. The factory LAN has no internet access during production hours (or connectivity is intermittent). When the CDN is unreachable, the browser waits up to 30 seconds before falling back to the system font stack. This causes every page load to stall for 30 seconds. With 5-second auto-refresh on phase pages, operators see a frozen/blank page repeatedly.

**Why it happens:**
The current pages have a reasonable fallback font stack (`'Inter', 'Segoe UI', system-ui`), but `<link rel="preconnect" href="https://fonts.googleapis.com">` causes the browser to attempt the CDN connection before rendering. The `font-display: swap` is not set by default in Google's served CSS, meaning the browser will block rendering for the timeout period.

**How to avoid:**
Self-host Inter font files in `app/frontend/fonts/` and serve them via Flask. Generate the `@font-face` declarations pointing to local paths. This is a one-time download of ~150KB of WOFF2 files. Remove all `fonts.googleapis.com` and `fonts.gstatic.com` references from all 7 pages. The shared CSS file becomes the single place for `@font-face` declarations.

```css
/* In shared design.css */
@font-face {
    font-family: 'Inter';
    src: url('/fonts/inter-variable.woff2') format('woff2');
    font-display: swap;
    font-weight: 100 900;
}
```

**Warning signs:**
- Page load feels sluggish in the factory even though the server is local
- Pages briefly show system fonts before Inter loads
- Network tab shows requests to `fonts.googleapis.com` with long wait times

**Phase to address:** Phase that creates the shared CSS file (this is the perfect moment to self-host fonts)

---

### Pitfall 5: Touch Target Size Too Small for Gloved Operators

**What goes wrong:**
The current UI has many small interactive elements: the "expand" icon on order rows (~20px), checkbox items in modals (~16px padding), close buttons (36x36px with 1px border), and status badge buttons. Factory workers at the laser and piega stations often wear thin nitrile or leather gloves. A 36x36px touch target requires precise touch that gloves prevent. Misregistered taps trigger wrong orders to start/complete, causing production errors.

**Why it happens:**
The UI was designed on a desktop with a mouse cursor. Mouse precision is ~1px; gloved finger precision is ~15–20mm. The minimum touch target for gloved industrial use is 44x44px (Apple HIG) to 56x56px (industrial HMI standards). The glassmorphism design prioritizes visual elegance over touch ergonomics.

**How to avoid:**
On phase workstation pages (laser.html, piega.html, saldatura.html) specifically, all interactive elements must meet 48x48px minimum. The "Avvia" and "Completa" action buttons are critical path — target 56x64px with generous margin. Checkboxes in the completion modal must use a label-wrapping pattern so the entire row is tappable, not just the 16px checkbox. Verify all touch targets using a physical tablet (or at minimum Chrome DevTools with touch simulation at 48px pointer).

```css
/* Phase page minimum: action buttons */
.btn-avvia, .btn-complete {
    min-height: 52px;
    min-width: 120px;
    padding: 14px 24px;
    touch-action: manipulation; /* removes 300ms tap delay */
}

/* Checkbox rows: full-row tap target */
.modal-checkbox-item {
    min-height: 48px;
    padding: 12px 16px;
    cursor: pointer;
}
.modal-checkbox-item label {
    width: 100%;
    cursor: pointer;
}
```

**Warning signs:**
- Needing to tap twice to register a touch
- Wrong order getting started because a nearby button was hit
- Operators complaining they need to take gloves off to use the screen

**Phase to address:** Phase redesigning phase workstation pages (laser, piega, saldatura)

---

### Pitfall 6: Glassmorphism Contrast Failure on Active Status Text

**What goes wrong:**
The current design uses semi-transparent card backgrounds (`rgba(255,255,255,0.03)`) with text color `#e6e6e6` on background `#0a0a0f`. The computed contrast of `#e6e6e6` on `#0a0a0f` is approximately 16:1 — well above WCAG AA. However, secondary text (`--text-secondary: #6b7b8d`) on the same dark background is approximately 3.8:1, failing WCAG AA (4.5:1) for normal-size text. The `--text-muted: #4a5568` color is approximately 2.3:1 — a hard failure. Factory lighting (bright overhead fluorescent, reflections on tablet screens) makes low-contrast text even harder to read. Status labels like "IN LAVORAZIONE" in muted tones are the exact values operators need to see at a glance from 50cm away.

**Why it happens:**
The contrast values were chosen for aesthetic harmony in a dark room on a calibrated monitor. Factory environments have controlled brightness tablets (often <300 nit) and ambient light washing out the screen. Glassmorphism's translucent panels further reduce effective contrast because the blurred background content shifts the apparent background luminance unpredictably.

**How to avoid:**
Run every text/background combination through WCAG contrast checker before finalizing. Enforce these minimums for factory pages specifically:
- Body text: 7:1 (WCAG AAA) — not 4.5:1 — because of ambient light degradation
- Secondary text: minimum 4.5:1 — replace `#6b7b8d` with `#8a9ab0` or similar
- Status indicators: use both color AND a shape/icon, never color alone
- Muted text: use sparingly, never for actionable or status information

**Warning signs:**
- Secondary text colors (`#6b7b8d`, `#4a5568`) used for status labels
- Text contrast below 4.5:1 in DevTools accessibility audit
- Status visible in the office but operators can't read it at the machine

**Phase to address:** Design token phase (define contrast-validated color scale) and each page redesign phase

---

### Pitfall 7: CSS Load Order Race — Shared File vs. Inline Style

**What goes wrong:**
When the shared CSS file is added via `<link rel="stylesheet" href="/design.css">` in `<head>`, it loads asynchronously. The inline `<style>` block that follows it in the HTML is parsed synchronously. If a developer relies on the inline block overriding shared rules, this works correctly in theory (inline `<style>` specificity beats external when they share same selector). But if a developer adds page-specific rules to the shared file (or leaves base resets in inline blocks), conflicts become non-deterministic on slow LAN file serving.

More concretely: if `* { margin: 0; padding: 0; box-sizing: border-box; }` exists in both the shared CSS and every inline `<style>` block, it causes double-parse with no harm. But if a shared file defines `.btn { padding: 8px 16px; }` and a page redefines `.btn { padding: 12px 20px; }` inline, the inline wins — but only if the inline selector is equal-or-higher specificity. Adding one class or ID selector anywhere in the chain can flip the winner unexpectedly.

**Why it happens:**
CSS specificity during migration is managed by developers mentally tracking which file "owns" which rule. With 7 pages, 1 shared file, and no build tool, there is no automated check. Conflicts stay invisible until a specific page breaks.

**How to avoid:**
Establish a strict ownership rule: the shared CSS file owns layout primitives and reset only. Every component-level rule (`.order-card`, `.btn-avvia`, `.status-badge`) lives in page-level inline `<style>` blocks until or unless fully standardized. Do not put any component rules in the shared file until the component has been validated across all pages that use it. Use browser DevTools "Computed" tab to verify which file wins each property after migration, not just visual inspection.

**Warning signs:**
- A button looks correct on dashboard but different on piega
- Padding or sizing changes unexpectedly on one page after editing shared CSS
- Using `!important` to "fix" a specificity conflict (this masks the real issue)

**Phase to address:** Shared CSS creation phase and any page that imports it for the first time

---

### Pitfall 8: Responsive Layout Breaks Modals and Fixed Positioning

**What goes wrong:**
The confirmation modal (used on laser, piega, saldatura) uses `position: fixed`, `display: flex`, `align-items: flex-start`, `padding-top: 5vh`. On a tablet in landscape mode (1024x768), this works. In portrait mode (768x1024) the modal content at `max-width: 800px; width: 90%` becomes 691px — fine. But on a smaller tablet (800x600 landscape) or at high browser zoom level, the modal overflows beyond the viewport, and the `overflow-y: auto` on `modal-content` causes a scrollable element inside a fixed container — the inner scrollbar appears but touching outside the scroll area dismisses the modal. Operators lose work in progress.

Also: the navbar is `height: 64px; position: fixed`. Adding responsive breakpoints that change navbar to a hamburger menu or multi-row layout will shift the `padding-top: 68px` applied to `main` on every page. If the shared CSS changes navbar height at any breakpoint without updating the matching `padding-top`, the top of content will be hidden under the navbar.

**Why it happens:**
Fixed positioning is viewport-relative. When the viewport changes (tablet rotation, zoom), fixed-height elements like navbars and modals don't adapt. The existing pages were designed for one screen size (1920x1080 desktop) and one usage context (mouse).

**How to avoid:**
For modals: switch from `padding-top: 5vh` to `align-items: center`, add `margin: 16px` to modal-content, and use `max-height: calc(100vh - 32px)` instead of `85vh`. Test all modals at 768px wide, 1024px wide, and at 150% browser zoom.

For navbar: define `--navbar-height: 64px` as a CSS variable in `:root`. Use `padding-top: var(--navbar-height)` everywhere. If the navbar height changes at any breakpoint, update only the variable.

**Warning signs:**
- Modals partially hidden under the navbar on a tablet
- Scroll inside a modal is unresponsive to touch
- Page content overlaps with navbar after adding responsive CSS

**Phase to address:** Responsive layout phase for any page with modals or fixed-position elements

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Copy-paste CSS variables to each page inline | No shared file needed, no load order issues | 7x maintenance cost, drift between pages, color inconsistencies | Never — use a shared file for constants |
| `!important` to force shared CSS overrides | Quickly fixes a specificity conflict | Creates a specificity war, unmaintainable, hides structural problems | Never during migration |
| Client-side filter only (no URL persistence) | Simple to implement | Filter lost on refresh, operators must re-enter after every 5s data reload | Acceptable for MVP if filter state is preserved across refresh cycles in JS |
| Self-closing Google Fonts link left in place | Less migration work | 30-second page stall when LAN has no internet; every page load degrades | Never — self-host fonts for any offline/LAN deployment |
| Adding CSS to shared file before validating on all 7 pages | Faster migration pace | One-off exception on one page becomes permanent `!important` hack | Never — validate each rule across all consumers first |
| Pixel-fixed widths in redesigned layout | Simpler to write | Breaks on tablet rotation or 150% zoom | Never on phase workstation pages; acceptable on non-operator pages (archive) |

---

## Integration Gotchas

Common mistakes when connecting shared CSS to existing self-contained pages.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Adding `<link href="/design.css">` | Adding it after the inline `<style>` block (reversed cascade) | Always add shared CSS link in `<head>` before the page's inline `<style>` block |
| Self-hosting Inter font | Forgetting to add Flask route for `/fonts/` directory | Add `app.static_folder` or explicit route: `@app.route('/fonts/<path:filename>')` |
| Shared CSS + per-page accent colors | Consolidating all `:root` variables into shared CSS, losing per-page theming | Keep common tokens in shared CSS; keep per-page accent variables in each page's inline `:root` |
| Auto-refresh + new filter UI | Filter input resets when refresh fires `loadOrders()` | Refactor `loadOrders` to only fetch; have a separate `renderOrders(filter)` that the interval calls |
| Touch target expansion | Increasing button size breaks adjacent layout (card overflow, nav wrapping) | Increase padding, not width; test the full card layout after every touch-size change |
| `backdrop-filter: blur()` on tablets | Some tablets (Android WebView) have partial or no `backdrop-filter` support | Wrap blur in `@supports (backdrop-filter: blur(1px))` with a solid-color fallback |

---

## Performance Traps

Patterns that work at small scale but fail as data grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Client-side filter on full orders list | Perceptible lag on keypress as order count grows | Debounce the filter input (150ms); no server-call needed for small datasets | Beyond 500 orders visible at once (unlikely in this app) |
| `backdrop-filter: blur(24px)` on every card | GPU overdraw causes jank during scroll on low-end tablets | Reduce blur radius (8–12px sufficient), limit to navbar and modals only | Any tablet GPU below integrated Intel |
| Rebuilding entire DOM on each auto-refresh | Flash of unstyled content, scroll reset, janky animation reset | Save expanded IDs + scroll position before rebuild, restore after (pattern already in ordini_estratti.html) | Every refresh on every page — already affects users now |
| 73 uses of `backdrop-filter: blur()` in laser.html alone | GPU-saturated tablet, battery drain | Audit and consolidate — most card-level blurs can be replaced with semi-transparent solid colors | Any tablet that isn't high-end |

---

## UX Pitfalls

Common user experience mistakes specific to factory operator interfaces.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Confirmation dialogs requiring precise tap on small "X" button | Operators accidentally dismiss modal they worked to fill | Make dismiss buttons 48x48px minimum; require explicit "Annulla" button tap, not outside-click-to-dismiss on critical modals |
| Search/filter that hides orders not matching query | Operator believes an order doesn't exist; skips it | Show "0 risultati per [query]" with clear-filter button; never silently show empty state |
| Status colors alone (no text/icon) to convey order state | Operators with any color vision deficiency miss status changes | Always pair color with a text label AND an icon shape |
| Information density: showing all article details at all times | Cognitive overload — operator can't find the one thing they need | Progressive disclosure: show order header only by default; expand for articles; expand articles for phase details |
| Auto-refresh with visible flash/rebuild animation | Operators think something broke; anxiety in production environment | The existing flash-prevention CSS (already resolved in recent commits) must survive the redesign |
| Aggressive use of `transition: all 0.3s` on every element | Touch feels laggy; operators doubt whether tap registered | Use `transition: none` for elements that toggle on tap; keep transitions only for decorative state changes |

---

## "Looks Done But Isn't" Checklist

Things that appear complete during development but are broken in the factory environment.

- [ ] **Search/filter on auto-refresh pages:** Filter state survives a full `loadOrders()` cycle — verify by: type a search query, wait 10 seconds, confirm results still filtered
- [ ] **Google Fonts removed:** All 7 pages load Inter from local `/fonts/` — verify by: disconnect the server from internet, reload all pages, confirm Inter renders correctly
- [ ] **Per-page accent colors preserved:** Laser page still shows red/accent-red hover; Piega shows amber; Dashboard shows cyan — verify by: inspect `--border-hover` computed value on each page after shared CSS is introduced
- [ ] **Expanded panel state preserved on refresh:** Open an order panel on laser.html, wait 5 seconds, confirm panel stays open — verify on all 3 phase pages
- [ ] **Touch targets meet 48px minimum:** Every button, checkbox-row, and close icon on phase workstation pages is at least 48x48px — verify by: Chrome DevTools > Rendering > Show touch targets; measure in the UI
- [ ] **WCAG contrast on secondary text:** `--text-secondary` color (#6b7b8d or replacement) on page background passes 4.5:1 — verify by: WebAIM Contrast Checker with each text/background pair
- [ ] **Modal usable at tablet portrait size:** Open each modal at 768x1024 viewport — confirm it doesn't overflow, inner scroll works, dismiss button is reachable without scrolling
- [ ] **Navbar height variable propagated:** Changing `--navbar-height` in shared CSS updates `padding-top` on main content on all pages — verify by temporarily setting to 80px and checking all 7 pages
- [ ] **No `!important` introduced during migration:** `grep -r '!important' app/frontend/` returns zero results in newly added CSS
- [ ] **Auto-refresh flash prevention survives redesign:** The no-flash pattern (already fixed in recent commits) is preserved after CSS migration — verify by watching any phase page for 30 seconds without interacting

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Filter state breaks on refresh | LOW | Refactor `loadOrders` into fetch + render; add `currentFilter` module variable; takes ~1 hour per page |
| Per-page accent colors merged into shared CSS | LOW-MEDIUM | Restore per-page `:root` accent overrides from git history; add comment explaining intent; takes ~30 minutes |
| Google Fonts timeout discovered in production | MEDIUM | Self-host fonts immediately: download Inter WOFF2, add to `app/frontend/fonts/`, update all 7 pages; takes ~2 hours |
| Touch targets too small, discovered during factory testing | MEDIUM | Targeted CSS increase to padding/min-height on action buttons and checkbox rows; re-test; takes ~1 day per page |
| Contrast failures discovered post-deployment | MEDIUM | Update `--text-secondary` and `--text-muted` values in shared CSS; verify cascade updates all pages; takes ~3 hours |
| Shared CSS specificity war with inline `<style>` | HIGH | Audit all 7 pages for conflicting selectors; establish clear file ownership rules; may require restructuring how component rules are split; takes 1–2 days |
| Modal overflow on tablet discovered post-deployment | MEDIUM | Update modal CSS to use `align-items: center` + `margin` approach; test on physical device; takes ~4 hours |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Auto-refresh wipes filter state | Phase: Search/Filter implementation (any page) | Manually type query, wait for 2 refresh cycles, verify filter persists |
| Expanded panel / scroll lost on refresh | Phase: Any page redesign that adds collapsible UI | Open 3 panels, wait 10 seconds, verify all still open |
| Shared CSS breaks per-page accent colors | Phase: Shared CSS design system creation | Load all 7 pages; verify distinct accent color per workstation page |
| Google Fonts CDN timeout | Phase: Shared CSS creation (font self-hosting happens here) | Disconnect from internet, reload all pages; verify Inter renders |
| Touch targets too small | Phase: Phase workstation page redesign (laser, piega, saldatura) | DevTools touch target overlay; 48px minimum on all interactive elements |
| Glassmorphism contrast failure | Phase: Design token definition (before any page redesign) | WebAIM contrast check; every text/bg pair passes 4.5:1 |
| CSS load order race | Phase: Shared CSS creation | Computed styles in DevTools match expected file; no `!important` in git diff |
| Responsive layout breaks modals/navbar | Phase: Responsive layout for tablet | Test all modals at 768px and 1024px viewport widths at 100% and 150% zoom |

---

## Sources

- Codebase analysis: `app/frontend/*.html` — all 7 pages examined for current CSS variable usage, auto-refresh patterns, glassmorphism counts, Google Fonts links
- [Integrating CSS Cascade Layers To An Existing Project — Smashing Magazine](https://smashingmagazine.com/2025/09/integrating-css-cascade-layers-existing-project/) — specificity migration strategy (MEDIUM confidence)
- [How to Redesign a Legacy UI Without Losing Users — XB Software](https://xbsoftware.com/blog/legacy-app-ui-redesign-mistakes/) — muscle memory and feature discoverability (MEDIUM confidence)
- [Dark Mode Accessibility — DubBot](https://dubbot.com/dubblog/2023/dark-mode-a11y.html) — WCAG contrast requirements for dark interfaces (HIGH confidence)
- [Glassmorphism — Interaction Design Foundation](https://www.interaction-design.org/literature/topics/glassmorphism) — glassmorphism accessibility challenges (MEDIUM confidence)
- [Touchscreen Requirements for Industrial HMI — Design World Online](https://www.designworldonline.com/touchscreen-requirements-for-human-machine-interface-in-industrial-automation/) — gloved touch target standards (MEDIUM confidence)
- [HMI Design Best Practices — AufaitUX](https://www.aufaitux.com/blog/hmi-design-best-practices/) — industrial operator UX (MEDIUM confidence)
- [Getting Past Dashboard Information Overload — XMPRO](https://xmpro.com/getting-past-dashboard-information-overload-reducing-cognitive-strain-with-augmented-decision-intelligence/) — cognitive load in manufacturing dashboards (MEDIUM confidence)
- [How to Host Google Fonts Locally — Coral Nodes](https://www.coralnodes.com/host-google-fonts-locally/) — self-hosting strategy for offline/LAN environments (HIGH confidence)
- [workbox-sw: Google fonts not rendering when fully offline — GitHub](https://github.com/GoogleChrome/workbox/issues/1563) — CDN font 30-second timeout behavior confirmed (HIGH confidence)
- [WCAG Contrast Checker — WebAIM](https://webaim.org/resources/contrastchecker/) — contrast ratio calculations (HIGH confidence)

---
*Pitfalls research for: UI/UX redesign of Schedulatore Laser production scheduling app*
*Researched: 2026-02-19*

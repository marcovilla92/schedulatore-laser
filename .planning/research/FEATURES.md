# Feature Research

**Domain:** Industrial production scheduling dashboard — UI/UX redesign of metal carpentry order management web app
**Researched:** 2026-02-19
**Confidence:** HIGH (industrial HMI patterns), MEDIUM (specific filter/search patterns), HIGH (touch/tablet UX)

---

## Context: What Already Exists

The backend is complete and frozen for this milestone. These are UI/UX features for a redesign, not new backend capabilities. The following already works:

- Dashboard with Kanban overview + delivery calendar
- Laser/piega/saldatura phase views with batch start/complete
- Per-article phase tracking with progress bars
- Ordini estratti page for PDF extraction and phase assignment
- Archive page, Welcome page (being removed)
- 30-second auto-refresh

The redesign must keep all existing functionality working while replacing the visual implementation.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the app must have for operators to consider the UI complete. Missing any of these = the UI feels broken or unprofessional, even if the backend works.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Shared design system (CSS tokens) | Currently every page has its own copy of `:root` variables — any inconsistency feels like bugs, not design | MEDIUM | Single `design-system.css` loaded on all pages via Flask static. Token layers: primitives → semantic → component |
| Persistent sticky navigation bar | All 7 pages already have navbars but inconsistently implemented. Users expect nav to stay visible while scrolling production lists | LOW | Already exists; needs unification into shared HTML fragment or at minimum consistent CSS |
| Status color consistency across pages | LASER (red/cyan), PIEGA (amber), SALDATURA (green) must be the same color on every page — Kanban card, phase badge, progress bar | LOW | Currently duplicated CSS; shared tokens solve this |
| Readable on bright workshop lighting | Office LCD monitors and workshop tablets have different ambient light. Current dark glassmorphism can wash out under factory lighting | MEDIUM | Increase contrast ratios. WCAG AA minimum (4.5:1 text). Avoid thin/light fonts. Test on high-brightness display |
| Touch targets min 44px tall for tablet operators | Gloved-hand operation requires minimum 44px interactive elements per accessibility standards (ISO 9241-110 recommends ~15mm / ~57px for industrial HMI) | LOW | Audit all buttons, checkboxes, nav links. Many current elements are 32-36px. Raise to 48px minimum for safety-critical actions |
| KPI summary row on dashboard | Industry standard: production dashboards open with a "hero row" of key numbers. Missing = operators can't get current state at a glance | MEDIUM | Ordini attivi, scadenze oggi, scadenze questa settimana, fasi in corso |
| Visual delivery deadline urgency (scadenze) | Orders due today or overdue must be visually distinguished from orders due next week. Color-coded urgency is expected in any scheduling tool | LOW | Three states: overdue (red), today (amber), upcoming (none/dim). Currently calendar shows this but cards don't |
| Direct dashboard landing (no welcome page) | Welcome/splash pages are rejected by experienced users in production environments. The dashboard IS the home | LOW | Remove welcome.html as landing. Flask route `/` redirects to `/dashboard` |
| Filter by phase status on phase pages | Operators at laser station only want to see LASER orders. Within that, they want In Progress vs Queued vs Completed. This is table stakes for phase views | MEDIUM | Already works via API; the UI needs visible filter chips/buttons above the list |
| Search by cliente or numero ordine | Any production tracking tool must let supervisors find a specific order without scrolling through 50 cards | MEDIUM | Text input in header bar, client-side filter against loaded orders. Backend already returns all data; no API change needed |
| Responsive layout: PC desktop + tablet | System runs on both office PCs (1920×1080+) and workshop tablets (768–1024px wide). Layout must adapt without breaking | MEDIUM | Two meaningful breakpoints: ≥1024px (desktop sidebar/multi-column), 768–1023px (tablet single-column compact). No mobile needed |
| Auto-refresh indicator | 30-second auto-refresh already exists. Users need to see WHEN data was last refreshed and when next refresh fires — otherwise they don't trust the data is current | LOW | Subtle "Aggiornato X secondi fa" timestamp + countdown ring or progress bar in header |
| Empty state messages | When a phase has zero orders (e.g., nothing queued for piega today) the current blank view looks broken. | LOW | Friendly Italian empty state: "Nessun ordine in questa fase" with icon |
| Legible progress bars per article | Existing progress bars are thin and hard to read on tablet. Must be taller (12px min) and show completion fraction as text (e.g., "3/5 articoli") | LOW | Purely CSS/HTML change |

### Differentiators (Competitive Advantage)

Features that would make this UI stand out from generic production tracking tools. These justify the redesign and improve daily operator experience.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Mixed panoramic dashboard (KPI + produzione + scadenze) | Instead of separate "stats" and "Kanban" sections, a unified view that shows KPI numbers, active phase cards, and deadline highlights on a single screen — operators see the whole plant state in one glance | HIGH | This is the flagship dashboard feature. Requires redesigning the information architecture: KPI row (top) → urgency highlights (middle) → active phase summary (bottom). Not a simple reskin |
| Persistent global search accessible from any page | A search bar in the sticky navbar that works on the current page's data without navigating. Operator at laser station can search for "Rossi" and see matching orders without leaving the laser view | HIGH | Client-side. On each page, the search filters the current page's visible cards/rows. No cross-page navigation needed. Requires consistent order card data structure across pages |
| Phase-accent ambient theming | Each workstation page (laser, piega, saldatura) has a phase-specific accent color for the ambient background gradient and active elements. Laser = red/warm, Piega = amber, Saldatura = green/blue. Immediately communicates "I'm at the laser station" | LOW | Purely CSS — already partially done but inconsistently. Formalizes into the design system as per-page theme modifier |
| Delivery deadline calendar integration in dashboard | A compact inline calendar (week view) highlighting delivery dates with order count badges. Supervisors can see at a glance which days are overloaded | HIGH | Requires a week-view calendar widget in vanilla JS. Already exists as month view; needs redesign to compact week strip |
| Additive filter chips with active count badge | Filters shown as removable pill badges (e.g., "[x] Cliente: Rossi" "[x] Scadenza: Oggi"). The filter bar shows active filter count in the nav. Clear one or all without reloading | MEDIUM | Pattern from enterprise filtering research. Additive lozenges pattern. Backed by URL query params for bookmarkability |
| Glassmorphism refined for industrial context | Current glassmorphism is too decorative (animations, blur effects). Refined version: sharper card borders, reduced blur radius, stronger surface contrast, industrial materials feel (steel/glass aesthetic) | MEDIUM | Reduce `body::before` animation. Increase card border opacity. Use `rgba(255,255,255,0.06-0.10)` for cards. Keep blur on nav only |
| Article-level completion inline on phase cards | On laser/piega/saldatura pages, show article checkboxes directly expanded on card hover (tablet: on tap). Currently requires expand then checkbox. Reduce taps for common action | MEDIUM | Inline expand pattern. Keep collapse as option for pages with 20+ orders |
| Color-blind accessible status indicators | Status colors (red/amber/green) supplemented by shape/icon: circle = in-progress, check = complete, clock = queued. Ensures operators with red-green color blindness can still read status | LOW | Add SVG icons alongside color. WCAG 1.4.1 compliance. Currently only color distinguishes states |

### Anti-Features (Commonly Requested, Often Problematic)

These look like good ideas but create problems in this specific context. Document them explicitly to prevent scope creep during implementation.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Light/bright theme toggle | "Workshop tablets might be in sunlight" | Doubles CSS maintenance burden. Inline CSS per page makes this extremely expensive. Dark theme WITH high contrast is the right answer for industrial use | Increase dark theme contrast ratios and brightness to meet workshop conditions without a second theme |
| Real-time WebSocket push updates | "30 seconds is too slow, I want instant updates" | Requires backend change (this milestone is UI-only). WebSocket adds server complexity, breaks current Flask-only architecture | Keep 30-second polling but make it visible. Add manual "Aggiorna ora" button for immediate refresh. Operators can trigger on demand |
| Full-text search with backend API | "Search should find orders by article name or note text" | Requires new API endpoint (backend frozen for this milestone). Client-side search over loaded data covers 95% of use cases | Client-side text filter over `cliente`, `numero_ordine`, and `id` fields already in loaded JSON. Flag backend search as v1.3 |
| Drag-and-drop order reordering / priority | "I want to drag orders to change priority" | No priority concept in current data model. Purely visual reordering with no persistence is misleading. Backend would need `sort_order` column | Phase sequence is already defined by workflow (LASER → PIEGA → SALDATURA). Date consegna IS the priority signal — sort by deadline |
| Infinite scroll / virtual list | "What if there are hundreds of orders?" | Current SQLite returns all orders in one API call. Implementing virtual scroll with 50+ orders currently visible per page is premature optimization. Typical use: 5–20 active orders at once | Pagination with "Mostra altri" load-more button if list exceeds 30 items. Simpler and sufficient |
| Per-user preferences / personalization | "Each operator wants different defaults" | No authentication system. No user identity. Implementing localStorage-based preferences risks confusion on shared tablets (one user changes, all users affected) | Design smart defaults: phase pages pre-filtered to their phase, dashboard shows all. Stateless = predictable on shared devices |
| Toast notifications / push alerts | "Notify me when an order moves to my phase" | No push infrastructure. Browser notifications require HTTPS + service worker (LAN HTTP). Frontend-only notification system that polls creates duplicate refresh logic | Order cards in each phase view are the notification system. Auto-refresh ensures operators see new assignments within 30 seconds |
| Animated charts / real-time graphs | "Show me a production throughput chart over time" | `processing_steps` table has timing data but analytics queries would need new API endpoints (backend frozen). Animated charts consume GPU on low-end shop-floor tablets | Static KPI numbers on dashboard. Charts deferred to v2 analytics module with dedicated backend endpoints |
| Welcome/splash page | "Brand first impression" | Research confirms splash pages are actively rejected in production environments. Operators need to see operational data immediately on every visit. Adds a mandatory navigation step | Remove entirely. Dashboard IS the landing page. Flask `GET /` redirects to `/dashboard` |

---

## Feature Dependencies

```
Shared Design System (design-system.css)
    └──required by──> All page redesigns
                          └──required by──> Global search (consistent card DOM structure)
                          └──required by──> Status color consistency
                          └──required by──> Touch target compliance

Global Search (sticky navbar search bar)
    └──requires──> Consistent order card data structure on each page
    └──enhances──> Filter chips (search + filter work together)

KPI Dashboard Row
    └──requires──> API already returns order counts and status — no backend change
    └──enhances──> Delivery deadline urgency visualization

Mixed Panoramic Dashboard
    └──requires──> KPI row
    └──requires──> Phase status cards (refactored from existing Kanban)
    └──requires──> Delivery urgency highlights
    └──requires──> Design system tokens (spacing, color, typography)

Filter Chips (additive lozenges)
    └──requires──> Shared filter UI component pattern
    └──enhances──> Global search (combined filtering)
    └──conflicts with──> Per-user preferences (filters must reset on page load — no persistence)

Phase-accent ambient theming
    └──requires──> Shared design system (extends base tokens with per-page modifier)
    └──no conflicts

Responsive layout (PC + tablet)
    └──requires──> All page HTML structure to support flex/grid reflow
    └──requires──> Touch target audit (44px+ interactive elements)
```

### Dependency Notes

- **Design system must be Phase 1** of implementation. Every other feature depends on shared tokens existing first.
- **Global search requires consistent DOM**: Every page that includes search must render order cards with the same data attributes (`data-cliente`, `data-ordine`, `data-status`) for the client-side filter to work.
- **Mixed panoramic dashboard is the hardest feature**: It requires rethinking the information architecture of the dashboard, not just restyling. Schedule it as its own implementation task after design system and individual page redesigns are stable.
- **Filter chips conflict with stateless design**: Filters must NOT persist across page loads (shared tablets). They should live in URL query params, which are stateless by default.

---

## MVP Definition

### Launch With (Redesign v1.2)

These are the minimum features that must ship for the UI/UX redesign milestone to be considered complete:

- [ ] `design-system.css` shared across all pages — CSS custom properties for colors, spacing, typography, radii, transitions
- [ ] Redirect: `GET /` lands on dashboard, welcome.html removed from navigation
- [ ] Dashboard: KPI row (ordini attivi, scadenze oggi, scadenze questa settimana, fasi in corso)
- [ ] Dashboard: Delivery deadline urgency coloring on order cards (overdue=red, today=amber)
- [ ] Sticky navbar with global search input (client-side filter on current page)
- [ ] All pages: touch targets minimum 48px for interactive elements
- [ ] All pages: status colors from shared tokens (no per-page color definitions)
- [ ] Laser/piega/saldatura: visible filter state (current phase pre-selected, removable)
- [ ] Responsive breakpoints: ≥1024px multi-column desktop, 768–1023px single-column tablet
- [ ] Auto-refresh indicator in nav ("Aggiornato X sec fa" + manual refresh button)
- [ ] Empty states: friendly Italian message when phase has no orders
- [ ] Progress bars: minimum 12px tall, show "N/M articoli" text label
- [ ] Color-blind accessible: status icons alongside status colors

### Add After Validation (v1.2.x)

- [ ] Additive filter chips as removable pills (requires testing that basic filters work first)
- [ ] Mixed panoramic dashboard (KPI + production + scadenze in unified layout) — complex, validate simpler KPI row first
- [ ] Inline article completion on phase cards (reduce taps — validate operator preference first)
- [ ] Compact week-view calendar strip on dashboard

### Future Consideration (v2+)

- [ ] Backend search API for full-text article/note search — requires new endpoint
- [ ] Analytics charts (throughput over time) — requires new API endpoints and data model
- [ ] Real-time WebSocket updates — requires backend architecture change
- [ ] Light theme variant — only if explicitly requested after v1.2 ships

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Shared CSS design system | HIGH | MEDIUM | P1 |
| Remove welcome page / direct dashboard landing | HIGH | LOW | P1 |
| KPI row on dashboard | HIGH | MEDIUM | P1 |
| Touch targets 48px minimum | HIGH | LOW | P1 |
| Delivery deadline urgency coloring | HIGH | LOW | P1 |
| Responsive PC + tablet layout | HIGH | MEDIUM | P1 |
| Global search in sticky nav | HIGH | MEDIUM | P1 |
| Status color consistency via tokens | HIGH | LOW | P1 |
| Auto-refresh indicator + manual refresh | MEDIUM | LOW | P1 |
| Empty states | MEDIUM | LOW | P1 |
| Phase-accent ambient theming | MEDIUM | LOW | P2 |
| Progress bars: taller + text label | MEDIUM | LOW | P2 |
| Color-blind accessible status icons | MEDIUM | LOW | P2 |
| Additive filter chips (removable pills) | MEDIUM | MEDIUM | P2 |
| Mixed panoramic dashboard (unified view) | HIGH | HIGH | P2 |
| Inline article expansion on phase cards | MEDIUM | MEDIUM | P2 |
| Compact week-view calendar strip | LOW | HIGH | P3 |

**Priority key:**
- P1: Must ship in v1.2 redesign milestone
- P2: Should ship in v1.2 if P1 is solid; defer to v1.2.x if time is tight
- P3: Nice to have, future consideration

---

## Manufacturing/Industrial UX Patterns (Research Findings)

### Pattern 1: Hero Section KPI Row (Summary First, Detail Later)

**What it is:** Top of every dashboard = large bold numbers for the most critical metrics. Everything else is detail.

**For this app:**
- "Ordini Attivi: 12" | "Scadenze Oggi: 3" | "Scadenze Settimana: 8" | "Laser in corso: 2"
- Each KPI card = label (small, muted) + value (large, bold, colored) + trend/context (small)

**Evidence:** Dataparc, Tulip, NN/G all confirm KPI cards must be in the "hero section" at top-left where eye naturally goes first.

### Pattern 2: Traffic Light Status System

**What it is:** Three-state color coding: GREEN = go/normal, AMBER = attention needed, RED = act now.

**For this app:**
- GREEN: ordine in lavorazione normale
- AMBER: scadenza oggi, in ritardo di meno di 1 giorno
- RED: scadenza passata (overdue), bloccato

**Evidence:** Tulip manufacturing dashboards, industrial HMI best practices consistently use this three-state system. Must be supplemented by icons (not color alone) for color blindness.

### Pattern 3: Contextual Filters Above Content

**What it is:** Filters live in a horizontal bar directly above the content they filter. Not in a sidebar on mobile/tablet. Applied filters shown as removable chips.

**For this app:** Phase pages (laser/piega/saldatura) show filter chips row: "[x] Solo in attesa" "[x] Acciaio inox". Clear individually or all at once.

**Evidence:** Pencilandpaper enterprise filtering research. Additive lozenges pattern validated for production systems.

### Pattern 4: 48px Minimum Touch Targets (Industrial HMI Standard)

**What it is:** ISO 9241-110 recommends ~15mm minimum touch targets. At typical screen DPI this is 57px. WCAG minimum is 44px. For gloved hands, err toward 48px minimum and 56px for safety-critical actions.

**For this app:** "Avvia fase" and "Completa articolo" buttons must be at minimum 48px tall. Checkboxes on article lists must use large click areas, not just the checkbox element itself.

**Evidence:** ISO 9241-110, Touch International, Aufait UX HMI guide, WCAG 2.1 criterion 2.5.5.

### Pattern 5: Consistent Button Placement (2–3 Tap Rule)

**What it is:** Critical actions must be reachable within 2-3 interactions from any screen. Navigation must be consistent across all screens so operators don't need to learn different layouts per page.

**For this app:** Current nav is consistent (already has this). The redesign must NOT change nav link order or position. Operators on the shop floor memorize button positions — changing them creates errors.

**Evidence:** Aufait UX HMI design guide, dataparc manufacturing dashboard report.

### Pattern 6: Audience-Specific Information Density

**What it is:** Operators need real-time, shift-based, action-oriented data. Supervisors need weekly trends and counts. Management needs monthly aggregates. One-size-fits-all dashboards serve no one well.

**For this app:**
- Phase pages (laser/piega/saldatura): only the orders queued for THAT phase, action buttons prominent
- Dashboard: panoramic view for supervisors — all phases visible, KPI numbers, deadline urgency
- The dashboard is NOT the same as the phase pages; they serve different users

**Evidence:** Dataparc, Tulip manufacturing dashboard research.

---

## Competitor Feature Analysis

| Feature | Generic ERP (e.g., NetSuite) | Tulip/FactoryOS | This App (target) |
|---------|----------------------------|-----------------|--------------------|
| Status colors | Three-color system | Three-color + icon | Three-color + icon (add icons) |
| Filter pattern | Sidebar panel | Horizontal filter bar | Horizontal filter chips above content |
| KPI display | Separate analytics page | Inline KPI cards | Hero row on dashboard |
| Touch optimization | Minimal (desktop-first) | Strong (tablet-first) | 48px targets, tablet-first |
| Search | Global search + backend | Page-scoped instant filter | Page-scoped client-side (instant, no backend) |
| Deadline visualization | Calendar module | Color-coded urgency on cards | Color-coded + calendar strip |
| Design system | Company design system | Proprietary | Single `design-system.css` (shared CSS tokens) |
| Refresh | Manual or event-driven | Real-time WebSocket | 30-sec polling + manual trigger |

---

## Sources

- Tulip.co: [6 Manufacturing Dashboards for Visualizing Production](https://tulip.co/blog/6-manufacturing-dashboards-for-visualizing-production/)
- Dataparc: [Building Effective Manufacturing KPI Dashboards](https://www.dataparc.com/blog/building-effective-manufacturing-kpi-dashboards-and-reports/)
- Pencil & Paper: [Enterprise Filtering UX Patterns](https://www.pencilandpaper.io/articles/ux-pattern-analysis-enterprise-filtering)
- Aufait UX: [HMI Design Best Practices](https://www.aufaitux.com/blog/hmi-design-best-practices/)
- Touch International: [Industrial Touchdisplay Designs](https://touchinternational.com/industrial-touchdisplay-designs/)
- Smashing Magazine: [Naming Best Practices for Design Tokens](https://www.smashingmagazine.com/2024/05/naming-best-practices/)
- NN/G: [Sticky Headers](https://www.nngroup.com/articles/sticky-headers/)
- Accessibility.digital.gov: [Touch Targets](https://accessibility.digital.gov/ux/touch-targets/)
- ISO 9241-110 (via Aufait UX): 15mm minimum touch target for industrial HMI
- LogRocket: [All Accessible Touch Target Sizes](https://blog.logrocket.com/ux-design/all-accessible-touch-target-sizes/)
- materialui.co: [Design Tokens & Theming: Scalable UI Systems in 2025](https://materialui.co/blog/design-tokens-and-theming-scalable-ui-2025)
- Penpot: [Developer's Guide to Design Tokens and CSS Variables](https://penpot.app/blog/the-developers-guide-to-design-tokens-and-css-variables/)
- Fuselab Creative: [UI/UX Design in Manufacturing & Warehousing](https://fuselabcreative.com/the-role-of-ui-ux-design-in-manufacturing-and-warehousing/)

---

*Feature research for: UI/UX redesign of production scheduling dashboard (carpenteria metallica)*
*Researched: 2026-02-19*
*Confidence: HIGH for industrial HMI/touch patterns, MEDIUM for specific filter implementation patterns, HIGH for design token architecture*

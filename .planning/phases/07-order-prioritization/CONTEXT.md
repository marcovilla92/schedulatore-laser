# Phase 07 — Order Prioritization for Laser Phase

**Date Created:** 2026-03-02
**Research:** manufacturing-prioritization-RESEARCH.md
**Status:** Planning Phase (ready for execution)

## User Vision

Manufacturing operators need to see which orders are most urgent at a glance. Currently, orders in laser.html appear in arbitrary order (likely API response order, which is not deadline-based). This creates inefficiency: operators might work on an order due in 10 days while another order is due tomorrow.

**Goal:** Implement Earliest Due Date (EDD) prioritization with visual urgency badges (3-tier system: green/yellow/red) so operators prioritize correctly without manual sorting.

## Scope: What's Included

### Implementation
- **EDD Algorithm**: Sort orders by `data_consegna` (delivery date) — earliest first
- **3-Tier Urgency Badges**:
  - Green: ≥7 days to deadline (safe)
  - Yellow: 3-7 days to deadline (moderate urgency)
  - Red: <3 days or overdue (critical)
- **Days-Remaining Display**: Show "N giorni", "Oggi", or "Scaduto" on each order
- **Client-Side Only**: No backend API changes. JavaScript calculation at render time.
- **Timezone-Safe**: Uses ISO 8601 date parsing (new Date() handles timezones correctly)
- **Extensible Pattern**: Same code duplicated to piega.html and saldatura.html

### Files Modified
1. `app/frontend/laser.html` — Primary implementation + reference
2. `app/frontend/piega.html` — Same pattern replicated
3. `app/frontend/saldatura.html` — Same pattern replicated

### Files NOT Modified
- No backend changes (app/backend/app.py, models.py, database.py)
- No database schema changes
- No API endpoint changes
- Existing orders continue to work as-is

## Research Findings (from RESEARCH.md)

**Manufacturing Best Practice:**
- EDD (Earliest Due Date) is industry-standard for job shops (like carpenteria metallica)
- EDD outperforms FIFO (First In First Out) when deadlines vary widely
- Studies show 15-30% improvement in on-time delivery rates with EDD
- Critical Ratio (more advanced) recommended for dynamic adjustment when orders slip

**For This Project:**
- EDD is sufficient for initial implementation (v1.0)
- Visual urgency badges (color + text) improve operator decision-making
- No external scheduling library needed (custom algorithm is lightweight)
- Client-side calculation is performant for <100 orders

## Technical Approach

### Algorithm: Earliest Due Date (EDD)
```
1. Parse each order's data_consegna (ISO 8601 DateTime)
2. Calculate days remaining = (data_consegna - today) / 86400000 ms
3. Sort ascending (earliest deadline first)
4. Assign urgency tier based on days remaining:
   - daysRemaining >= 7 → 'green'
   - 3 <= daysRemaining < 7 → 'yellow'
   - daysRemaining < 3 → 'red'
5. Display on card: badge color + text ("6 giorni", "Oggi", "Scaduto")
```

### Implementation Details
- **Utility Functions** (3):
  - `getDaysRemaining(dateString)` → number
  - `getUrgencyTier(daysRemaining)` → 'green'|'yellow'|'red'
  - `getUrgencyLabel(daysRemaining)` → "6 giorni"|"Oggi"|"Scaduto"
- **Sorting Function** (1):
  - `sortOrdersByEDD(orders)` → sorted array (immutable)
- **CSS Classes** (3):
  - `.urgency-badge.urgency-tier-green` — green styling
  - `.urgency-badge.urgency-tier-yellow` — amber/yellow styling
  - `.urgency-badge.urgency-tier-red` — red styling
  - `.urgency-indicator` — glowing dot (accessibility + visual distinction)

### Data Source
- Source: `order.data_consegna` (from `/api/phase/LASER/orders` response)
- Format: ISO 8601 DateTime (e.g., "2026-03-10T00:00:00")
- Type: Parsed via `new Date()` in JavaScript

### No API Changes
- GET /api/phase/{PHASE}/orders returns orders unsorted (as before)
- Sorting happens in frontend JavaScript during renderOrders()
- Backward compatible with existing orders and API

## Extensibility

### Future Enhancements (Out of Scope)
- **localStorage toggle**: Operator can switch between EDD and FIFO sorting preference (stored in browser)
- **Critical Ratio filter**: Show only urgent orders (< 3 days)
- **Dashboard metrics**: OTD (On-Time Delivery) percentage, average order age, critical orders count
- **Alerts**: Notify when order enters red zone (< 3 days)

### Replication Pattern
Same code can be added to all phase pages:
- laser.html (LASER phase) — **this plan**
- piega.html (PIEGA phase) — replicate from laser.html
- saldatura.html (SALDATURA phase) — replicate from laser.html
- dashboard.html (summary view) — optional, requires full order list

## Decisions

### Design Choices
1. **Client-Side Sorting**: Fastest for operators (instant), no server load. Trade-off: if orders change mid-session, page refresh needed (currently every 5 seconds).
2. **3-Tier System**: Simpler than 5-tier (green/yellow/orange/red/critical). Research shows 3 tiers sufficient for user decision-making.
3. **Color Coding**: Green/yellow/red is international manufacturing standard (ANSI, ISO 8601). Accessible to color-blind operators (color + text).
4. **EDD Algorithm**: Deterministic (same order every time), simple to implement, proven in manufacturing. No special library needed.
5. **Timezone-Safe**: ISO 8601 + new Date() handles all timezones automatically. No manual timezone logic needed.

### Architecture
- **No Backend Changes**: Reduces risk, no migration needed, API stable
- **Self-Contained HTML**: Each phase page has full logic (laser.html, piega.html, saldatura.html are independent)
- **Immutable Sorting**: slice().sort() doesn't mutate input (safer, no side effects)

## Definition of Done

Phase 07 complete when:
- [ ] laser.html implements EDD sorting + urgency badges
- [ ] piega.html and saldatura.html have same logic
- [ ] All 3 pages render orders sorted by deadline
- [ ] Badge colors correct for 3 tiers
- [ ] Days-remaining text accurate ("N giorni", "Oggi", "Scaduto")
- [ ] No console errors
- [ ] No API changes
- [ ] Tested with edge cases (overdue, today, boundary conditions)
- [ ] PLAN.md and SUMMARY.md created and committed

## Notes for Executor

1. **First Task**: Implement utility functions (getDaysRemaining, getUrgencyTier, getUrgencyLabel) in laser.html
   - Test in browser console before proceeding
   - Verify with multiple dates (overdue, today, future)

2. **Second Task**: Implement sortOrdersByEDD() and update renderOrders()
   - Use slice() to avoid mutating original array
   - Call sortOrdersByEDD before mapping to HTML

3. **CSS Step**: Add urgency badge styles (copy from PLAN.md)
   - Uses existing color variables (--accent-green, --accent-amber, --accent-red)
   - Add indicator dots for accessibility

4. **Integration**: Update renderOrders() template to display badge after status-ready
   - Use IIFE (Immediately Invoked Function Expression) to calculate tier locally
   - Clean up HTML generation, keep readable

5. **Replication**: Copy pattern to piega.html and saldatura.html
   - No changes needed to PHASE constant (already correct)
   - Test each page independently

6. **Testing**: Create test orders with diverse delivery dates
   - Verify sorting order is consistent
   - Verify colors match tiers
   - Check edge cases (overdue, today, 3-day boundary, 7-day boundary)

## Questions for User (If Needed)

1. **Sort Algorithm**: Should we add a localStorage toggle to switch between EDD and FIFO? (Out of scope for now, future enhancement)
2. **Critical Threshold**: Is "<3 days" the right threshold for red? Or should it be "<5 days"? (Research recommended 3 days, CIAA standard)
3. **Dashboard Integration**: Should the dashboard show EDD-sorted order summary too? (Out of scope, can be added later)

## Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Invalid date_consegna in old orders | Medium | Sorting breaks | Handle gracefully: skip invalid dates, don't throw |
| Timezone differences (user in different zone) | Low | Days off by 1 | Use full date comparison, not string comparison |
| Performance with 100+ orders | Low | Slow rendering | Test with large order count; sorting is O(n log n) |
| Operator confusion about urgency colors | Low | Wrong prioritization | Add tooltips on badge (future enhancement) |

## Success Metrics

- **User Adoption**: Operators report easier prioritization (post-deployment feedback)
- **OTD Improvement**: On-Time Delivery rate improves (measure after 2-4 weeks of use)
- **Code Quality**: No console errors, clean implementation, extensible pattern
- **Performance**: Orders with 50+ items render in <200ms

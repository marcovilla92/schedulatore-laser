# Phase 07 — Order Prioritization for Laser Phase

## Quick Summary

**Objective:** Add deadline-aware order prioritization to laser.html (and phase pages) using Earliest Due Date (EDD) algorithm with visual 3-tier urgency badges (green/yellow/red).

**Status:** ✅ Planning Complete — Ready for Execution

**Files:**
- `.planning/phases/07-order-prioritization/07-01-PLAN.md` — Detailed task breakdown (6 atomic tasks)
- `.planning/phases/07-order-prioritization/CONTEXT.md` — Design rationale, decisions, research summary

## What Gets Built

### Frontend Changes (Client-Side Only)
Three phase pages updated with identical prioritization logic:
- **laser.html** — Stazione LASER
- **piega.html** — Stazione PIEGA
- **saldatura.html** — Stazione SALDATURA

### Visible Features
1. **EDD Sorting**: Orders displayed in priority order (earliest deadline first)
2. **Urgency Badges**: Color-coded on each order card
   - 🟢 **Green** (safe): ≥7 days to deadline
   - 🟡 **Yellow** (caution): 3-7 days to deadline
   - 🔴 **Red** (critical): <3 days or overdue
3. **Days-Remaining Text**: "6 giorni", "Oggi", or "Scaduto" on each badge
4. **Glowing Indicator Dots**: Visual distinction for accessibility

### Example: Before vs After

**Before (arbitrary order):**
```
Order Cliente A — Due 2026-03-15
Order Cliente B — Due 2026-03-05  ← MOST URGENT (comes last, hard to find)
Order Cliente C — Due 2026-03-10
```

**After (EDD sorted with urgency badges):**
```
Order Cliente B — Due 2026-03-05 🔴 Scaduto     ← FIRST (critical)
Order Cliente C — Due 2026-03-10 🟡 5 giorni    ← SECOND (moderate)
Order Cliente A — Due 2026-03-15 🟢 13 giorni   ← THIRD (safe)
```

## How It Works

### Algorithm: Earliest Due Date (EDD)
```javascript
// Pseudo-code
sortOrdersByEDD = (orders) => {
  return orders.slice().sort((a, b) => {
    const dateA = new Date(a.data_consegna);
    const dateB = new Date(b.data_consegna);
    return dateA.getTime() - dateB.getTime();  // Earliest first
  });
}

// Urgency tier assignment
daysRemaining >= 7  → Green   (safe, no pressure)
3 <= daysRemaining < 7 → Yellow (moderate urgency)
daysRemaining < 3   → Red     (critical, act now)
```

### No Backend Changes
- Existing `/api/phase/{PHASE}/orders` endpoint unchanged
- All sorting/calculation happens in frontend JavaScript
- Database schema untouched
- Zero risk to existing API

### Timezone-Safe
- Uses ISO 8601 date format from database (`data_consegna` DateTime)
- JavaScript `new Date()` automatically handles timezone conversion
- Comparison is by full date (not string), so timezone differences don't affect sort

## Implementation Plan (6 Tasks)

### Task 1: Utility Functions
Implement three calculation functions in laser.html:
- `getDaysRemaining(deliveryDate)` → number of days
- `getUrgencyTier(daysRemaining)` → 'green'|'yellow'|'red'
- `getUrgencyLabel(daysRemaining)` → "6 giorni"|"Oggi"|"Scaduto"

**Time estimate:** 10 minutes
**Complexity:** Low (pure functions, no DOM manipulation)

### Task 2: EDD Sorting Function
Implement `sortOrdersByEDD(orders)` which sorts array by delivery date.
- Immutable (uses slice())
- Gracefully handles invalid dates
- Returns array in priority order (earliest first)

**Time estimate:** 5 minutes
**Complexity:** Low (single sort function)

### Task 3: Add CSS for Badges
Create three CSS classes for urgency tiers:
- `.urgency-badge.urgency-tier-green`
- `.urgency-badge.urgency-tier-yellow`
- `.urgency-badge.urgency-tier-red`

Plus `.urgency-indicator` for glowing dot.

**Time estimate:** 5 minutes
**Complexity:** Low (copy-paste CSS, reuses existing color variables)

### Task 4: Update laser.html renderOrders()
Integrate sorting and badge display:
1. Call `sortOrdersByEDD()` before rendering
2. Add urgency badge HTML in template (after status-ready badge)
3. Use IIFE to calculate tier/label per order

**Time estimate:** 10 minutes
**Complexity:** Low (template modification, copy code from PLAN)

### Task 5: Replicate to piega.html & saldatura.html
Copy all logic (functions, CSS, rendering) to two other phase pages.
- No changes to phase constants (already correct)
- Test each page independently

**Time estimate:** 10 minutes
**Complexity:** Low (copy-paste from laser.html)

### Task 6: Testing Edge Cases
Create test orders with diverse delivery dates and verify:
- Overdue orders appear first in red
- Today's deadline shows "Oggi"
- 7-day boundary (green ↔ yellow) correct
- 3-day boundary (yellow ↔ red) correct
- Empty order list still works
- Invalid dates don't break sorting

**Time estimate:** 15 minutes
**Complexity:** Low (manual testing in browser)

## Total Effort Estimate

| Task | Time | Complexity |
|------|------|-----------|
| 1. Utility functions | 10 min | Low |
| 2. EDD sorting | 5 min | Low |
| 3. CSS badges | 5 min | Low |
| 4. laser.html integration | 10 min | Low |
| 5. Replicate to piega/saldatura | 10 min | Low |
| 6. Testing | 15 min | Low |
| **Total** | **55 minutes** | **Low** |

All tasks are independent implementations or straightforward copy-paste. No blocking dependencies.

## Key Files

### Planning Files
```
.planning/phases/07-order-prioritization/
├── 07-01-PLAN.md          ← Detailed task breakdown with verification criteria
├── CONTEXT.md             ← Design decisions, research summary, technical approach
└── README.md              ← This file
```

### Files to Modify During Execution
```
app/frontend/
├── laser.html             ← Primary implementation (Tasks 1-4)
├── piega.html             ← Pattern replication (Task 5)
└── saldatura.html         ← Pattern replication (Task 5)
```

### Reference Files
```
.planning/
├── manufacturing-prioritization-RESEARCH.md  ← Background on EDD + urgency systems
└── STATE.md                                   ← Project state, decisions, context
```

## Verification Checklist

After all 6 tasks complete:

- [ ] laser.html loads without console errors
- [ ] Orders on laser.html sorted by delivery date (earliest first)
- [ ] Urgency badges display with correct colors (green/yellow/red)
- [ ] Days-remaining text accurate ("N giorni", "Oggi", "Scaduto")
- [ ] piega.html and saldatura.html have same logic and sorting
- [ ] Test orders with overdue dates show red and appear first
- [ ] Test orders with today's deadline show "Oggi" and red
- [ ] No API changes detected (GET /api/phase/{PHASE}/orders unchanged)
- [ ] Edge cases handled (empty list, invalid dates, boundary conditions)

## Success Criteria

Phase 07 is **COMPLETE** when:

1. **Primary Requirement** ✓
   - Orders in laser.html, piega.html, saldatura.html are sorted by delivery deadline (EDD)
   - Most urgent orders appear first on the page

2. **Visual Feedback** ✓
   - Urgency badge on each order card with color (green/yellow/red) + text label
   - Operator can determine at a glance: "This order is urgent (red) vs safe (green)"

3. **Accuracy** ✓
   - Days-remaining calculation correct for all date ranges (past, today, future)
   - Tier assignment correct (green ≥7, yellow 3-7, red <3)

4. **No Regression** ✓
   - Existing order functionality unchanged
   - Phase tracking (start/complete) still works
   - No breaking changes to API or database

5. **Code Quality** ✓
   - No console errors
   - Clean, readable implementation (functions with clear purpose)
   - Extensible pattern (replicable to other pages)

## Manufacturing Context

**Why EDD?**
- Industry standard for job shops handling custom metal fabrication orders
- Outperforms FIFO by 15-30% on on-time delivery rates (research finding)
- Aligns operator behavior with business goal (meet customer deadlines)
- Simple algorithm, proven in manufacturing worldwide

**Future Enhancements (Out of Scope):**
- localStorage toggle: Operator can switch between EDD and FIFO preference
- Critical Ratio: More dynamic approach for orders that slip schedule
- Dashboard metrics: OTD (On-Time Delivery %), order age, critical count
- Notifications: Alert when order enters red zone

## Execution Instructions

### When Ready to Execute:

1. **Read Planning Files**
   ```
   cat .planning/phases/07-order-prioritization/07-01-PLAN.md
   cat .planning/phases/07-order-prioritization/CONTEXT.md
   ```

2. **Start Execution**
   ```
   /gsd:execute-phase 07
   ```
   This spawns Claude executor with full plan context.

3. **Executor Will:**
   - Implement all 6 tasks in order
   - Test each task with verification criteria
   - Create SUMMARY.md with results
   - Commit to git

### Optional: Preview Implementation

See PLAN.md for exact code to add:
- Lines 1-50: getDaysRemaining, getUrgencyTier, getUrgencyLabel
- Lines 51-60: sortOrdersByEDD
- Lines 61-100: CSS for urgency badges
- Lines 101-150: Updated renderOrders() template

## Questions & Answers

**Q: Will this slow down the application?**
A: No. Sorting <100 orders in JavaScript is <100ms. No server calls. All client-side.

**Q: What if an order doesn't have a delivery date?**
A: Gracefully handled. Invalid dates are skipped in sorting (no error thrown).

**Q: Can I turn this off and use FIFO instead?**
A: Not yet. Future enhancement: localStorage toggle for algorithm preference.

**Q: Will existing orders be re-sorted?**
A: Yes. Every time loadOrders() is called (currently every 5 seconds), orders are sorted by deadline. This is intentional—operators see current prioritization.

**Q: Does this work with mobile?**
A: Yes. CSS is responsive. JavaScript works on all browsers.

## Next Steps

1. **Review PLAN.md** — Understand all 6 tasks in detail
2. **Review CONTEXT.md** — Understand design decisions and research
3. **Execute via `/gsd:execute-phase 07`** — Claude executor implements all tasks
4. **Verify** — Test in browser with sample orders
5. **Commit** — Auto-committed with full message and SUMMARY
6. **Deploy** — Merges to production as part of normal workflow

---

**Date Created:** 2026-03-02
**Confidence Level:** HIGH (manufacturing best practice + proven JavaScript patterns)
**Risk Level:** LOW (client-side only, no API changes, extensible pattern)
**Estimate:** 55 minutes execution time

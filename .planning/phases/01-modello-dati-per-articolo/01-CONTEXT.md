# Phase 1: Modello Dati per Articolo - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Backend data model, API, and logic for per-article phase tracking. Every article in an order carries its own assigned phases, tracks its own completion status, and the system correctly derives order-level status from article-level data. UI for assigning phases (Phase 2) and department views (Phase 3) are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Default phases per article
- All 5 phases (LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE) are assigned by default when an order is created
- Office staff will remove phases that don't apply in Phase 2 (Assegnazione Fasi) — this phase just provides the data model and defaults
- No client-specific or format-specific defaults — always all 5

### Articles as first-class entities
- Articles must become their own database table (`articles`) instead of staying as JSON inside the `orders` table
- Each article is a proper DB record with its own UUID primary key, a foreign key to `order_id`, and its own `required_phases`
- Auto-generated UUID for article identity — not dependent on extracted PDF fields or position index

### Claude's Discretion
- Whether `required_phases` is stored as a JSON list column on the articles table or as a separate normalized ArticlePhase table — pick what fits best with existing SQLAlchemy patterns
- Migration strategy for existing orders (how to populate the new articles table from existing JSON data)
- Exact article table schema (which fields from the current JSON articles structure become columns vs stay as JSON attributes)
- Backward compatibility approach for pre-v1.1 data
- API contract changes for phase start/complete operations
- Phase ordering logic (whether to enforce sequence or allow flexibility)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The key constraint is that this phase builds the foundation that Phase 2 (UI checkboxes) and Phase 3 (department views) will consume, so the API must cleanly support those use cases.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-modello-dati-per-articolo*
*Context gathered: 2026-02-19*

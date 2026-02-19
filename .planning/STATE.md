# Project State — Schedulatore Laser

## Current Position

**Milestone**: v1.1 Fasi per Articolo
**Phase**: Not started (defining requirements)
**Plan**: —
**Status**: Defining requirements
**Last activity**: 2026-02-19 — Milestone v1.1 started

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Operators see what needs processing next and track completion in real-time
**Current focus:** Per-article phase management with batch operations

## Progress

```
Progress: ░░░░░░░░░░ 0%
```

## Accumulated Context

### From v1.0 (Pre-GSD)

| Date | Action | Details |
|------|--------|---------|
| 2026-02-18 | Backend review | Fixed 14 critical/high bugs across 9 files |
| 2026-02-18 | GSD installed | v1.20.4 with full skill ecosystem |
| 2026-02-18 | Skills integrated | 12 commands + 6 skills + SQLite MCP |
| 2026-02-18 | UI redesign | 7 pages with dark glassmorphism design |

### Decisions

| Decision | Phase | Rationale |
|----------|-------|-----------|
| flag_modified() for JSON mutations | Backend fix | SQLAlchemy doesn't track in-place JSON changes |
| 50MB upload limit | Security | Prevent unbounded file uploads |
| lambda defaults for Column | Backend fix | Prevent mutable default sharing |

### Known Issues

- `get_orders_by_phase` loads ALL orders (optimize with JOIN when volume grows)
- `declarative_base()` deprecated in SQLAlchemy 2.0
- `datetime.utcnow()` deprecated in Python 3.12+
- ORM objects returned after session.close() (fragile pattern)

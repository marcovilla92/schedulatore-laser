# Project State — Schedulatore Laser

## Current Position

**Milestone**: v1.0 Stabilization
**Phase**: Pre-planning (GSD just initialized)
**Status**: Ready for `/gsd:map-codebase` or `/gsd:plan-phase`

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** Operators see what needs processing next and track completion in real-time
**Current focus:** Backend stabilization and tooling integration

## Progress

```
[====================] Project initialized
```

## Recent Activity

| Date | Action | Details |
|------|--------|---------|
| 2026-02-18 | Backend review | Fixed 14 critical/high bugs across 9 files |
| 2026-02-18 | GSD installed | v1.20.4 with full skill ecosystem |
| 2026-02-18 | Skills integrated | 12 commands + 6 skills + SQLite MCP |
| 2026-02-18 | UI redesign | 7 pages with dark glassmorphism design |

## Decisions

| Decision | Phase | Rationale |
|----------|-------|-----------|
| flag_modified() for JSON mutations | Backend fix | SQLAlchemy doesn't track in-place JSON changes |
| 50MB upload limit | Security | Prevent unbounded file uploads |
| lambda defaults for Column | Backend fix | Prevent mutable default sharing |

## Known Issues

- `get_orders_by_phase` loads ALL orders (optimize with JOIN when volume grows)
- `declarative_base()` deprecated in SQLAlchemy 2.0
- `datetime.utcnow()` deprecated in Python 3.12+
- ORM objects returned after session.close() (fragile pattern)

## Tooling Available

- **Commands**: /commit, /test, /quality, /verify, /clean, /deps, /pr-create
- **Skills**: webapp-testing, vibesec, playwright-skill, pdf, mcp-builder, skill-creator
- **MCP**: SQLite direct access to scheduler.db
- **GSD**: Full 30+ command suite with 11 agents

## Last Session

**Date**: 2026-02-18
**Stopped at**: GSD + skill ecosystem integration complete
**Resume with**: `/gsd:map-codebase` to analyze full codebase, then `/gsd:plan-phase 1`

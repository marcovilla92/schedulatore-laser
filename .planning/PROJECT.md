# Schedulatore Laser

## What This Is

A web-based order management and laser cutting scheduling system for metal carpentry (carpenteria metallica). Handles the full lifecycle: PDF order intake, data extraction, laser cut planning, and multi-phase production tracking (LASER → PIEGA → SALDATURA → PULIZIA → SPEDIZIONE) across workstations on a local network.

## Core Value

Operators at any workstation can see what needs to be cut/bent/welded next, start/complete phases, and track partial article completion — eliminating paper-based scheduling.

## Requirements

### Validated

- PDF upload and automatic data extraction (16 formats supported)
- Order creation with articles, delivery dates, client info
- Multi-phase processing: LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE
- Partial article completion per phase
- Timer tracking per phase with real-time display
- Dashboard with Kanban-style status overview
- Phase-specific views (laser.html, piega.html, saldatura.html)
- LAN multi-workstation access
- DXF/DWG drawing file attachment
- Order archival

### Active

#### Current Milestone: v1.1 Fasi per Articolo

**Goal:** Ogni articolo ha il proprio percorso di fasi indipendente, assegnato dall'ufficio, con gestione batch nelle viste di reparto.

**Target features:**
- Assegnazione fasi per articolo (checkbox per LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE — tutte opzionali)
- Stato indipendente per articolo (ogni articolo traccia il proprio avanzamento)
- Viste reparto mostrano solo articoli pertinenti a quella fase
- Batch start/complete per ordine dentro ogni fase
- Ordine completato quando tutti gli articoli hanno finito le loro fasi assegnate

### Out of Scope

- Profili/template predefiniti per combinazioni di fasi — v2 (checkbox sufficienti per v1.1)
- Fix tecnici/deprecation (sessioni ORM, API deprecate) — milestone separato
- Nuove fasi di lavorazione oltre le 5 esistenti — non richiesto

## Context

- **Stack**: Python 3.8+ / Flask 2.3 / SQLAlchemy 2.0 / SQLite / Vanilla HTML+CSS+JS
- **Deployment**: Local network, single server, multiple browser clients
- **Users**: Factory floor operators (non-technical), office staff
- **Language**: All UI and code in Italian
- **No build step**: Frontend is pure HTML with inline CSS/JS
- **16 PDF formats**: Each client sends orders in different PDF layouts

## Constraints

- **Tech stack**: Flask + SQLite — no heavy frameworks, must stay lightweight
- **No build tools**: Frontend must remain vanilla HTML/CSS/JS — no bundlers
- **LAN only**: No cloud deployment, no external auth
- **Italian**: All user-facing text in Italian
- **Single DB file**: SQLite with `check_same_thread=False`

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SQLite over PostgreSQL | Single server, <1000 orders, no concurrent writes | ✓ Good |
| Vanilla JS over React | Factory operators, no build step needed | ✓ Good |
| UUID string PKs | Avoid integer collision across distributed creation | ✓ Good |
| JSON columns for articles | Flexible schema per order format | ✓ Good |
| Dark glassmorphism UI redesign | Modern look, consistent design system | — Pending |

---
*Last updated: 2026-02-19 after milestone v1.1 definition*

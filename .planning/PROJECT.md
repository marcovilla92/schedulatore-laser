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

#### Current Milestone: v1.2 Parser Universale

**Goal:** Il sistema estrae automaticamente cliente, articoli, quantità e data di consegna da qualsiasi PDF — inclusi formati mai visti — usando Docling + Gemini 2.0 Flash API, senza dover scrivere parser specifici per ogni nuovo cliente.

**Target features:**
- Audit del success rate dei parser esistenti su PDF reali
- Estrattore universale basato su Docling + Gemini 2.0 Flash
- Confidence scoring: l'utente vede quali campi sono stati estratti con bassa confidenza
- Integrazione nella pipeline esistente con fallback ai parser noti
- Nessuna modifica al flusso UI: l'utente vede già i risultati nella pagina ordini estratti

#### Pending Milestone: v1.1 Fasi per Articolo

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
- Training/fine-tuning di modelli custom — Gemini off-the-shelf è sufficiente
- Parser specifici per nuovi formati — l'estrattore universale li gestisce automaticamente

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
- **LAN only**: No cloud deployment, no external auth — ma il server ha accesso internet per le API esterne
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
| Gemini 2.0 Flash over local LLM | Server ha internet, free tier sufficiente, massima accuratezza senza infrastruttura | — Pending |
| Docling come base per estrazione testo | Già nel progetto, ottimo per layout/tabelle, complementare all'LLM | — Pending |

---
*Last updated: 2026-02-19 after milestone v1.2 definition*

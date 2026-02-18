# CLAUDE.md — Schedulatore Laser

## Project Overview

**Schedulatore Laser v1.0** is a web-based order management and laser cutting scheduling system for metal carpentry (carpenteria metallica). It handles the full lifecycle of fabrication orders: PDF intake, data extraction, laser cut planning, and multi-phase production tracking across workstations on a local network.

**Primary language**: Italian (UI, variable names, documentation, comments).

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.8+ / Flask 2.3.2 |
| Database | SQLite 3 via SQLAlchemy 2.0.19 ORM |
| Frontend | Vanilla HTML5 + CSS3 + JavaScript (zero frameworks) |
| PDF Parsing | PyPDF2 3.0.1, pdfplumber 0.9.0, Docling 2.2.0 (lazy-loaded) |
| DXF/Drawing | ezdxf 1.9.11 |
| CORS | Flask-CORS 4.0.0 |
| WSGI | gunicorn 21.2.0 (production) |

## Repository Structure

```
schedulatore-laser/
├── CLAUDE.md                          # This file
├── README.md                          # Project README
├── LEGGI_PRIMA.md                     # Italian overview doc
├── AVVIO_RAPIDO.txt                   # Quick start guide (Italian)
├── COMPLETAMENTO.md                   # Completion report
├── 00_LEGGI_QUESTO_PRIMO.txt          # Summary of all features
│
├── app/                               # Main application directory
│   ├── requirements.txt               # Python dependencies (pinned versions)
│   ├── run.py                         # Entry point: python run.py
│   ├── start_backend.py               # Alternative entry point
│   ├── .gitignore                     # Excludes venv, db, uploads, caches
│   │
│   ├── backend/                       # Flask API + business logic
│   │   ├── __init__.py                # Package init
│   │   ├── __main__.py                # python -m backend
│   │   ├── app.py                     # Flask app, routes, API endpoints
│   │   ├── models.py                  # SQLAlchemy ORM models (4 tables)
│   │   ├── database.py                # OrderManager CRUD operations
│   │   ├── pdf_parser.py              # PDF format dispatcher (16 formats)
│   │   ├── parsers_divisione.py       # DIVISIONE CUCINE format
│   │   ├── parsers_for_ordine.py      # FOR-ORDINE / Sozzi format
│   │   ├── parsers_for_ordine_aza.py  # AZA INTERNATIONAL variant
│   │   ├── parsers_generic.py         # Fallback/generic regex parser
│   │   ├── parsers_markdown_tables.py # Table extraction via Docling
│   │   ├── parsers_oafa.py            # OAFA / DECA format
│   │   ├── parsers_ordine_ls.py       # Ordine LS format
│   │   └── parsers_po_bebitalia.py    # B&B Italia PO format
│   │
│   ├── frontend/                      # Static HTML pages (served by Flask)
│   │   ├── welcome.html               # Landing page / system status
│   │   ├── dashboard.html             # Main dashboard with stats & Kanban
│   │   ├── laser.html                 # Laser planning by material thickness
│   │   ├── piega.html                 # Bending phase tracking
│   │   ├── saldatura.html             # Welding phase tracking
│   │   ├── ordini_estratti.html       # Extracted orders from PDFs
│   │   ├── archive.html               # Order archive
│   │   └── index.html                 # Redirect
│   │
│   ├── uploads/                       # Auto-created at runtime
│   │   ├── pdfs/                      # Uploaded PDF orders (gitignored)
│   │   └── drawings/                  # Uploaded DXF/DWG files (gitignored)
│   │
│   ├── database/                      # Auto-created at runtime
│   │   └── scheduler.db               # SQLite database (gitignored)
│   │
│   ├── START_BACKEND.bat              # Windows launcher
│   ├── FIND_IP.bat                    # Discover LAN IP for remote access
│   ├── TEST_SISTEMA.bat               # System diagnostic script
│   ├── SETUP_RETE.bat                 # Network/firewall setup
│   │
│   └── [50+ test/debug scripts]       # test_*.py, debug_*.py, analyze_*.py
│
└── 072-24/                            # Reference order with DXF drawings
```

## How to Run

```bash
# Install dependencies
cd app
pip install -r requirements.txt

# Start the server (port 5000, all interfaces)
python run.py
```

The server starts at `http://localhost:5000`. Database and upload directories are auto-created on first run. For LAN access from other workstations, use `http://<server-ip>:5000`.

On Windows, use `app/START_BACKEND.bat` for automated setup and launch.

## Database Schema (4 tables)

| Table | Purpose | Primary Key |
|-------|---------|-------------|
| `orders` | Main order records with articles (JSON), status, delivery dates | `id` (String/UUID) |
| `order_files` | PDF/DXF files attached to orders | `id` (String/UUID) |
| `processing_steps` | Per-phase tracking (LASER, PIEGA, SALDATURA, etc.) with article-level completion | `id` (String/UUID) |
| `order_notifications` | Completion notifications with total times | `id` (String/UUID) |

All IDs are UUID strings. The database is SQLite with `check_same_thread=False` for Flask compatibility. Schema is auto-created via `Base.metadata.create_all()`.

### Key Enums

- **OrderStatus**: `RICEVUTO`, `LASER_COMPLETATO`, `PIEGA_COMPLETATA`, `SALDATURA_COMPLETATA`, `PULIZIA_COMPLETATA`, `SPEDITO`
- **ProcessingPhase**: `LASER`, `PIEGA`, `SALDATURA`, `PULIZIA`, `SPEDIZIONE`

## API Endpoints

### Frontend Routes
- `GET /` — welcome page
- `GET /ordini-estratti` — extracted orders dashboard
- `GET /<path:filename>` — any frontend file

### Orders
- `POST /api/orders` — create order
- `GET /api/orders` — list orders (optional `?cliente=` filter)
- `GET /api/orders/<id>` — get single order
- `PUT /api/orders/<id>/articles` — update articles

### Processing Phases
- `POST /api/orders/<id>/phase/<name>/start` — start a phase
- `POST /api/orders/<id>/phase/<name>/complete` — complete entire phase
- `POST /api/orders/<id>/phase/<name>/complete-partial` — mark specific articles done
- `GET /api/phase/<name>/orders` — get all orders for a phase

### Files & PDF
- `POST /api/extract-pdf-data` — extract metadata from uploaded PDF
- `POST /api/upload-drawing` — upload DXF/DWG file
- `POST /api/process-pdfs` — batch process a folder of PDFs
- `GET /api/extracted-orders` — list all extracted orders
- `GET /api/health` — health check

## Architecture & Patterns

### Backend
- **MVC-like**: `models.py` (Model), `app.py` (Controller/Routes), HTML files (View)
- **Repository pattern**: `OrderManager` class in `database.py` encapsulates all CRUD
- **Factory/dispatcher pattern**: `pdf_parser.py` detects PDF format and delegates to the correct `parsers_*.py` module
- **Two-stage extraction**: Primary format-specific parser → fallback to `parsers_generic.py`
- **Lazy loading**: Docling (heavy ML library) only imported when actually needed
- **Session-per-request**: SQLAlchemy sessions created and closed within each operation

### Frontend
- All pages are self-contained HTML files with inline `<style>` and `<script>` blocks
- No bundler, no build step, no framework
- Fetch API for all backend communication (JSON payloads)
- 30-second auto-refresh on the dashboard
- Drag-and-drop file uploads
- Mobile-first responsive design

### PDF Parser Architecture
The dispatcher in `pdf_parser.py` uses text content matching to identify which of the 16 supported formats a PDF belongs to, then delegates to the appropriate parser. Each parser module exports functions that return a structured dict with `cliente`, `numero_ordine`, `articles[]`, etc.

## Naming Conventions

| Element | Convention | Examples |
|---------|-----------|----------|
| Python files | `snake_case` | `pdf_parser.py`, `parsers_for_ordine.py` |
| Python classes | `PascalCase` | `OrderManager`, `ProcessingStep` |
| Python functions | `snake_case` | `extract_pdf_content`, `create_order` |
| Python variables | `snake_case` | `order_id`, `data_consegna` |
| Enums | `UPPER_SNAKE_CASE` | `LASER_COMPLETATO`, `RICEVUTO` |
| HTML/CSS IDs & classes | `kebab-case` | `upload-area`, `order-card` |
| API routes | `kebab-case` with REST verbs | `/api/orders`, `/api/extract-pdf-data` |
| DB columns | `snake_case` | `timestamp_inizio`, `completed_articles` |

**Domain terms are in Italian**: ordine (order), cliente (client), fase (phase), piega (bending), saldatura (welding), pulizia (cleaning), spedizione (shipping), consegna (delivery), lavorazione (processing), articolo (article/item).

## Key Development Guidelines

### When Modifying Backend Code
- All backend modules are inside `app/backend/` and use relative imports (`from .models import ...`)
- The entry point is `app/run.py` which imports `from backend.app import app`
- Database sessions must be properly closed — follow the pattern in `database.py` (try/finally with `session.close()`)
- JSON columns (`articles`, `required_phases`, `completed_articles`) store Python lists/dicts serialized to JSON
- All API endpoints return JSON responses with appropriate HTTP status codes
- Error responses follow `{"error": "message"}` format

### When Modifying Frontend Code
- Each HTML file is fully self-contained (CSS + JS inline)
- No shared CSS/JS files — changes to common UI must be replicated across pages
- The backend URL is typically hardcoded or derived from `window.location`
- All UI text is in Italian

### When Adding New PDF Parsers
1. Create a new `parsers_<format_name>.py` in `app/backend/`
2. Export a parsing function that accepts text content and returns a standardized dict
3. Register the format detection logic in `pdf_parser.py`'s dispatcher
4. Follow the two-stage pattern: specific parser first, generic fallback

### When Modifying the Database Schema
- Edit models in `models.py`
- The database auto-creates missing tables but does NOT auto-migrate existing ones
- For schema changes on existing tables, delete `app/database/scheduler.db` and let it recreate, or add manual migration logic

## Files That Should NOT Be Committed
- `app/database/` — SQLite database (auto-created)
- `app/uploads/pdfs/` — user-uploaded PDFs
- `app/uploads/drawings/` — user-uploaded DXF/DWG files
- `.env` files — environment variables
- `__pycache__/` — Python bytecode cache
- Virtual environment directories (`venv/`, `.venv/`)

## Testing

There is no formal test framework (no pytest configuration). The project contains 50+ ad-hoc test/debug scripts (`test_*.py`, `debug_*.py`, `analyze_*.py`) in `app/` that were used during development. The primary validation method is:

```bash
# Batch test all 16 PDF formats
cd app
python test_all_16_final.py
```

To manually test the API:
```bash
# Health check
curl http://localhost:5000/api/health

# List orders
curl http://localhost:5000/api/orders
```

## Common Tasks

| Task | Command |
|------|---------|
| Start server | `cd app && python run.py` |
| Install deps | `cd app && pip install -r requirements.txt` |
| Test PDF extraction | `cd app && python test_all_16_final.py` |
| Check system health | `curl http://localhost:5000/api/health` |
| Find LAN IP (Windows) | `app\FIND_IP.bat` |

## Performance Characteristics

- Single PDF extraction: 0.5–1.0 seconds
- Batch (16 PDFs): 15–20 seconds
- API response time: <100ms
- Dashboard load: <500ms
- Supports multiple concurrent workstations over LAN

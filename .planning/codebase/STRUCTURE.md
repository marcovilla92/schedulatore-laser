# Codebase Structure

**Analysis Date:** 2026-02-19

## Directory Layout

```
schedulatore-laser/
├── app/
│   ├── backend/                    # Flask REST API server
│   │   ├── __init__.py
│   │   ├── __main__.py             # Entry point: python -m app.backend
│   │   ├── app.py                  # Flask app, 17 routes (350 lines)
│   │   ├── models.py               # SQLAlchemy ORM schema (94 lines)
│   │   ├── database.py             # OrderManager CRUD class (396 lines)
│   │   ├── pdf_parser.py           # PDF format dispatcher
│   │   ├── parsers_*.py            # 8 format-specific parsers
│   │   ├── parsers_generic.py      # Fallback intelligent parser
│   │   └── parsers_markdown_tables.py  # Table extraction helper
│   ├── frontend/                   # HTML5 web UI (7 pages)
│   │   ├── welcome.html            # Order intake, PDF upload (800+ lines)
│   │   ├── laser.html              # LASER phase station (1000+ lines)
│   │   ├── piega.html              # PIEGA phase station
│   │   ├── saldatura.html          # SALDATURA phase station
│   │   ├── dashboard.html          # Order status overview
│   │   ├── ordini_estratti.html    # Extracted orders view
│   │   └── archive.html            # Completed orders archive
│   ├── database/                   # SQLite database
│   │   └── scheduler.db            # Generated at runtime
│   └── uploads/                    # Uploaded files (runtime-created)
│       ├── pdfs/                   # PDF uploads
│       └── drawings/               # DXF/image uploads
├── .planning/codebase/             # GSD analysis (this directory)
│   ├── ARCHITECTURE.md             # System design and data flow
│   └── STRUCTURE.md                # This file
├── requirements.txt                # Python dependencies
├── README.md                       # Project overview
└── [test scripts and docs]         # 100+ analysis/test files
```

## Directory Purposes

**app/backend:**
- Purpose: REST API server, database models, PDF parsing pipeline
- Contains: Flask routes, SQLAlchemy ORM, PDF dispatcher and 8 format parsers
- Key files: `app.py` (routes), `models.py` (schema), `database.py` (CRUD), `pdf_parser.py` (dispatcher)

**app/frontend:**
- Purpose: Single Page Application with 7 HTML pages for multi-station order tracking
- Contains: HTML + inline CSS + JavaScript, no bundler (direct script tags)
- Key files: `welcome.html` (order entry), `laser.html`/`piega.html`/`saldatura.html` (phase stations), `ordini_estratti.html` (dashboard)

**app/database:**
- Purpose: SQLite database persistence
- Generated at runtime by SQLAlchemy schema initialization (`models.initialize_database()`)
- Single file: `scheduler.db` - contains Order, ProcessingStep, OrderFile, OrderNotification tables

**app/uploads:**
- Purpose: Temporary storage for user-uploaded files
- Subdirs: `pdfs/` (order PDFs), `drawings/` (DXF/image files)
- Lifecycle: Created at runtime, persisted for reference

**.planning/codebase/:**
- Purpose: GSD (Get-Shit-Done) orchestration artifacts
- Contains: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md

## Key File Locations

**Entry Points:**

- `app/backend/__main__.py` - Script entry: `python -m app.backend` starts Flask server on localhost:5000
- `app/backend/app.py` - Flask app definition, CORS config, route registration
- `app/frontend/welcome.html` - Root route `/` serves this first

**Configuration:**

- `app/backend/app.py` lines 14-25 - Flask config: MAX_CONTENT_LENGTH=50MB, CORS enabled, upload folders
- `app/backend/models.py` lines 9-10 - Database URL construction for SQLite

**Core Logic:**

- `app/backend/models.py` - SQLAlchemy schema: Order (5 relationships), ProcessingStep (article tracking), OrderFile, OrderNotification
- `app/backend/database.py` - OrderManager class with 11 static methods: create, read, update, phase transitions
- `app/backend/pdf_parser.py` - PDF dispatcher: format detection → parser selection → field extraction

**Testing:**

- No unit test framework configured (see TESTING.md)
- 100+ manual test scripts in `app/` root (analyze_*.py, test_*.py, debug_*.py)
- Test results saved as .txt files (analyze_57ac.txt, test_all_16_results.txt, etc.)

**PDF Parsers (Format Support):**

- `parsers_divisione.py` - DIVISIONE CUCINE format
- `parsers_for_ordine.py` - FOR-ORDINE format (4 variants)
- `parsers_oafa.py` - OAFA format
- `parsers_for_ordine_aza.py` - FOR-ORDINE AZA variant
- `parsers_ordine_ls.py` - Ordine LS simple format
- `parsers_po_bebitalia.py` - B&B ITALIA PO format
- `parsers_generic.py` - Fallback intelligent parser
- `parsers_markdown_tables.py` - Table extraction helper

## Naming Conventions

**Files:**

- Python modules: `snake_case.py` - e.g., `pdf_parser.py`, `parsers_oafa.py`, `models.py`
- HTML pages: `snake_case.html` - e.g., `welcome.html`, `ordini_estratti.html`
- Database: `scheduler.db` (fixed)
- Uploads: `{order_id}_{original_filename}` for drawings, `{original_filename}` for PDFs

**Functions/Methods:**

- Flask routes: `snake_case()` - e.g., `extract_pdf_data()`, `start_phase()`, `complete_phase_partial()`
- Parser functions: `extract_<field>_<format>()` - e.g., `extract_cliente_oafa()`, `extract_numero_ordine_divisione()`
- Dispatcher: `extract_pdf_content()` - main entry point for any PDF

**Classes:**

- ORM models: `PascalCase` - Order, ProcessingStep, OrderFile, OrderNotification
- Enums: `PascalCase` - OrderStatus, ProcessingPhase
- Manager: `PascalCase` - OrderManager (static utility class)

**Directories:**

- Feature: `snake_case/` - e.g., `backend/`, `frontend/`, `uploads/`
- Not deeply nested (max 3 levels: app/backend, app/frontend, app/uploads/pdfs)

**Database/ORM:**

- Table names: `snake_case_plural` - orders, processing_steps, order_files, order_notifications
- Column names: `snake_case` - order_id, timestamp_inizio, completed_articles
- JSON columns (flexible): stored as JSON strings, accessed via Python dict/list

**Environment Variables:**

- Stored in `.env` file (not tracked)
- Accessed via `os.environ.get()` or `os.getenv()`
- Key configs hardcoded in app.py (UPLOAD_FOLDER, DATABASE_URL)

## Where to Add New Code

**New Feature (e.g., Quality Control Phase):**

1. **Backend Route:**
   - Add method to `OrderManager` in `app/backend/database.py`
   - Add Flask route to `app/backend/app.py` under appropriate section (FASI, API, etc.)
   - Follows pattern: validate input → call OrderManager → return JSON with success + details

2. **Frontend Page:**
   - Create new HTML file in `app/frontend/` (e.g., `qc.html`)
   - Copy structure from `laser.html` (nav bar, phase container, article list, buttons)
   - Add phase name in nav links and route to new page
   - JavaScript fetch calls to backend `/api/orders/*/phase/QC/*` endpoints

3. **Database Schema:**
   - Modify `Order.required_phases` to include new phase
   - ProcessingStep automatically created for each required phase
   - No migration needed (SQLite, single dev environment)

**New PDF Format Support:**

1. **Add Format Parser:**
   - Create `app/backend/parsers_<format_name>.py`
   - Implement function `extract_<format_name>(text: str, markdown_text: str = None, filepath: str = None) -> dict`
   - Return dict with keys: cliente, numero_ordine, data_consegna, data_ricezione, articoli

2. **Register in Dispatcher:**
   - Add detection regex to `detect_pdf_format()` in `app/backend/pdf_parser.py`
   - Add import: `from .parsers_<format_name> import extract_<format_name>`
   - Add case in dispatch logic: `if format_name == "FORMAT": return extract_<format_name>(...)`

3. **Test:**
   - Create test PDF sample
   - Test via `/api/extract-pdf-data` endpoint or batch script
   - Verify extracted data matches expected (cliente, articoli count, etc.)

**New Utility Function:**

- **Data extraction helpers:** Add to relevant `parsers_*.py` file
- **Shared utilities:** Add to `parsers_generic.py` or create `app/backend/utils.py`
- Import pattern: `from .module import function`

**Tests:**

- **Manual tests:** Create `test_<feature>.py` in `app/` root
- **Integration tests:** Use `/api/*` endpoints with HTTP client
- **Parser tests:** Parse sample PDFs, verify extracted fields

## Special Directories

**app/database/:**
- Purpose: Persistent SQLite database storage
- Generated: Yes (created at first run by `initialize_database()`)
- Committed: No (app/database/ exists but empty; `.db` files in .gitignore)

**app/uploads/:**
- Purpose: Temporary storage for PDFs and drawings
- Generated: Yes (directories created at app startup)
- Committed: No (all files ignored, directories exist for runtime)

**app/frontend (HTML only):**
- Purpose: Static web UI served by Flask
- Generated: No (manually created HTML files)
- Committed: Yes (source files tracked)
- No build step, no bundling, no transpilation

**Test/Debug Directory (app/ root):**
- 100+ Python scripts for testing parsers, APIs, formats
- Not part of core app; aids development
- Scripts: analyze_*.py, test_*.py, debug_*.py, batch_test_*.py
- Results: .txt files with extraction output for verification

---

*Structure analysis: 2026-02-19*

# Architecture

**Analysis Date:** 2026-02-19

## Pattern Overview

**Overall:** Layered architecture with a Flask REST API backend, HTML/JavaScript frontend, and multi-format PDF extraction pipeline. The system follows a three-tier pattern: Presentation (HTML), API (Flask routes), and Data (SQLAlchemy ORM with SQLite).

**Key Characteristics:**
- REST API-driven communication between frontend and backend
- Multi-format dispatcher pattern for PDF parsing (format detection + format-specific parsers)
- Database-centric state management with SQLAlchemy ORM
- Client-side state for UI interactions (no persistent client state)
- Sequential processing pipeline for PDF extraction and order creation

## Layers

**Presentation Layer (Frontend):**
- Purpose: Provides HTML5 UI for order management and phase tracking across 7 station pages
- Location: `app/frontend/`
- Contains: HTML files with embedded inline CSS and JavaScript
- Depends on: REST API endpoints exposed by backend
- Used by: Browser clients (end users at different workstations)
- Key files: `welcome.html`, `laser.html`, `piega.html`, `saldatura.html`, `dashboard.html`, `ordini_estratti.html`, `archive.html`

**API Layer (Routes):**
- Purpose: Exposes REST endpoints for order CRUD, phase tracking, PDF upload, and file management
- Location: `app/backend/app.py`
- Contains: 17 Flask route handlers organized into 5 groups: Frontend routes, Order API, Phase API, File API, PDF Processing
- Depends on: Database layer (`OrderManager`), PDF parsing layer (`extract_pdf_content`)
- Used by: Frontend JavaScript, batch processing scripts
- Pattern: Each route validates input, delegates to business logic, returns JSON

**Business Logic Layer (Database Management):**
- Purpose: Handles order state transitions, article tracking, and processing step management
- Location: `app/backend/database.py`
- Contains: `OrderManager` class with 11 static methods for order lifecycle management
- Depends on: ORM models (`Order`, `ProcessingStep`, `OrderFile`, `OrderNotification`)
- Used by: API layer routes
- Key operations: create orders, track partial completions, query by phase, manage article state

**Data Model Layer (ORM):**
- Purpose: Defines database schema and relationships
- Location: `app/backend/models.py`
- Contains: 4 SQLAlchemy model classes + 2 enum classes + database initialization
- Depends on: SQLAlchemy, SQLite
- Used by: Database manager, direct ORM queries
- Pattern: Declarative base with relationships, JSON columns for flexible article/step tracking

**PDF Extraction Layer (Multi-Format Parser):**
- Purpose: Converts PDF files into structured order data through format detection and format-specific parsing
- Location: `app/backend/pdf_parser.py` (dispatcher) + 8 format-specific parsers
- Contains:
  - Dispatcher: `extract_pdf_content()` → format detection → parser selection → fallback chain
  - Format parsers: 8 specialized modules (`parsers_oafa.py`, `parsers_for_ordine.py`, `parsers_ordine_ls.py`, etc.)
  - Utility parsers: `parsers_generic.py`, `parsers_markdown_tables.py`
- Depends on: PyPDF2 (text extraction), regex (pattern matching), Docling (optional OCR)
- Used by: API endpoint `extract_pdf_data()`, batch processing
- Pattern: Detection → specialized parsing → field extraction (cliente, numero_ordine, data_consegna, articoli)

## Data Flow

**User Creates Order (Manual):**

1. User submits order form at `welcome.html`
2. Frontend POST to `/api/orders` with order JSON
3. `OrderManager.create_order()` creates Order + ProcessingStep records for each required phase
4. Response returns order_id + order details
5. Frontend stores order_id for subsequent phase tracking

**PDF Upload → Order Extraction:**

1. User uploads PDF file at `welcome.html`
2. Frontend POST to `/api/extract-pdf-data` with file
3. `extract_pdf_data()` route calls `extract_pdf_content(filepath)`
4. Dispatcher in `pdf_parser.py`:
   - Extracts raw text using PyPDF2
   - Calls `detect_pdf_format(text)` → returns format string
   - Calls appropriate parser: `extract_oafa()`, `extract_for_ordine()`, etc.
   - Each parser extracts: cliente, numero_ordine, data_consegna, articoli (list)
5. Return JSON with extracted data to frontend
6. User reviews and creates order via `/api/orders` endpoint (same as manual)

**Order Phase Completion Flow:**

1. Operator at station (laser.html, piega.html, etc.) clicks "Start Phase" button
2. Frontend POST to `/api/orders/<order_id>/phase/<phase>/start` with operatore name
3. `start_phase()` sets `ProcessingStep.timestamp_inizio` and `operatore`
4. When articles done, operator clicks "Complete Phase"
5. Frontend POST to `/api/orders/<order_id>/phase/<phase>/complete-partial` with article_indices
6. `complete_phase_partial()`:
   - Marks specified articles as completed in `ProcessingStep.completed_articles`
   - If all articles for phase done, sets `timestamp_fine`
   - If all phases done for order, sets order status to SPEDITO
7. Response includes updated order details with next phases
8. Frontend refreshes article list for operator

**Dashboard Data Load:**

1. User opens `ordini_estratti.html`
2. Frontend periodically GETs `/api/extracted-orders`
3. Returns all orders with serialized processing_steps and article states
4. Frontend groups/sorts by client or status

**State Management:**

- **Persistent State (Database):** Order records, article lists, processing steps, timestamps
- **Session State:** Active order_id, current phase, logged-in operator
- **UI State (Frontend):** Selected articles, filter choices, modal visibility (stored in DOM/JS variables)

## Key Abstractions

**Order:**
- Purpose: Represents a customer production job with multiple articles and required processing phases
- Examples: `app/backend/models.py` lines 29-48 (`Order` class)
- Pattern: Aggregate root with JSON-stored articles and related ProcessingStep entities

**ProcessingStep:**
- Purpose: Tracks state of a specific phase (LASER, PIEGA, SALDATURA, etc.) for an order
- Examples: `app/backend/models.py` lines 60-72
- Pattern: Entity with timestamps (start/finish), operatore tracking, completed_articles indices array

**OrderManager:**
- Purpose: Encapsulates all business logic for order lifecycle (CRUD, phase transitions, queries)
- Examples: `app/backend/database.py` lines 11-396
- Pattern: Static utility class with transaction management and session handling
- Key methods:
  - `create_order()` - initializes order + processing steps
  - `complete_phase_partial()` - updates article state, marks phase complete when all articles done
  - `get_order_details()` - calculates next_phase per article by finding first incomplete required phase

**PDF Parser Dispatcher:**
- Purpose: Routes PDF files to correct format-specific parser
- Examples: `app/backend/pdf_parser.py` lines 100-200 (excerpt)
- Pattern: Format detection via regex patterns → dynamic function dispatch → structured output

**Article:**
- Purpose: Individual product line item in an order (JSON stored, not separate table)
- Structure: `{"name": str, "code": str, "qty": int, "required_phases": [str]}`
- Pattern: Flexible JSON to support varying article attributes across PDF formats

## Entry Points

**Web Application Entry:**
- Location: `app/backend/app.py` lines 382-383
- Triggers: `python -m app.backend` or `python app/backend/__main__.py`
- Responsibilities:
  - Initialize Flask app with CORS
  - Create upload directories
  - Initialize database schema
  - Start HTTP server on port 5000

**Frontend Routes (HTML Served):**
- `/` → `welcome.html` - Landing/order intake page
- `/ordini-estratti` → `ordini_estratti.html` - Extracted orders dashboard
- `/laser`, `/piega`, `/saldatura`, etc. → Station-specific phase tracking pages

**API Entry Points:**
- `/api/extract-pdf-data` POST - PDF file upload → order data extraction
- `/api/orders` POST/GET - Create or list orders
- `/api/orders/<id>/phase/<phase>/start` POST - Begin phase
- `/api/orders/<id>/phase/<phase>/complete-partial` POST - Mark articles complete for phase
- `/api/process-pdfs` POST - Batch process PDF folder

**PDF Processing Entry:**
- Location: `app/backend/pdf_parser.py` function `extract_pdf_content(filepath: str) -> dict`
- Triggers: Called by `/api/extract-pdf-data` route or batch processing scripts
- Responsibilities:
  - Read PDF file from disk
  - Extract text via PyPDF2
  - Detect format via pattern matching
  - Call appropriate parser
  - Return dict with cliente, numero_ordine, data_consegna, articoli

## Error Handling

**Strategy:** Try-catch at route level with JSON error responses; format detection includes silent fallback to generic parser.

**Patterns:**

**Route-Level Error Handling (`app.py`):**
```python
try:
    # Business logic
    order = OrderManager.create_order(...)
    return jsonify({'success': True, 'order_id': order.id}), 201
except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 400
```
- Location: `app/backend/app.py` lines 49-74 (create_order), lines 214-269 (extract_pdf_data)
- Returns 400 for invalid input, 404 for not found, 500 for server errors

**PDF Parser Fallback Chain:**
```
Try Docling OCR
  → Fallback: PyPDF2 text extraction
    → Try format-specific parser
      → Fallback: Generic intelligent parser
        → Return partial results if field extraction fails
```
- Location: `app/backend/pdf_parser.py` lines 20-68 (lazy-loaded Docling with fallback to PyPDF2)
- All 8 format parsers call `extract_generic_intelligent()` if no matches found

**Database Transaction Safety:**
```python
try:
    # Query, modify, commit
    session.commit()
except Exception as e:
    session.rollback()
    raise e
finally:
    session.close()
```
- Location: `app/backend/database.py` lines 27-62 (create_order), lines 244-306 (complete_phase_partial)
- Every method creates fresh session, always rolls back on error

## Cross-Cutting Concerns

**Logging:** Print statements to stdout with formatted headers (=== MARKERS ===). See `app/backend/app.py` lines 217-256 for PDF extraction logging.

**Validation:**
- Route level: Check file type (`.pdf`), validate JSON structure, check required fields
- Database level: Order and article creation validates quantity > 0, datetime formats

**Authentication:** Not implemented. System assumes single-site physical access control.

**File Storage:**
- PDFs: `app/uploads/pdfs/` - uploaded files named with original filename
- Drawings: `app/uploads/drawings/` - named as `{order_id}_{filename}`
- Database: `app/database/scheduler.db` - SQLite with all order/phase state

**Concurrency:** No explicit locking. SQLAlchemy handles session isolation at SQLite level. Designed for single-user-per-station concurrency model.

---

*Architecture analysis: 2026-02-19*

# External Integrations

**Analysis Date:** 2026-02-19

## APIs & External Services

**No External APIs Currently Integrated**
- System is fully self-contained
- No cloud service dependencies (AWS, Azure, GCP, etc.)
- No third-party SaaS integrations detected

## Data Storage

**Databases:**
- SQLite (embedded)
  - Location: `app/database/scheduler.db`
  - Connection: `sqlite:///[path]/scheduler.db` (local file-based)
  - Client: SQLAlchemy ORM
  - Tables: orders, order_files, processing_steps, order_notifications

**File Storage:**
- Local filesystem only
  - PDF uploads: `app/uploads/pdfs/`
  - Drawing files (DXF/images): `app/uploads/drawings/`
  - Both directories auto-created on startup at `app/backend/app.py:24-25`

**Caching:**
- None detected (no Redis, Memcached, or equivalent)
- Each request re-queries SQLite database
- Frontend has no persistent client-side caching strategy

## Authentication & Identity

**Auth Provider:**
- None - System is unauthenticated
  - No login/logout functionality
  - No user accounts
  - No authorization checks on API endpoints
  - All endpoints accessible without credentials
  - Operatore (operator) name is optional parameter in phase tracking, not authentication

## Monitoring & Observability

**Error Tracking:**
- None - No Sentry, Datadog, or equivalent service
- Errors logged to console via print statements

**Logs:**
- Console output only
  - Flask development server prints to stdout/stderr
  - Backend prints debug info to console (see `app/backend/app.py:217-268` PDF extraction logging)
  - No persistent log file configured
  - Verbose logging via `print()` and `sys.stdout.flush()` calls

## CI/CD & Deployment

**Hosting:**
- Local/on-premises deployment expected
- No integration with cloud platforms detected
- Can run on any system with Python 3.8+
- Gunicorn recommended for production deployment

**CI Pipeline:**
- None detected
- No GitHub Actions, GitLab CI, Jenkins, or equivalent
- No automated testing framework integration
- Manual testing via Python test scripts in `app/` directory

## Environment Configuration

**Required env vars:**
- No critical environment variables detected
- python-dotenv is installed but codebase does not require specific env vars
- All paths are relative to app directory
- Configuration is hard-coded in Python files:
  - Upload paths: `app/backend/app.py:19-22`
  - Database path: `app/backend/models.py:9`
  - Server port/host: `app/backend/app.py:383` (hardcoded to 0.0.0.0:5000)

**Secrets location:**
- `.env` file support available via python-dotenv
- No secrets detected in codebase
- Credentials/sensitive data should be stored in `.env` (which is in .gitignore)

## Webhooks & Callbacks

**Incoming:**
- None - No webhook endpoints defined
- All communication is request/response via REST API

**Outgoing:**
- None - No external callbacks or webhook deliveries
- System does not initiate outbound requests to external services

## Content Delivery

**Google Fonts:**
- Fonts loaded via CDN: `https://fonts.googleapis.com`
- Used in frontend HTML files:
  - `app/frontend/welcome.html` - Inter font family
  - `app/frontend/dashboard.html` - Inter font family
  - `app/frontend/laser.html` - Inter and JetBrains Mono fonts
  - `app/frontend/piega.html` - Inter and JetBrains Mono fonts
  - Other pages - Inter font family
- Preconnect headers for performance optimization

## API Endpoints Overview

**Order Management:**
- POST `/api/orders` - Create order with articles
- GET `/api/orders` - List all orders (filterable by cliente)
- GET `/api/orders/<order_id>` - Get order details
- PUT `/api/orders/<order_id>/articles` - Update articles

**Phase Tracking:**
- POST `/api/orders/<order_id>/phase/<phase>/start` - Start processing phase
- POST `/api/orders/<order_id>/phase/<phase>/complete` - Complete entire phase
- POST `/api/orders/<order_id>/phase/<phase>/complete-partial` - Complete phase for specific articles
- GET `/api/phase/<phase>/orders` - Get orders requiring a specific phase

**PDF Processing:**
- POST `/api/extract-pdf-data` - Extract data from uploaded PDF
- POST `/api/process-pdfs` - Batch process all PDFs in folder
- GET `/api/extracted-orders` - Get all orders extracted from PDFs

**File Management:**
- POST `/api/upload-drawing` - Upload DXF/drawing file

**Health:**
- GET `/api/health` - System health check

## PDF Extraction System

**Supported Formats (16 verified):**
1. DIVISIONE - DIVISIONE CUCINE
2-5. FOR-ORDINE - Sozzi Arredamenti S.p.A. (4 variants)
6. OAFA - DECA S.r.l.
7. OF_IMPORTAZIONE - Tecnoapp S.r.l.
8-11. ORDINE FORNITORE - AZA INTERNATIONAL (4 variants)
12-13. ORDINE LS - Abieffe Trading S.r.l. (2 variants)
14-15. ORDINE LS D_ACQUISTO - L.S. SRL (2 variants)
16. PO_BEBITALIA - B&B ITALIA S.p.A.

**Parsers Location:**
- `app/backend/pdf_parser.py` - Main dispatcher with Docling integration
- `app/backend/parsers_oafa.py` - OAFA format extraction
- `app/backend/parsers_for_ordine.py` - FOR-ORDINE format extraction
- `app/backend/parsers_divisione.py` - DIVISIONE format extraction
- `app/backend/parsers_po_bebitalia.py` - B&B Italia PO extraction
- `app/backend/parsers_for_ordine_aza.py` - AZA variants extraction
- `app/backend/parsers_ordine_ls.py` - LS format extraction
- `app/backend/parsers_generic.py` - Intelligent fallback parser
- `app/backend/parsers_markdown_tables.py` - Markdown table parsing (Docling output)

**Extraction Strategy:**
1. Primary: Docling conversion to markdown with table detection
2. Fallback: Format-specific regex parsers
3. Last resort: Generic intelligent parser with keyword matching

---

*Integration audit: 2026-02-19*

# Technology Stack

**Analysis Date:** 2026-02-19

## Languages

**Primary:**
- Python 3.8+ - Backend API, PDF processing, and data extraction logic
- HTML5 - Frontend pages and UI structure
- JavaScript (vanilla) - Client-side interactivity and API communication
- CSS3 - Styling and responsive design

## Runtime

**Environment:**
- Python runtime (local or server-based)
- WSGI application server (Gunicorn)

**Package Manager:**
- pip (Python Package Manager)
- Lockfile: requirements.txt present at `app/requirements.txt`

## Frameworks

**Core:**
- Flask 2.3.2 - Web framework and API server
- Flask-CORS 4.0.0 - Cross-Origin Resource Sharing support
- Gunicorn 21.2.0 - Production WSGI application server

**Database & ORM:**
- SQLAlchemy 2.0.19 - ORM for database operations
- SQLite - Embedded database (scheduler.db at `app/database/scheduler.db`)

**PDF Processing:**
- PyPDF2 3.0.1 - PDF text extraction
- pdfplumber 0.9.0 - Advanced PDF parsing
- Docling 2.2.0 - Advanced document understanding and conversion to markdown

**Document & Data:**
- pandas 2.0.3 - Data manipulation and analysis
- openpyxl 3.1.2 - Excel file handling
- ezdxf 1.9.11 - DXF/CAD file parsing

**Utilities:**
- Pillow 10.0.0 - Image processing and manipulation
- python-dotenv 1.0.0 - Environment variable loading from .env files

## Key Dependencies

**Critical:**
- Docling 2.2.0 - Document conversion to markdown format with high accuracy
- PyPDF2 3.0.1 - Fallback PDF text extraction when Docling unavailable
- pdfplumber 0.9.0 - Precision PDF parsing with table detection
- SQLAlchemy 2.0.19 - Database persistence layer

**Infrastructure:**
- Flask 2.3.2 - HTTP request handling and routing
- Flask-CORS 4.0.0 - Cross-origin request support for frontend
- Gunicorn 21.2.0 - Production server deployment

## Configuration

**Environment:**
- `.env` file support via python-dotenv (file present but contents not exposed)
- Database location: `app/database/scheduler.db`
- Upload folder: `app/uploads/`
  - PDFs: `app/uploads/pdfs/`
  - Drawings: `app/uploads/drawings/`
- Frontend folder: `app/frontend/`

**Application Configuration:**
- Flask debug mode available for development
- MAX_CONTENT_LENGTH: 50 MB (file upload limit) - set in `app/backend/app.py:15`
- CORS enabled globally
- Port: 5000 (default)
- Host: 0.0.0.0 (all interfaces)

**Build:**
- requirements.txt at `app/requirements.txt` - All Python dependencies listed
- Manual setup via pip install -r requirements.txt
- No build tool (webpack, vite, etc.) - frontend served as static HTML files

## Platform Requirements

**Development:**
- Python 3.8 or higher
- pip for package management
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Local filesystem for database and file uploads

**Production:**
- Python 3.8+
- Gunicorn WSGI server
- Database persistence (SQLite)
- 50 MB or larger available disk space per request
- Network access on port 5000 (configurable)

**System Requirements:**
- No external service dependencies (self-contained)
- Works offline with pre-installed dependencies
- File system access for PDF and DXF uploads

---

*Stack analysis: 2026-02-19*

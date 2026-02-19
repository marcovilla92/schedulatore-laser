# Codebase Concerns

**Analysis Date:** 2026-02-19

## Tech Debt

**Excessive Debug Logging in Production Code:**
- Issue: All endpoints in `app.py` and parsers contain extensive `print()` statements with emoji decorations for debugging. This clogs stdout and slows down response times.
- Files: `app/backend/app.py` (lines 217-267), `app/backend/pdf_parser.py` (lines 122-231), `app/backend/parsers_generic.py` (lines 17-27), and all parser modules
- Impact: Stdout pollution makes production monitoring difficult, performance degradation on high-volume requests, mixed concerns (business logic + debugging)
- Fix approach: Replace all `print()` calls with a proper logging framework (Python `logging` module). Keep debug-level logs hidden by default, configurable via environment variable

**Docling Integration Disabled and Dead Code:**
- Issue: `pdf_parser.py` has Docling as a hard-coded dependency but it's disabled (`_ensure_docling_loaded()` always returns False on line 28). The code still tries to load it on fallback but will never succeed.
- Files: `app/backend/pdf_parser.py` (lines 16-68, 71-111, 174-209)
- Impact: Misleading code paths, unnecessary imports in `requirements.txt`, wasted investigation time on "why Docling isn't working"
- Fix approach: Either enable Docling properly or remove all references. If enabling: implement proper lazy loading. If removing: delete lines 14-111 and simplify fallback logic

**Hardcoded Known Clients in Parser:**
- Issue: `parsers_for_ordine.py` lines 21-28 hardcodes PDF filenames and known clients. This doesn't scale and masks underlying parsing issues.
- Files: `app/backend/parsers_for_ordine.py` (lines 21-36)
- Impact: New PDF formats will fail parsing silently, errors are hidden, no audit trail of what was hardcoded vs. extracted
- Fix approach: Remove hardcoded mappings. Improve actual PDF text extraction logic instead. If needed, add a configuration file for known problematic PDFs with full traceability

**No Input Validation or Sanitization:**
- Issue: File uploads accept any filename without sanitization (`app.py` lines 241, 281-282). API endpoints don't validate JSON schema or sanitize file paths.
- Files: `app/backend/app.py` (lines 214-269, 271-291)
- Impact: Path traversal vulnerabilities possible, malicious filenames could corrupt uploads directory, user-supplied data used directly in file operations
- Fix approach: Implement whitelist validation for filenames, use UUID + safe extensions, validate JSON schema with marshmallow or pydantic, add rate limiting

**Overly Broad CORS Configuration:**
- Issue: `app.py` line 16: `CORS(app)` enables CORS globally without restrictions.
- Files: `app/backend/app.py` (line 16)
- Impact: Any domain can make requests to this API, potential for csrf attacks, information disclosure
- Fix approach: Configure CORS with explicit allowed origins: `CORS(app, origins=['http://localhost:5000', 'https://yourdomain.com'])`

**SQLite with check_same_thread=False:**
- Issue: `models.py` line 85: SQLite engine configured with `check_same_thread=False` for multi-threaded access, but Flask default debug mode is single-threaded.
- Files: `app/backend/models.py` (line 85)
- Impact: Database corruption risk if code ever runs with threaded workers (e.g., gunicorn), race conditions on concurrent writes not detected
- Fix approach: Use PostgreSQL for production, or if SQLite required, implement connection pooling and test with threaded workers

**No Error Recovery or Partial Failure Handling:**
- Issue: PDF extraction processes file but if parsing fails mid-way, no cleanup happens. Temp files could accumulate.
- Files: `app/backend/app.py` (lines 240-269), `app/backend/pdf_parser.py` (lines 114-231)
- Impact: Disk space accumulation, orphaned files, no way to retry failed extractions
- Fix approach: Use context managers or try/finally blocks to clean up temp files, implement retry logic with exponential backoff

---

## Known Bugs

**PDF Format Detection Fragile to Case Sensitivity:**
- Symptoms: Some PDFs fail to detect format if text contains mixed case markers (e.g., "Ordine fornitore" vs "ORDINE FORNITORE")
- Files: `app/backend/pdf_parser.py` (lines 234-297), `app/backend/parsers_for_ordine.py` (lines 95-100)
- Trigger: PDFs with non-standard capitalization in format markers
- Workaround: Ensure all regex searches use re.IGNORECASE flag, normalize text to upper() before matching

**JSON Column Default Uses Mutable List:**
- Symptoms: SQLAlchemy model `Order.articles` defaults to `list` instead of callable, causing all Order instances to share the same list object
- Files: `app/backend/models.py` (line 43)
- Trigger: Creating multiple orders without explicit articles array corrupts all previous orders
- Workaround: Change line 43 to `articles = Column(JSON, default=lambda: [])` to match line 37 pattern

**Article Index Out of Bounds on Partial Completion:**
- Symptoms: If client sends invalid article indices to `/api/orders/<id>/phase/<phase>/complete-partial`, no validation happens
- Files: `app/backend/app.py` (lines 157-164), `app/backend/database.py` (lines 236-306)
- Trigger: Frontend sends `article_indices=[0, 1, 999]` when order only has 3 articles
- Workaround: Add bounds checking in `complete_phase_partial()` before appending indices

**Timezone Awareness Issues:**
- Symptoms: Using `datetime.utcnow()` everywhere but no timezone info stored in database, causes comparison errors with timezone-aware datetimes
- Files: `app/backend/models.py` (lines 34, 81, 92), `app/backend/database.py` (lines 162, 184, 270)
- Trigger: Any integration with timezone-aware systems (e.g., frontend sending ISO timezone, cloud services)
- Workaround: Use `datetime.now(timezone.utc)` and ensure all datetime columns are timezone-aware

---

## Security Considerations

**Arbitrary File Upload Path Traversal:**
- Risk: Uploaded PDF filename could contain `../` sequences, allowing writes outside uploads directory
- Files: `app/backend/app.py` (lines 241, 281-282)
- Current mitigation: File extension check only (`.pdf` check on line 234)
- Recommendations:
  - Use `os.path.basename()` to strip directory traversal
  - Generate UUID-based filenames instead of trusting user input
  - Validate full path is within PDFS_FOLDER after file.save()

**No Authentication on Any Endpoint:**
- Risk: All API endpoints are publicly accessible without authentication
- Files: `app/backend/app.py` (all routes lines 32-364)
- Current mitigation: None
- Recommendations:
  - Add JWT or session-based authentication
  - Implement role-based access control (RBAC) for different operations
  - At minimum, add API key validation

**Sensitive Info Potentially Exposed in Error Messages:**
- Risk: Exception messages returned directly to client (`app.py` lines 74, 85, 96, 111, 150, 181, 210, 269, 291)
- Files: `app/backend/app.py`, `app/backend/database.py`
- Current mitigation: None
- Recommendations:
  - Log full exceptions server-side only
  - Return generic error messages to client ("An error occurred, ID: 12345")
  - Map error IDs to detailed logs for debugging

**SQL Injection via Raw Queries (if introduced later):**
- Risk: Current ORM prevents SQL injection, but codebase doesn't validate/document this
- Files: `app/backend/database.py` (uses SQLAlchemy ORM throughout - currently safe)
- Current mitigation: ORM usage blocks injection
- Recommendations:
  - Document ORM requirement in code comments
  - Add pre-commit hook to detect raw SQL strings
  - Consider sqlalchemy.orm type hints to enforce ORM usage

---

## Performance Bottlenecks

**Sequential PDF Processing in Batch Endpoint:**
- Problem: `/api/process-pdfs` processes all PDFs sequentially (line 319 in app.py)
- Files: `app/backend/app.py` (lines 302-364)
- Cause: Loop processes one PDF at a time, PyPDF2 extraction takes 0.5-1s per PDF
- Improvement path:
  - Implement concurrent processing with ThreadPoolExecutor (5-10 threads)
  - Add queue system (celery/RQ) for async batch jobs
  - Return job ID immediately, let frontend poll progress endpoint

**Full Text Extraction on Every Format Detection:**
- Problem: `pdf_parser.py` extracts full PDF text (lines 126-149) before detecting format, then may extract again if Docling is used
- Files: `app/backend/pdf_parser.py` (lines 125-209)
- Cause: Unclear conditional logic around Docling fallback causes double-extraction
- Improvement path:
  - Cache extracted text in memory during single request
  - Use first N pages only for format detection (e.g., first 5 pages)
  - Simplify Docling logic (currently disabled anyway)

**No Database Query Optimization:**
- Problem: `get_all_orders_dict()` loads all orders with all relationships into memory, no pagination
- Files: `app/backend/database.py` (lines 91-124)
- Cause: For 1000+ orders, this loads entire database
- Improvement path:
  - Add limit/offset pagination parameters
  - Add indexes on frequently queried columns (`cliente`, `status`, `data_consegna`)
  - Implement lazy loading only when needed

**Frontend Dashboard Auto-Refresh:**
- Problem: `ordini_estratti.html` likely auto-refreshes full data every N seconds without delta updates
- Files: `app/frontend/ordini_estratti.html` (not fully visible, but indicated in README)
- Cause: No indication of WebSocket or server-sent events, likely polling entire order list
- Improvement path:
  - Implement WebSocket for real-time updates
  - Add delta/diff API endpoints to fetch only changed orders
  - Reduce refresh interval or use user-triggered refresh

---

## Fragile Areas

**PDF Parser Format Detection Logic:**
- Files: `app/backend/pdf_parser.py` (lines 234-297)
- Why fragile: Detection relies on exact text markers ("DIVISIONE CUCINE", "ORDINE FORNITORE", "B&B ITALIA"). Any variation breaks detection. Multiple nested if statements with unclear precedence.
- Safe modification:
  - Add unit tests for each format with variations (mixed case, extra whitespace, missing markers)
  - Extract detection into separate class with clearer strategy pattern
  - Add logging of detected format confidence scores
- Test coverage: No test files found for format detection logic. This is critical.

**Database Session Management:**
- Files: `app/backend/database.py` (everywhere) and `app/backend/models.py` (line 89)
- Why fragile: Every method creates session locally, closes in finally block. No context manager pattern. Easy to accidentally leave sessions open or reuse closed sessions.
- Safe modification:
  - Implement context manager for sessions: `with get_session() as session:`
  - Add tests for session cleanup in error scenarios
  - Document session lifecycle in class docstring
- Test coverage: No session lifecycle tests found.

**Articoli/Articles JSON Column Storage:**
- Files: `app/backend/models.py` (line 43), `app/backend/database.py` (lines 386, 262-263)
- Why fragile: Storing unstructured JSON without schema. Client can send malformed article objects, no validation on shape. Index-based article references in `completed_articles` will break if articles array reordered.
- Safe modification:
  - Define ArticleSchema with required fields (name, code, qty, required_phases)
  - Validate articles on order creation
  - Use UUID article IDs instead of index-based references
- Test coverage: Only unit test needed, none found.

**Parser-Specific Hardcoded Logic:**
- Files: `app/backend/parsers_*.py` (7 different files)
- Why fragile: Each parser has custom regex and string matching for a specific PDF format. Changes to supplier PDFs (header reorder, font change) breaks extraction. New formats require new parser file.
- Safe modification:
  - Implement format-agnostic extraction (use Docling/pytorch for layout understanding instead of regex)
  - Build parser config in JSON/YAML instead of hardcoded regex
  - Add test PDF samples in version control with expected extraction results
- Test coverage: test_all_16_detailed.py exists but not integrated into CI/CD.

---

## Scaling Limits

**SQLite File-Based Database:**
- Current capacity: ~100-1000 orders before slowdown (typical SQLite limit is ~10GB)
- Limit: Single-file bottleneck, no read replicas, concurrent writes serialize, max 5 concurrent connections
- Scaling path:
  - Migrate to PostgreSQL for multi-concurrent-write scenarios
  - Add connection pooling (pgbouncer)
  - Implement read replicas for reporting

**Single Flask Process:**
- Current capacity: ~10-50 req/s depending on PDF complexity
- Limit: Debug mode runs single-threaded, no load balancing
- Scaling path:
  - Use gunicorn with 4x CPU workers: `gunicorn -w 4 app:app`
  - Put nginx or HAProxy in front for load balancing
  - Add Redis for session state if multi-worker needed

**PDF Processing Memory:**
- Current capacity: Entire PDF loaded into memory (PyPDF2 loads full document)
- Limit: Large PDFs (>50MB) could cause memory spikes, 16 concurrent extractions could use >2GB RAM
- Scaling path:
  - Stream PDF processing with pdfplumber instead of PyPDF2
  - Process pages in chunks
  - Implement memory monitoring and queue rejection on high load

**File Storage on Local Filesystem:**
- Current capacity: Filesystem limit (typically 100k+ files per directory, but slower above 10k)
- Limit: `/app/uploads` directory will accumulate files, no retention policy, no cleanup
- Scaling path:
  - Implement S3-compatible storage (MinIO, AWS S3)
  - Add file expiration policy (e.g., delete PDFs after 30 days)
  - Implement directory structure by date: `/uploads/2026-02-19/...`

---

## Dependencies at Risk

**PyPDF2 - Unmaintained Library:**
- Risk: PyPDF2 is known for bugs in complex PDF handling. Last major update 2022. Community fork pdfplumber is more active.
- Impact: PDF extraction failures on edge cases, security vulnerabilities if discovered
- Migration plan:
  - Consider replacing with pdfplumber (which is already in requirements.txt but not used for text extraction)
  - Or use PyMuPDF (fitz) for more robust extraction
  - Docling was attempted but disabled - should complete that migration or remove

**Flask Development Server in Production:**
- Risk: Debug mode is on in line 383: `app.run(debug=True, host='0.0.0.0', port=5000)`
- Impact: Reloader restarts app on file changes, slowdown, potential security exposure of /console endpoint
- Migration plan:
  - Change to `app.run(debug=False, ...)` for production
  - Use gunicorn instead: `gunicorn -w 4 app:app`
  - Move debug setting to environment variable: `debug=os.getenv('FLASK_DEBUG', False)`

**SQLAlchemy 2.0 API Migration Incomplete:**
- Risk: Code uses some SQLAlchemy 2.0 syntax but mixed with 1.x patterns. Future minor versions may break compatibility.
- Impact: Warnings in logs, potential breaking changes in SQLAlchemy 2.1+
- Migration plan:
  - Audit all ORM usage for 1.x vs 2.0 patterns
  - Use sqlalchemy.orm.Session instead of sessionmaker directly
  - Enable SQLAlchemy warnings: `import warnings; warnings.filterwarnings('error', category=DeprecationWarning)`

---

## Missing Critical Features

**No Rate Limiting:**
- Problem: Any client can hammer `/api/process-pdfs` with 100 concurrent requests
- Blocks: Can't scale safely, DDoS vulnerable
- Implementation: Add Flask-Limiter with Redis backend

**No Audit Trail:**
- Problem: No logs of who created/modified orders, when PDFs were extracted, what errors occurred
- Blocks: Regulatory compliance (if processing business-critical data), debugging production issues
- Implementation: Add database audit table with trigger logging all Order changes

**No Data Validation:**
- Problem: Articles can be created with missing fields, dates can be invalid, quantities can be negative
- Blocks: Data quality issues cascade through system
- Implementation: Use pydantic models to validate all API payloads and database objects

**No Backup/Disaster Recovery:**
- Problem: SQLite database on local filesystem with no backups
- Blocks: Data loss = complete system failure, no recovery path
- Implementation: Implement daily automated SQLite backups to S3, implement restore procedure

**No Multi-Tenant Support:**
- Problem: System assumes single company using it
- Blocks: Can't be sold as SaaS or used by multiple divisions
- Implementation: Add tenant_id to all models, filter all queries by tenant

---

## Test Coverage Gaps

**PDF Format Detection Not Unit Tested:**
- What's not tested: `detect_pdf_format()` function with edge cases (partial markers, case variations, mixed formats)
- Files: `app/backend/pdf_parser.py` (lines 234-297)
- Risk: Format detection regression will break extraction for entire format family silently
- Priority: **High** - this is business-critical

**Parser Individual Logic Not Tested:**
- What's not tested: Each parser's internal functions (e.g., `extract_cliente_for_ordine`, `extract_articoli_for_ordine`)
- Files: `app/backend/parsers_*.py` (all 7 parsers)
- Risk: Parser changes could break extraction for specific fields without knowing it
- Priority: **High** - extraction accuracy is key feature

**Database Concurrency Not Tested:**
- What's not tested: Multiple simultaneous requests modifying same order, race conditions in `complete_phase_partial()`
- Files: `app/backend/database.py` (lines 236-306)
- Risk: Data corruption in high-load scenarios
- Priority: **Medium** - only matters if scaling

**API Response Validation Not Tested:**
- What's not tested: API returns correct schema, error responses have proper format
- Files: `app/backend/app.py` (all routes)
- Risk: Frontend breaks on unexpected response format, no regression protection
- Priority: **Medium** - helps frontend stability

**Error Scenarios Not Tested:**
- What's not tested: What happens if PDF is corrupted, database is down, file permissions denied
- Files: Entire backend
- Risk: Unknown behavior in production, no graceful error handling
- Priority: **Low** - reactive rather than proactive

---

*Concerns audit: 2026-02-19*

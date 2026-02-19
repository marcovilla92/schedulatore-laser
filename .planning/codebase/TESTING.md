# Testing Patterns

**Analysis Date:** 2026-02-19

## Test Framework

**Runner:**
- No formal test framework configured (pytest/unittest not in use)
- Tests are standalone Python scripts executed directly with `python script_name.py`
- Config: No pytest.ini, setup.cfg, or tox.ini files present

**Assertion Library:**
- No external assertion library; simple `if/else` checks with print output
- Manual comparison: `if success: print("[OK]")` else `print("[FAIL]")`
- Direct equality checks: `if len(result['articoli']) == 13 and sum(...) == 865:`

**Run Commands:**
```bash
python test_all_16_final.py              # Run comprehensive test suite
python test_api_integration.py           # Test API endpoints with real PDFs
python test_quick.py                     # Quick test via HTTP requests
python test_[format]_parser.py           # Format-specific parser tests
```

## Test File Organization

**Location:**
- Test files co-located in project root (`/c/Users/Marco/Documents/VisualStudio/Schedulatore/schedulatore-laser/app/`)
- Not separated into dedicated test directory
- Tests exist alongside source code in same directory

**Naming:**
- Inconsistent: Mix of `test_*.py` prefix and `*_test.py` suffix
- Examples: `test_all_16_final.py`, `test_api_integration.py`, `test_divisione_parser.py`, `batch_test_ordini.py`
- Descriptive suffixes: `test_[feature]_[variant].py` (e.g., `test_docling_parsing.py`, `test_frontend_integration.py`)

**Structure:**
- Test files in app root directory:
```
app/
├── backend/                  # Production code
│   ├── app.py
│   ├── models.py
│   ├── database.py
│   ├── pdf_parser.py
│   └── parsers_*.py
├── uploads/                  # Generated test outputs
├── test_all_16_final.py
├── test_api_integration.py
├── test_divisione_parser.py
└── ... (40+ test files)
```

## Test Structure

**Suite Organization:**
- No formal test suite structure (no unittest.TestCase or pytest classes)
- Scripts execute test cases sequentially with print-based reporting
- Tests operate on hardcoded file paths (typically local ORDINI folder)

**Example from `test_all_16_final.py`:**
```python
#!/usr/bin/env python
"""Full test of all 16 PDFs - WITHOUT SLOW DOCLING"""

from backend.pdf_parser import extract_pdf_content
import os

all_pdfs = [
    ('C:/Users/39334/Documents/ORDINI/300000946.pdf', 'DIVISIONE 300000946'),
    ('C:/Users/39334/Documents/ORDINI/FOR-ORDINE_0000173_00(50359).pdf', 'FOR-ORDINE 0000173'),
    # ... more test files
]

success_count = 0
fail_count = 0
results = []

for filepath, name in all_pdfs:
    if not os.path.exists(filepath):
        print(f"\n[ERROR] File not found: {name}")
        fail_count += 1
        continue

    try:
        result = extract_pdf_content(filepath)
        cliente = result.get('cliente', '')
        ordine = result.get('numero_ordine', '')
        articoli = result.get('articoli', [])

        # Success criteria: cliente and ordine present, at least 1 article
        success = cliente and ordine and len(articoli) >= 1

        if success:
            print(f"[OK] {name:40s} | Cliente: {cliente:30s} | Ordine: {ordine:10s} | Art: {len(articoli)}")
            success_count += 1
        else:
            print(f"[FAIL] {name:40s} | Cliente: {str(cliente)[:30]:30s} | Ordine: {ordine:10s} | Art: {len(articoli)}")
            fail_count += 1

        results.append({
            'name': name,
            'cliente': cliente,
            'ordine': ordine,
            'articoli': len(articoli),
            'success': success
        })

    except Exception as e:
        print(f"[ERROR] {name:40s} - {str(e)[:50]}")
        fail_count += 1

print("\n" + "=" * 100)
print(f"RESULTS: {success_count}/16 SUCCESS ({success_count*100//16}%)")
```

**Patterns:**
- Setup: Initialize test data (file paths, expected values)
- Execution: Call function under test and capture results
- Assertion: Manual boolean checks with formatted print output
- Teardown: None explicit; test isolation minimal

## Mocking

**Framework:** No mocking framework in use (unittest.mock not imported)

**Patterns:** None detected
- Tests call actual PDF files from disk
- Database tests manipulate actual SQLite database
- No mocks for external dependencies

**What to Test:**
- Parser accuracy: Client name, order number, delivery date, article extraction
- API endpoints: HTTP status codes, JSON response structure, data persistence
- PDF format detection: Router correctly identifies format and calls appropriate parser

**What NOT to Mock:**
- File system: Tests use real PDF files
- Database: Tests use actual SQLite database instance
- External libraries: PyPDF2, docling (when available) called directly

## Fixtures and Factories

**Test Data:**
- Hardcoded file paths to real PDF files stored locally
- Example from `test_api_integration.py`:
```python
ordini_folder = 'C:/Users/39334/Documents/ORDINI'

pdf_files = sorted([f for f in os.listdir(ordini_folder) if f.lower().endswith('.pdf')])

for idx, pdf_file in enumerate(pdf_files[:8], 1):
    try:
        pdf_path = os.path.join(ordini_folder, pdf_file)
        data = extract_pdf_content(pdf_path)
        is_success = bool(data.get('numero_ordine'))
        # ... assertions
    except Exception as e:
        error_count += 1
```

- HTTP test from `test_quick.py`:
```python
tests = [
    ('uploads/pdfs/OAFA202600125.pdf', 'OAFA'),
    ('uploads/pdfs/ORDINE FORNITORE 57-AC del 30-01-2026  L S S R L.pdf', 'FOR-ORDINE'),
    ('uploads/pdfs/Ordine LS N°172.pdf', 'LS'),
]

for pdf_path, name in tests:
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': f}
            r = requests.post('http://localhost:5000/api/extract-pdf-data', files=files, timeout=60)
        # ... assertions
    except Exception as e:
        print(f"  ❌ {e}")
```

**Location:**
- Test fixtures stored in local file system:
  - PDFs: `C:/Users/39334/Documents/ORDINI/` (hardcoded paths)
  - Local uploads: `uploads/pdfs/` (relative path from app root)
  - Database: `app/database/scheduler.db` (SQLite file)

## Coverage

**Requirements:** No coverage requirements enforced

**View Coverage:**
- Not applicable; no coverage tool configured
- No coverage.py or pytest-cov integration detected

## Test Types

**Unit Tests:**
- Parser tests: Individual `test_[format]_parser.py` files test each PDF format parser
- Scope: Extract specific fields (cliente, numero_ordine, articoli) from PDF text
- Approach: Load PDF, extract text, call parser function, assert output structure and values
- Example: `test_divisione_parser.py` expects 13 articles with 865 total units

**Integration Tests:**
- API integration: `test_api_integration.py`, `test_api_http.py` test end-to-end PDF → API → database
- Scope: HTTP endpoints, file upload handling, PDF processing, response format
- Approach: Send POST request with PDF file, verify HTTP status and JSON response
- Database integration: OrderManager CRUD operations tested via API

**E2E Tests:**
- Frontend tests: `test_frontend_integration.py` tests web UI interaction
- Scope: Dashboard pages, order display, phase tracking
- Framework: No E2E framework; appears to be manual browser testing via screenshots
- Not automated in code; test evidence is screenshots (dashboard-page.png, etc.)

## Common Patterns

**Async Testing:**
- Not used; no async/await patterns in test code
- HTTP requests use requests library (blocking)
- Flask routes are synchronous

**Error Testing:**
```python
# From test_api_integration.py
try:
    result = extract_pdf_content(filepath)
    # ... success path
except Exception as e:
    error_count += 1
    print(f"✗ [{idx}] {pdf_file[:45]:45s} | ERRORE: {str(e)[:45]}")
```

**Success/Failure Reporting:**
```python
# Explicit boolean check with branching output
success = cliente and ordine and len(articoli) >= 1

if success:
    print(f"[OK] {name:40s} | Cliente: {cliente:30s}")
    success_count += 1
else:
    print(f"[FAIL] {name:40s}")
    fail_count += 1

# Summary statistics
print(f"RESULTS: {success_count}/16 SUCCESS ({success_count*100//16}%)")
```

**Test Isolation:**
- Minimal isolation; tests share database and file system state
- Database tests modify `app/database/scheduler.db`
- Tests can interfere with each other if run sequentially
- No transaction rollback or cleanup between tests

## Test Execution Notes

**Entry Point:** `test_all_16_final.py` appears to be primary validation test
- Tests 16 different PDF formats in sequence
- Reports pass/fail count with percentage
- Validating 100% accuracy on extraction from 16 formats

**Local Dependencies:**
- Tests hardcoded to local user paths: `C:/Users/39334/Documents/ORDINI/`
- Must run on development machine with specific folder structure
- Not portable across machines or CI/CD environments

**Test Data Quality:**
- Real-world PDF samples used (not synthetic test data)
- 40+ test variants suggest iterative development with continuous validation
- Focus on parser accuracy across diverse PDF format variations

---

*Testing analysis: 2026-02-19*

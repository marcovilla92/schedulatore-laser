# Coding Conventions

**Analysis Date:** 2026-02-19

## Naming Patterns

**Files:**
- Snake case: `parsers_divisione.py`, `pdf_parser.py`, `database.py`
- Format-specific parsers: `parsers_[format_name].py` (e.g., `parsers_oafa.py`, `parsers_for_ordine.py`)
- Test files: `test_[feature_name].py` or `[feature_name]_test.py` (inconsistent usage, many test variants)
- Backend module organization: `backend/app.py`, `backend/models.py`, `backend/database.py`

**Functions:**
- Snake case: `extract_pdf_content()`, `create_order()`, `get_order_details()`
- Public functions: Descriptive names starting with action verb: `extract_*`, `create_*`, `get_*`, `update_*`, `start_*`, `complete_*`
- Private functions: Prefixed with underscore: `_extract_cliente()`, `_extract_articoli_from_table()`, `_ensure_docling_loaded()`
- Parser functions: Standardized pattern: `extract_[format_name]()` → returns dict with structure `{cliente, numero_ordine, data_consegna, data_ricezione, articoli}`

**Variables:**
- Snake case: `order_id`, `cliente`, `data_consegna`, `articles`, `required_phases`
- Italian terms used for domain-specific variables: `cliente` (customer), `data_consegna` (delivery date), `articoli` (articles/items), `operatore` (operator)
- Constants: UPPER_CASE with underscores: `UPLOAD_FOLDER`, `DATABASE_URL`, `MAX_CONTENT_LENGTH`
- Boolean prefixes: `is_success`, `success`, `completed_articles`

**Types:**
- Type hints used in function signatures: `def extract_pdf_content(filepath: str) -> dict:`
- Class names: PascalCase: `Order`, `OrderFile`, `ProcessingStep`, `OrderNotification`, `OrderManager`, `OrderStatus`, `ProcessingPhase`
- Enum classes: PascalCase with UPPER_CASE values: `OrderStatus.RICEVUTO`, `ProcessingPhase.LASER`

## Code Style

**Formatting:**
- No explicit formatter detected (no `.black`, `.prettier`, or linting config files)
- Imports appear manually formatted
- Indentation: 4 spaces (Python standard)
- Max line length: Not enforced; some lines exceed 100 characters

**Linting:**
- No linting configuration files detected (no `.pylintrc`, `.flake8`, `eslint.config.js`)
- Code quality appears informal with some style inconsistencies

## Import Organization

**Order:**
1. Standard library imports: `import os`, `import sys`, `from datetime import datetime`
2. Third-party library imports: `from flask import Flask`, `import PyPDF2`, `from sqlalchemy import...`
3. Local relative imports: `from .models import`, `from .database import`, `from .pdf_parser import`

**Path Aliases:**
- No explicit path aliases detected in codebase
- Relative imports used throughout: `from .models import`, `from .database import OrderManager`
- Backend module structured with explicit `__init__.py` in `/c/Users/Marco/Documents/VisualStudio/Schedulatore/schedulatore-laser/app/backend/`

**Example from `app.py`:**
```python
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path

# Importa moduli locali
from .models import initialize_database
from .database import OrderManager
from .pdf_parser import extract_pdf_content
```

## Error Handling

**Patterns:**
- Try-except wrapping in Flask routes with generic Exception catching:
```python
try:
    data = request.get_json()
    order = OrderManager.create_order(...)
    return jsonify({'success': True, ...}), 201
except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 400
```

- HTTP status codes: 201 (created), 200 (success), 404 (not found), 400 (bad request), 500 (server error)
- Error response format: `{'error': str(e)}` or `{'success': False, 'error': str(e)}`
- Fallback patterns in parsers: Try primary method, then fallback to alternate method (e.g., Pattern matching → Markdown parser → generic intelligent parser)
- Print-based debugging: Extensive use of `print()` and `sys.stdout.flush()` for debugging output with prefixes like `[PDF]`, `[ERROR]`, `[OK]`, `[WARNING]`

## Logging

**Framework:** Native `print()` statements with flush() calls (not a logging framework)

**Patterns:**
- Prefixed output: `print("[PDF] ...")`, `print("[PARSER] ...")`, `print("[OK] ...")`, `print("[WARNING] ...")`
- Progress tracking: Incremental output in extraction functions showing processing steps
- Print-based tracing in parsers: Each parser outputs its detection results and fallback behavior
- sys.stdout.flush() after important messages for immediate output visibility

**Example from `parsers_generic.py`:**
```python
print("\n   [PARSER] PARSER GENERICO INTELLIGENTE")
print("   " + "="*70)
print(f"\n   [DATA] TESTO RICEVUTO (primi 1500 caratteri):")
print("   " + "-"*70)
print(text[:1500])
sys.stdout.flush()
```

## Comments

**When to Comment:**
- Explain parser selection logic and why a particular format was chosen
- Document multi-format support and fallback strategies
- Clarify regex patterns that extract specific data fields
- Note workarounds or hardcoded values with business logic explanation
- Flag experimental or disabled code sections (e.g., "TEMPORARILY DISABLED FOR TESTING")

**JSDoc/TSDoc:**
- Python docstrings used for public functions: triple-quoted strings immediately after function definition
- Docstring patterns: Brief description on first line, then detailed explanation
- Multi-line docstrings document function purpose, parameters in description, and return value

**Example from `pdf_parser.py`:**
```python
def extract_pdf_content(filepath: str) -> dict:
    """
    Estrae dati dal PDF riconoscendo automaticamente il formato
    Supporta: OAFA, FOR-ORDINE, DIVISIONE, PO_BEBITALIA

    STRATEGIA: PyPDF2 PRIMA (veloce), Docling SOLO se needful (fallback)
    """
```

**Example from `database.py`:**
```python
@staticmethod
def create_order(cliente: str, data_consegna: str, articles: list = None,
                 required_phases: list = None, preventivo_minuti: int = 0,
                 note: str = "") -> Order:
    """
    Crea un nuovo ordine con articoli

    articles = [
        {"name": "Staffa A", "code": "SA-001", "qty": 50,
         "required_phases": ["LASER", "PIEGA", "SALDATURA"]},
        ...
    ]
    """
```

## Function Design

**Size:** Functions are typically small to medium (10-40 lines)
- Parser helper functions: Extract single field per function (e.g., `extract_cliente_*`, `extract_numero_ordine_*`)
- Database operations: Encapsulated in OrderManager static methods (30-50 lines each)
- Flask routes: Handle HTTP logic and call OrderManager for persistence (10-20 lines)

**Parameters:**
- Named parameters with defaults: `def extract_pdf_content(filepath: str) -> dict:`
- Optional parameters use `= None` or empty collections: `articles: list = None`, `required_phases: list = None`
- Type hints consistently used in all function signatures

**Return Values:**
- Parser functions return dictionaries with consistent structure:
```python
{
    'cliente': str,
    'numero_ordine': str,
    'data_consegna': str (ISO format),
    'data_ricezione': str (ISO format),
    'articoli': list[dict]
}
```
- Article structure: `{'code': str, 'name': str, 'qty': int, 'price': float (optional)}`
- API responses: JSON-serializable dicts with `success` boolean and optional `error`/`data` keys
- Database operations return Order objects or dicts with full details

## Module Design

**Exports:**
- Main entry points: `extract_pdf_content()` from `pdf_parser.py` (dispatches to specific parsers)
- Database layer: `OrderManager` class with static methods for all CRUD operations
- Parser modules: Each `parsers_[format].py` exports one main function `extract_[format]()`

**Barrel Files:**
- No explicit barrel files (index.py) detected
- Backend imports structured as relative imports from specific modules: `from .models import`, `from .database import`
- Module dependencies flow: `app.py` → `pdf_parser.py` → specific parsers; `app.py` → `database.py` → `models.py`

---

*Convention analysis: 2026-02-19*

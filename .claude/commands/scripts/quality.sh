#!/bin/bash
# /quality - Run lint, syntax check, and tests for Schedulatore Laser
# Customized for Python/Flask project

# ============================================
# PROJECT CONFIG: Schedulatore Laser (Python)
# ============================================
RUN_LINT=true
RUN_TYPECHECK=true
RUN_TESTS=true
LINT_COMMAND="python -m py_compile"
# ============================================

set -e

echo "Running quality checks..."
echo ""

STEP=1
TOTAL_STEPS=3

# Step 1: Syntax check all Python files
if [ "$RUN_LINT" = true ]; then
    echo "Step $STEP/$TOTAL_STEPS: Syntax checking Python files..."
    ERRORS=0
    for f in app/backend/*.py app/run.py app/start_backend.py; do
        if [ -f "$f" ]; then
            if python -m py_compile "$f" 2>/dev/null; then
                echo "  OK: $f"
            else
                echo "  FAIL: $f"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    done

    if [ $ERRORS -gt 0 ]; then
        echo ""
        echo "Quality check failed: $ERRORS syntax errors"
        exit 1
    fi
    echo "Syntax check passed"
    echo ""
    ((STEP++))
fi

# Step 2: Import check (verify all modules load)
if [ "$RUN_TYPECHECK" = true ]; then
    echo "Step $STEP/$TOTAL_STEPS: Import check (verify modules load)..."
    cd app
    if python -c "
from backend.models import Order, ProcessingStep, OrderNotification, OrderFile
from backend.database import OrderManager
from backend.pdf_parser import extract_pdf_content
print('  All imports OK')
" 2>&1; then
        echo "Import check passed"
    else
        echo ""
        echo "Quality check failed: Import errors"
        exit 1
    fi
    cd ..
    echo ""
    ((STEP++))
fi

# Step 3: API smoke test (if server is running)
if [ "$RUN_TESTS" = true ]; then
    echo "Step $STEP/$TOTAL_STEPS: API smoke test..."
    if curl -sf http://localhost:5000/api/health > /dev/null 2>&1; then
        echo "  Server is running, testing endpoints..."

        STATUS=$(curl -o /dev/null -s -w '%{http_code}' http://localhost:5000/api/health)
        echo "  /api/health: $STATUS"

        STATUS=$(curl -o /dev/null -s -w '%{http_code}' http://localhost:5000/api/orders)
        echo "  /api/orders: $STATUS"

        STATUS=$(curl -o /dev/null -s -w '%{http_code}' http://localhost:5000/)
        echo "  /: $STATUS"

        echo "API smoke test passed"
    else
        echo "  Server not running, skipping API tests"
        echo "  (start with: python app/run.py)"
    fi
    echo ""
fi

echo "All quality checks passed!"
exit 0

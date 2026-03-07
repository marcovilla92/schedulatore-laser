#!/bin/bash
# ============================================================
# SCHEDULATORE LASER — Script avvio macOS / Linux
# ============================================================
# Usa Python 3.10+ (cerca Homebrew 3.12 prima del system Python)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔════════════════════════════════════════╗"
echo "║   SCHEDULATORE LASER - BACKEND START   ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Cerca Python 3.10+ in ordine di preferenza
PYTHON=""
for candidate in \
    /opt/homebrew/bin/python3.12 \
    /opt/homebrew/bin/python3.11 \
    /opt/homebrew/bin/python3.10 \
    /usr/local/bin/python3.12 \
    /usr/local/bin/python3.11 \
    /usr/local/bin/python3.10 \
    python3.12 python3.11 python3.10 python3
do
    if command -v "$candidate" &>/dev/null; then
        VERSION=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [ "$MAJOR" -gt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ]; }; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERRORE] Nessun Python 3.10+ trovato nel sistema."
    echo "[INFO]   Su macOS installa con: brew install python@3.12"
    exit 1
fi

echo "[OK] Python: $PYTHON ($("$PYTHON" --version 2>&1))"
echo ""

# Installa dipendenze se necessario
if [ -f "requirements.txt" ]; then
    echo "[*] Verifica dipendenze..."
    "$PYTHON" -m pip install -q -r requirements.txt
    echo "[OK] Dipendenze OK"
    echo ""
fi

echo "[*] Avvio server su http://localhost:5000"
echo "[INFO] Premi CTRL+C per fermare"
echo ""

exec "$PYTHON" run.py

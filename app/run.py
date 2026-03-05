#!/usr/bin/env python
"""
Launcher per SCHEDULATORE LASER backend
Avvia il server Flask sulla porta 5000
"""

import sys
import os

# Aggiungi la cartella app al path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")  # Carica app/.env (contiene GEMINI_API_KEY)

# Importa app dal backend
from backend.app import app
from backend.models import initialize_database

if __name__ == '__main__':
    # Inizializza database
    initialize_database()

    # Beta: debug=False per stabilità
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # Avvia Flask
    print("[START] Avvio SCHEDULATORE LASER su porta 5000")
    print("[INFO] Accedi via browser: http://localhost:5000")
    print(f"[INFO] Debug mode: {'ON' if debug_mode else 'OFF'}")
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)

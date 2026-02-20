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
    
    # Avvia Flask
    print("[START] Avvio SCHEDULATORE LASER su localhost:5000")
    print("[INFO] Accedi via browser: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)

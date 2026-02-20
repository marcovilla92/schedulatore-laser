#!/usr/bin/env python
"""Script per avviare il backend Flask"""
import sys
import os

# Aggiungi la cartella app al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(os.path.abspath(__file__)).parent / ".env")  # Carica app/.env

print("🚀 Caricamento backend...", flush=True)

try:
    from backend.app import app
    print("✅ Backend caricato con successo!", flush=True)
    
    # Avvia Flask
    print("📡 Avvio Flask server...", flush=True)
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False  # Disabilita auto-reload per evitare problemi
    )
except Exception as e:
    print(f"❌ ERRORE: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

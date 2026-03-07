#!/usr/bin/env python
"""
Launcher per SCHEDULATORE LASER backend
Avvia il server Flask sulla porta 5000
"""

import sys
import os
import threading
import time

# Aggiungi la cartella app al path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")  # Carica app/.env (contiene GEMINI_API_KEY)

# Importa app dal backend
from backend.app import app
from backend.models import initialize_database

# Intervallo backup in secondi (default: 1 ora, configurabile via env)
BACKUP_INTERVALLO = int(os.environ.get('BACKUP_INTERVALLO_SECONDI', 3600))
# Intervallo export JSON in secondi (default: 24 ore)
EXPORT_INTERVALLO = int(os.environ.get('EXPORT_INTERVALLO_SECONDI', 86400))


def _loop_backup():
    """Thread daemon: esegue backup orario del database."""
    from backup_db import backup, integrity_check
    time.sleep(60)  # Attende 1 minuto dopo l'avvio prima del primo backup
    while True:
        try:
            integrity_check()
            backup(motivo='schedulato')
        except Exception as e:
            print(f'[BACKUP] Errore nel thread schedulato: {e}')
        time.sleep(BACKUP_INTERVALLO)


def _loop_export_json():
    """Thread daemon: esegue export JSON giornaliero di tutti gli ordini."""
    time.sleep(120)  # Attende 2 minuti dopo l'avvio
    while True:
        try:
            _esegui_export_json()
        except Exception as e:
            print(f'[EXPORT] Errore nel thread export JSON: {e}')
        time.sleep(EXPORT_INTERVALLO)


def _esegui_export_json():
    """Esporta tutti gli ordini in un file JSON nella cartella database/exports."""
    import json
    from backend.database import OrderManager
    from pathlib import Path

    export_dir = Path(__file__).parent / 'database' / 'exports'
    export_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    export_path = export_dir / f'ordini_{ts}.json'

    ordini = OrderManager.get_all_orders_dict()
    with open(export_path, 'w', encoding='utf-8') as f:
        json.dump(ordini, f, ensure_ascii=False, indent=2, default=str)

    size_kb = export_path.stat().st_size // 1024
    print(f'[EXPORT] JSON salvato: {export_path.name} ({size_kb} KB, {len(ordini)} ordini)')

    # Mantieni solo gli ultimi 30 export
    import glob
    files = sorted(glob.glob(str(export_dir / 'ordini_*.json')))
    for old in files[:-30]:
        os.remove(old)


if __name__ == '__main__':
    # Inizializza database
    initialize_database()

    # Avvia thread backup orario (daemon: si chiude con il processo principale)
    t_backup = threading.Thread(target=_loop_backup, daemon=True, name='backup-scheduler')
    t_backup.start()
    print(f'[START] Thread backup schedulato ogni {BACKUP_INTERVALLO//60} minuti')

    # Avvia thread export JSON giornaliero
    t_export = threading.Thread(target=_loop_export_json, daemon=True, name='export-scheduler')
    t_export.start()
    print(f'[START] Thread export JSON schedulato ogni {EXPORT_INTERVALLO//3600} ore')

    # Beta: debug=False per stabilità
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # Avvia Flask
    print("[START] Avvio SCHEDULATORE LASER su porta 5000")
    print("[INFO] Accedi via browser: http://localhost:5000")
    print(f"[INFO] Debug mode: {'ON' if debug_mode else 'OFF'}")
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)

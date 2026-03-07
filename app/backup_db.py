"""
backup_db.py — Backup automatico del database SQLite

Funzionalità:
  - Backup a caldo con SQLite Online Backup API (sicuro anche con server attivo)
  - Rotazione automatica: mantiene gli ultimi MAX_BACKUPS backup locali
  - Backup remoto opzionale su NAS/secondo PC (configura BACKUP_REMOTO_PATH in .env)
  - Eseguibile manualmente: python backup_db.py

Configurazione via variabili d'ambiente in app/.env:
  BACKUP_MAX_COPIE=30           (default: 30)
  BACKUP_REMOTO_PATH=\\NAS\bk   (default: disabilitato)
"""

import sqlite3
import shutil
import os
import glob
import time
from pathlib import Path

# Percorsi
_HERE = Path(__file__).parent
DB_PATH = _HERE / 'database' / 'scheduler.db'
BACKUP_DIR = _HERE / 'database' / 'backups'

# Configurazione da env (con default)
MAX_BACKUPS = int(os.environ.get('BACKUP_MAX_COPIE', 30))
BACKUP_REMOTO_PATH = os.environ.get('BACKUP_REMOTO_PATH', '').strip()


def backup(motivo: str = 'schedulato') -> str | None:
    """
    Esegue un backup a caldo del database.

    Usa l'SQLite Online Backup API: sicuro anche con il server Flask attivo,
    non richiede lock esclusivi e non interrompe le operazioni in corso.

    Args:
        motivo: etichetta nel nome file (es: 'schedulato', 'manuale', 'pre_migrazione')

    Returns:
        Path del file di backup creato, oppure None in caso di errore.
    """
    if not DB_PATH.exists():
        print(f'[BACKUP] Database non trovato: {DB_PATH}')
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f'scheduler_{motivo}_{ts}.db'

    try:
        # SQLite Online Backup API — copia consistente senza bloccare il server
        src_conn = sqlite3.connect(str(DB_PATH))
        dst_conn = sqlite3.connect(str(dst))
        src_conn.backup(dst_conn, pages=100)  # pages=100: copia in chunk da 100 pagine
        dst_conn.close()
        src_conn.close()

        size_kb = dst.stat().st_size // 1024
        print(f'[BACKUP] OK: {dst.name} ({size_kb} KB)')

        # Backup remoto (NAS / secondo PC)
        if BACKUP_REMOTO_PATH:
            _copia_remota(dst)

        # Rotazione: elimina i più vecchi oltre MAX_BACKUPS
        _ruota_backup()

        return str(dst)

    except Exception as e:
        print(f'[BACKUP] ERRORE: {e}')
        if dst.exists():
            dst.unlink()
        return None


def _copia_remota(src: Path):
    """Copia il backup su percorso remoto (NAS, UNC share, cartella di rete)."""
    try:
        remote_dir = Path(BACKUP_REMOTO_PATH)
        remote_dir.mkdir(parents=True, exist_ok=True)
        dst_remote = remote_dir / src.name
        shutil.copy2(src, dst_remote)
        print(f'[BACKUP] Remoto OK: {dst_remote}')
    except Exception as e:
        print(f'[BACKUP] WARN copia remota fallita: {e}')


def _ruota_backup():
    """Mantiene solo gli ultimi MAX_BACKUPS file, elimina i più vecchi."""
    pattern = str(BACKUP_DIR / 'scheduler_schedulato_*.db')
    files = sorted(glob.glob(pattern))
    da_eliminare = files[:-MAX_BACKUPS] if len(files) > MAX_BACKUPS else []
    for old in da_eliminare:
        try:
            os.remove(old)
            print(f'[BACKUP] Rimosso vecchio backup: {Path(old).name}')
        except Exception as e:
            print(f'[BACKUP] WARN rimozione fallita {old}: {e}')


def integrity_check() -> bool:
    """Verifica l'integrità del database. Restituisce True se tutto OK."""
    if not DB_PATH.exists():
        return False
    try:
        conn = sqlite3.connect(str(DB_PATH))
        result = conn.execute('PRAGMA integrity_check').fetchone()
        conn.close()
        ok = result and result[0] == 'ok'
        if ok:
            print('[BACKUP] Integrity check: OK')
        else:
            print(f'[BACKUP] ATTENZIONE integrity check: {result}')
        return ok
    except Exception as e:
        print(f'[BACKUP] ERRORE integrity check: {e}')
        return False


if __name__ == '__main__':
    print('=== BACKUP MANUALE ===')
    integrity_check()
    path = backup(motivo='manuale')
    if path:
        print(f'Backup salvato in: {path}')
    else:
        print('Backup fallito.')

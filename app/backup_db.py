"""
backup_db.py — Backup automatico del database SQLite

Funzionalita':
  - Backup a caldo con SQLite Online Backup API (sicuro anche con server attivo)
  - Rotazione automatica: mantiene gli ultimi max_backups backup locali
  - Backup remoto opzionale su NAS/secondo PC
  - Configurazione tramite backup_config.json
  - Scheduler integrato con thread background
  - Eseguibile manualmente: python backup_db.py
"""

import sqlite3
import shutil
import os
import glob
import json
import time
import threading
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Percorsi default
_HERE = Path(__file__).parent
DB_PATH = _HERE / 'database' / 'scheduler.db'
DEFAULT_BACKUP_DIR = _HERE / 'database' / 'backups'
CONFIG_PATH = _HERE / 'backup_config.json'

# Config defaults
DEFAULT_CONFIG = {
    'backup_enabled': True,
    'interval_hours': 12,
    'max_backups': 30,
    'backup_path': '',
    'remote_path': ''
}


def load_config() -> dict:
    """Carica configurazione da backup_config.json."""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
            merged = {**DEFAULT_CONFIG, **config}
            return merged
    except Exception as e:
        logger.warning(f'[BACKUP] Errore lettura config: {e}')
    return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    """Salva configurazione su backup_config.json."""
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info('[BACKUP] Config salvata')
    except Exception as e:
        logger.error(f'[BACKUP] Errore salvataggio config: {e}')


def _get_backup_dir() -> Path:
    """Ritorna la cartella backup (da config o default)."""
    config = load_config()
    custom_path = config.get('backup_path', '').strip()
    if custom_path:
        return Path(custom_path)
    return DEFAULT_BACKUP_DIR


def backup(motivo: str = 'schedulato') -> str | None:
    """
    Esegue un backup a caldo del database.

    Usa l'SQLite Online Backup API: sicuro anche con il server Flask attivo,
    non richiede lock esclusivi e non interrompe le operazioni in corso.

    Returns:
        Path del file di backup creato, oppure None in caso di errore.
    """
    if not DB_PATH.exists():
        logger.error(f'[BACKUP] Database non trovato: {DB_PATH}')
        return None

    backup_dir = _get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    dst = backup_dir / f'scheduler_{motivo}_{ts}.db'

    try:
        src_conn = sqlite3.connect(str(DB_PATH))
        dst_conn = sqlite3.connect(str(dst))
        src_conn.backup(dst_conn, pages=100)
        dst_conn.close()
        src_conn.close()

        size_kb = dst.stat().st_size // 1024
        logger.info(f'[BACKUP] OK: {dst.name} ({size_kb} KB)')

        # Backup remoto
        config = load_config()
        remote_path = config.get('remote_path', '').strip()
        if remote_path:
            _copia_remota(dst, remote_path)

        # Rotazione
        max_backups = config.get('max_backups', 30)
        _ruota_backup(backup_dir, max_backups)

        return str(dst)

    except Exception as e:
        logger.error(f'[BACKUP] ERRORE: {e}')
        if dst.exists():
            dst.unlink()
        return None


def _copia_remota(src: Path, remote_path: str):
    """Copia il backup su percorso remoto (NAS, UNC share, cartella di rete)."""
    try:
        remote_dir = Path(remote_path)
        remote_dir.mkdir(parents=True, exist_ok=True)
        dst_remote = remote_dir / src.name
        shutil.copy2(src, dst_remote)
        logger.info(f'[BACKUP] Remoto OK: {dst_remote}')
    except Exception as e:
        logger.warning(f'[BACKUP] WARN copia remota fallita: {e}')


def _ruota_backup(backup_dir: Path, max_backups: int):
    """Mantiene solo gli ultimi max_backups file, elimina i piu' vecchi."""
    pattern = str(backup_dir / 'scheduler_*.db')
    files = sorted(glob.glob(pattern))
    da_eliminare = files[:-max_backups] if len(files) > max_backups else []
    for old in da_eliminare:
        try:
            os.remove(old)
            logger.info(f'[BACKUP] Rimosso vecchio: {Path(old).name}')
        except Exception as e:
            logger.warning(f'[BACKUP] WARN rimozione fallita {old}: {e}')


def integrity_check() -> bool:
    """Verifica l'integrita' del database. Restituisce True se tutto OK."""
    if not DB_PATH.exists():
        return False
    try:
        conn = sqlite3.connect(str(DB_PATH))
        result = conn.execute('PRAGMA integrity_check').fetchone()
        conn.close()
        ok = result and result[0] == 'ok'
        if ok:
            logger.info('[BACKUP] Integrity check: OK')
        else:
            logger.warning(f'[BACKUP] ATTENZIONE integrity check: {result}')
        return ok
    except Exception as e:
        logger.error(f'[BACKUP] ERRORE integrity check: {e}')
        return False


def list_backups() -> list:
    """Ritorna lista dei backup esistenti con info."""
    backup_dir = _get_backup_dir()
    if not backup_dir.exists():
        return []
    pattern = str(backup_dir / 'scheduler_*.db')
    files = sorted(glob.glob(pattern), reverse=True)
    result = []
    for f in files:
        p = Path(f)
        stat = p.stat()
        result.append({
            'filename': p.name,
            'size_kb': stat.st_size // 1024,
            'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'path': str(p)
        })
    return result


# === SCHEDULER BACKGROUND ===

_scheduler_thread = None
_scheduler_stop = threading.Event()


def start_scheduler():
    """Avvia il backup scheduler in background."""
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return

    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name='backup-scheduler')
    _scheduler_thread.start()
    logger.info('[BACKUP] Scheduler avviato')


def stop_scheduler():
    """Ferma il backup scheduler."""
    _scheduler_stop.set()
    logger.info('[BACKUP] Scheduler fermato')


def _scheduler_loop():
    """Loop principale dello scheduler."""
    while not _scheduler_stop.is_set():
        config = load_config()
        if not config.get('backup_enabled', True):
            _scheduler_stop.wait(60)
            continue

        interval_hours = max(1, config.get('interval_hours', 12))
        interval_seconds = interval_hours * 3600

        logger.info(f'[BACKUP] Prossimo backup tra {interval_hours}h')
        if _scheduler_stop.wait(interval_seconds):
            break

        config = load_config()
        if config.get('backup_enabled', True):
            logger.info('[BACKUP] Esecuzione backup schedulato...')
            backup(motivo='schedulato')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print('=== BACKUP MANUALE ===')
    integrity_check()
    path = backup(motivo='manuale')
    if path:
        print(f'Backup salvato in: {path}')
    else:
        print('Backup fallito.')

"""Cache dei risultati di parsing DXF, chiavata per hash SHA256 del contenuto file.

Se un DXF con stesso hash è già stato parsato, la seconda chiamata restituisce
il risultato cachato istantaneamente. Utile per:

1. **Commesse ripetute**: cliente rimanda gli stessi disegni per un preventivo
   simile → hash uguali → tutte le extrazioni skip.
2. **Batch grandi (100 DXF)**: molti file possono essere identici tra loro
   (varianti di un template) → parsing una sola volta.
3. **Ricaricamento pagina**: dopo un refresh, il preventivo esistente ha già
   articoli con DXF già visti → riapertura istantanea.

Storage: file SQLite dedicato `database/dxf_cache.db` (non tocca il DB
principale scheduler.db).

Chiave: hash SHA256 dei bytes del file DXF (deterministico anche se il file
viene rinominato o spostato).

Payload cachato:
- geometria (area, perimetro, n_forature, bbox)
- materiale + confidence
- peso + confidence
- spessore + confidence
- lavorazioni (pieghe, saldatura_ml, filettatura, svasatura)
- svg_string (per thumbnail)

TTL: nessuno. Il file DXF non cambia mai per un dato hash — se cambia,
cambia anche l'hash.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'database', 'dxf_cache.db'
)

_LOCK = threading.Lock()
_INITIALIZED = False


def _init_db() -> None:
    """Crea la tabella cache se non esiste (thread-safe, chiamato lazy)."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    with _LOCK:
        if _INITIALIZED:
            return
        os.makedirs(os.path.dirname(_CACHE_DB_PATH), exist_ok=True)
        con = sqlite3.connect(_CACHE_DB_PATH)
        try:
            con.execute("""
                CREATE TABLE IF NOT EXISTS dxf_parse_cache (
                    file_hash TEXT PRIMARY KEY,
                    filename TEXT,
                    payload_json TEXT NOT NULL,
                    svg_string TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    last_hit_at TEXT NOT NULL DEFAULT (datetime('now')),
                    hit_count INTEGER NOT NULL DEFAULT 1
                )
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_dxf_cache_last_hit
                ON dxf_parse_cache(last_hit_at)
            """)
            con.commit()
        finally:
            con.close()
        _INITIALIZED = True


def hash_file(path: str) -> str:
    """Calcola SHA256 dei bytes del file DXF. Chunked per file grandi."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(1 << 20):  # 1 MB chunks
            h.update(chunk)
    return h.hexdigest()


def get(file_hash: str) -> dict | None:
    """Recupera payload cachato (dict) + svg_string. None se miss.

    Aggiorna last_hit_at e hit_count (per LRU-style eviction futura).
    """
    _init_db()
    con = sqlite3.connect(_CACHE_DB_PATH)
    try:
        con.row_factory = sqlite3.Row
        cur = con.execute(
            "SELECT payload_json, svg_string FROM dxf_parse_cache WHERE file_hash = ?",
            (file_hash,)
        )
        row = cur.fetchone()
        if not row:
            return None
        # Aggiorna hit stats (non-blocking sui letti, best-effort)
        try:
            con.execute("""
                UPDATE dxf_parse_cache
                SET last_hit_at = datetime('now'), hit_count = hit_count + 1
                WHERE file_hash = ?
            """, (file_hash,))
            con.commit()
        except Exception:
            pass
        try:
            payload = json.loads(row['payload_json'])
        except json.JSONDecodeError:
            logger.warning('cache payload corrotto per hash %s', file_hash[:16])
            return None
        return {'payload': payload, 'svg_string': row['svg_string']}
    finally:
        con.close()


def put(file_hash: str, filename: str, payload: dict, svg_string: str | None = None) -> None:
    """Salva payload nella cache. Idempotente (INSERT OR REPLACE).

    payload deve essere JSON-serializable. Se non lo è, log warning e skip.
    """
    _init_db()
    try:
        payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as e:
        logger.warning('put cache fallito (payload non serializzabile): %s', e)
        return
    con = sqlite3.connect(_CACHE_DB_PATH)
    try:
        con.execute("""
            INSERT OR REPLACE INTO dxf_parse_cache
                (file_hash, filename, payload_json, svg_string,
                 created_at, last_hit_at, hit_count)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'),
                    COALESCE((SELECT hit_count FROM dxf_parse_cache WHERE file_hash = ?), 0) + 1)
        """, (file_hash, filename, payload_json, svg_string, file_hash))
        con.commit()
    finally:
        con.close()


def stats() -> dict:
    """Statistiche cache per debug/monitoring."""
    _init_db()
    con = sqlite3.connect(_CACHE_DB_PATH)
    try:
        cur = con.execute("""
            SELECT COUNT(*) as n_entries,
                   SUM(hit_count) as tot_hits,
                   MAX(hit_count) as max_hits_single,
                   SUM(LENGTH(svg_string) + LENGTH(payload_json)) as tot_bytes
            FROM dxf_parse_cache
        """)
        r = cur.fetchone()
        return {
            'n_entries': r[0] or 0,
            'tot_hits': r[1] or 0,
            'max_hits_single': r[2] or 0,
            'tot_bytes': r[3] or 0,
            'db_path': _CACHE_DB_PATH,
        }
    finally:
        con.close()


def clear() -> int:
    """Svuota la cache. Ritorna numero entry rimosse (per admin panel)."""
    _init_db()
    con = sqlite3.connect(_CACHE_DB_PATH)
    try:
        cur = con.execute("SELECT COUNT(*) FROM dxf_parse_cache")
        n = cur.fetchone()[0]
        con.execute("DELETE FROM dxf_parse_cache")
        con.commit()
        return n
    finally:
        con.close()

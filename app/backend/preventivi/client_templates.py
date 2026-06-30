import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

class ClientTemplates:
    """Manages client profile templates for recurring customers."""

    def __init__(self, db_path: str | None = None):
        """Initialize with same DB as Database service."""
        if db_path is None:
            from preventivatore.services.database import Database
            temp_db = Database()
            self.db_path = temp_db._db_path
        else:
            self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def salva_template(self, nome: str, margine: float = 0, sconto: float = 0,
                       condizioni: str = "", note: str = "",
                       azienda_info: dict | None = None) -> int:
        """Save or update a client template. Returns template ID.
        If nome already exists, updates the existing record."""
        azienda_json = json.dumps(azienda_info or {}, ensure_ascii=False)
        with self._get_conn() as conn:
            # Check if exists
            existing = conn.execute(
                "SELECT id FROM clienti_template WHERE nome = ?", (nome,)
            ).fetchone()
            if existing:
                conn.execute("""
                    UPDATE clienti_template SET
                        margine_default=?, sconto_default=?, condizioni_pagamento=?,
                        note=?, azienda_info=?, data_modifica=datetime('now','localtime')
                    WHERE nome=?
                """, (margine, sconto, condizioni, note, azienda_json, nome))
                logger.info("Template cliente aggiornato: %s", nome)
                return existing['id']
            else:
                cursor = conn.execute("""
                    INSERT INTO clienti_template (nome, margine_default, sconto_default,
                        condizioni_pagamento, note, azienda_info)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nome, margine, sconto, condizioni, note, azienda_json))
                logger.info("Template cliente creato: %s (ID=%d)", nome, cursor.lastrowid)
                return cursor.lastrowid

    def cerca_templates(self, filtro: str = "") -> list[dict]:
        """Search templates by name (partial match). Returns list of summary dicts."""
        with self._get_conn() as conn:
            if filtro:
                rows = conn.execute(
                    "SELECT * FROM clienti_template WHERE nome LIKE ? ORDER BY nome",
                    (f"%{filtro}%",)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM clienti_template ORDER BY nome"
                ).fetchall()
            return [dict(r) for r in rows]

    def carica_template(self, template_id: int) -> dict | None:
        """Load a single template by ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM clienti_template WHERE id = ?", (template_id,)
            ).fetchone()
            if row:
                result = dict(row)
                try:
                    result['azienda_info'] = json.loads(result.get('azienda_info', '{}'))
                except (json.JSONDecodeError, TypeError):
                    result['azienda_info'] = {}
                return result
            return None

    def carica_template_per_nome(self, nome: str) -> dict | None:
        """Load a template by exact name match."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM clienti_template WHERE nome = ?", (nome,)
            ).fetchone()
            if row:
                result = dict(row)
                try:
                    result['azienda_info'] = json.loads(result.get('azienda_info', '{}'))
                except (json.JSONDecodeError, TypeError):
                    result['azienda_info'] = {}
                return result
            return None

    def nomi_clienti(self) -> list[str]:
        """Get all client names for autocomplete."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT nome FROM clienti_template ORDER BY nome"
            ).fetchall()
            return [r['nome'] for r in rows]

    def elimina_template(self, template_id: int) -> bool:
        """Delete a template by ID."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM clienti_template WHERE id = ?", (template_id,)
            )
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("Template cliente eliminato: ID=%d", template_id)
            return deleted

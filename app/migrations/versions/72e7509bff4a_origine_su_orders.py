"""Aggiunge colonne `origine` e `preventivo_id_origine` su orders.

Parte del merge Preventivatore: distingue gli ordini creati da PDF (Elena oggi)
vs quelli creati da accettazione preventivo (commerciale nuovo).

NOTA: questa migration NON crea le 5 tabelle preventivi (preventivi,
preventivo_articoli, preventivo_assiemi, preventivo_tubolari, preventivo_piastre).
Quelle vengono create da `Base.metadata.create_all()` in `initialize_database()`
(pattern legacy del progetto). Le future modifiche di colonne su quelle tabelle
useranno Alembic correttamente.

Revision ID: 72e7509bff4a
Revises: 34f2aa86f9e3
Create Date: 2026-06-30 20:37:02.263288

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72e7509bff4a'
down_revision: Union[str, Sequence[str], None] = '34f2aa86f9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aggiunge origine + preventivo_id_origine su orders, idempotente."""
    # Su DB legacy le 2 colonne possono essere già state aggiunte da
    # `Base.metadata.create_all()`. Verifica prima di aggiungerle.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {c['name'] for c in inspector.get_columns('orders')}
    if 'origine' not in existing_cols:
        op.add_column('orders', sa.Column('origine', sa.String(), nullable=True, server_default='PDF'))
    if 'preventivo_id_origine' not in existing_cols:
        op.add_column('orders', sa.Column('preventivo_id_origine', sa.String(), nullable=True))


def downgrade() -> None:
    """Rimuove le colonne aggiunte (richiede SQLite batch mode per ALTER)."""
    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_column('preventivo_id_origine')
        batch_op.drop_column('origine')

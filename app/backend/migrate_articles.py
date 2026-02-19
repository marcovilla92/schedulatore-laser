"""
Utilita di migrazione: popola la tabella articles a partire dal JSON articles degli ordini esistenti.
Gestisce anche la migrazione dello schema per colonne aggiunte in v1.1+.

Uso standalone:
    python -m app.backend.migrate_articles

Uso programmatico:
    from app.backend.migrate_articles import run_migration
    result = run_migration()
"""
import uuid
import sqlalchemy
from .models import Base, Article, Order, get_session, engine


def _ensure_column_exists(table_name: str, column_name: str, column_def: str):
    """
    Aggiunge una colonna a una tabella esistente se non e gia presente.
    Operazione idempotente — usa PRAGMA table_info per verificare prima.

    Args:
        table_name: nome della tabella SQLite
        column_name: nome della colonna da aggiungere
        column_def: definizione SQL della colonna (es. "TEXT DEFAULT NULL")
    """
    with engine.connect() as conn:
        # Controlla le colonne esistenti
        result = conn.execute(sqlalchemy.text(f"PRAGMA table_info({table_name})"))
        existing_columns = {row[1] for row in result.fetchall()}

        if column_name not in existing_columns:
            conn.execute(
                sqlalchemy.text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
            )
            conn.commit()
            print(f"[MIGRAZIONE] Colonna '{column_name}' aggiunta a '{table_name}'.")
        else:
            print(f"[MIGRAZIONE] Colonna '{column_name}' gia presente in '{table_name}'.")


def ensure_articles_table():
    """
    Crea la tabella articles se non esiste ancora e assicura che tutte
    le colonne v1.1+ siano presenti nelle tabelle esistenti.
    Operazione idempotente — sicura da chiamare piu volte.
    """
    # Crea tabelle nuove (articles) — non tocca tabelle esistenti
    Base.metadata.create_all(bind=engine)

    # Assicura che processing_steps.article_id esista (aggiunta in v1.1+)
    # SQLAlchemy create_all non aggiunge colonne a tabelle esistenti
    _ensure_column_exists(
        table_name='processing_steps',
        column_name='article_id',
        column_def='TEXT DEFAULT NULL REFERENCES articles(id)'
    )

    print("[MIGRAZIONE] Schema v1.1+ verificato/aggiornato.")


def migrate_existing_orders() -> dict:
    """
    Crea record Article a partire dai dati JSON degli ordini esistenti.

    Per ogni ordine che ha articoli nel campo JSON ma nessun record
    nella tabella articles, vengono creati i corrispondenti Article.

    Ritorna:
        dict con chiavi migrated_orders, migrated_articles, errors
    """
    session = get_session()
    migrated_orders = 0
    migrated_articles = 0
    errors = []

    try:
        # Recupera tutti gli ordini che hanno articoli JSON
        orders = session.query(Order).all()

        for order in orders:
            # Salta ordini senza articoli JSON
            if not order.articles:
                continue

            # Controlla se esistono gia record Article per questo ordine
            existing_count = session.query(Article).filter(
                Article.order_id == order.id
            ).count()

            if existing_count > 0:
                # Gia migrato — salta
                continue

            # Migra ogni articolo JSON come record Article separato
            articoli_migrati = 0
            try:
                for articolo in order.articles:
                    if not isinstance(articolo, dict):
                        # Dati malformati — salta ma registra l'errore
                        errors.append(
                            f"Ordine {order.id}: articolo non e un dizionario: {articolo!r}"
                        )
                        continue

                    # Campi noti estratti direttamente
                    campi_noti = {'name', 'code', 'qty', 'required_phases'}
                    attributes_extra = {
                        k: v for k, v in articolo.items() if k not in campi_noti
                    }

                    article = Article(
                        id=str(uuid.uuid4()),
                        order_id=order.id,
                        name=articolo.get('name', ''),
                        code=articolo.get('code', ''),
                        qty=articolo.get('qty', 0),
                        required_phases=articolo.get(
                            'required_phases',
                            ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'SPEDIZIONE']
                        ),
                        attributes=attributes_extra,
                    )
                    session.add(article)
                    articoli_migrati += 1

                # Commit per ordine (transazione per ordine, non per articolo)
                session.commit()
                migrated_orders += 1
                migrated_articles += articoli_migrati
                print(
                    f"[MIGRAZIONE] Ordine {order.id} ({order.cliente}): "
                    f"{articoli_migrati} articoli migrati"
                )

            except Exception as e:
                session.rollback()
                msg = f"Ordine {order.id} ({order.cliente}): errore durante migrazione — {e}"
                errors.append(msg)
                print(f"[MIGRAZIONE] ERRORE — {msg}")

    finally:
        session.close()

    return {
        "migrated_orders": migrated_orders,
        "migrated_articles": migrated_articles,
        "errors": errors,
    }


def run_migration() -> dict:
    """
    Punto di ingresso principale per la migrazione.

    1. Assicura che la tabella articles esista
    2. Popola i record Article dagli ordini esistenti
    3. Stampa il riepilogo
    """
    print("[MIGRAZIONE] Avvio migrazione articoli...")
    ensure_articles_table()
    result = migrate_existing_orders()

    print(
        f"[MIGRAZIONE] Completato: "
        f"{result['migrated_orders']} ordini migrati, "
        f"{result['migrated_articles']} articoli creati, "
        f"{len(result['errors'])} errori."
    )
    if result['errors']:
        print("[MIGRAZIONE] Errori riscontrati:")
        for err in result['errors']:
            print(f"  - {err}")

    return result


if __name__ == '__main__':
    run_migration()

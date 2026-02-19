"""Operazioni CRUD per la gestione degli Ordini con tracking per articolo (v1.1+)"""
from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified
from .models import (
    Order, Article, OrderFile, ProcessingStep, OrderNotification,
    OrderStatus, ProcessingPhase, get_session
)
import uuid
import json

# Ordine canonico delle fasi
PHASE_ORDER = ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'SPEDIZIONE']


class OrderManager:
    """Gestore operazioni su ordini con articoli e tracking per-articolo (v1.1+)"""

    @staticmethod
    def create_order(cliente: str, data_consegna: str, articles: list = None,
                     required_phases: list = None, preventivo_minuti: int = 0,
                     note: str = "") -> Order:
        """
        Crea un nuovo ordine con articoli e ProcessingStep per articolo.

        articles = [
            {"name": "Staffa A", "code": "SA-001", "qty": 50,
             "required_phases": ["LASER", "PIEGA", "SALDATURA"]},
            ...
        ]

        Per ogni articolo viene creato un record Article nella tabella articles,
        e per ciascuna fase richiesta da quell'articolo viene creato un ProcessingStep
        con article_id impostato (v1.1+).

        Se non vengono passati articoli, viene creato un articolo "default" con
        tutte e 5 le fasi (gestione ordini senza articoli espliciti).
        """
        session = get_session()

        try:
            # Normalizza la lista articoli
            articles_list = articles or []

            # Calcola le fasi richieste come unione di tutte le fasi degli articoli
            # (compatibilità con order.required_phases JSON)
            if articles_list:
                all_phases = set()
                for article in articles_list:
                    for p in article.get('required_phases', PHASE_ORDER):
                        all_phases.add(p)
                actual_phases = [p for p in PHASE_ORDER if p in all_phases]
                if not actual_phases:
                    actual_phases = required_phases or ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'SPEDIZIONE']
            else:
                actual_phases = required_phases or ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'SPEDIZIONE']

            # Crea il record Order
            order = Order(
                id=str(uuid.uuid4()),
                cliente=cliente,
                data_consegna=datetime.fromisoformat(data_consegna),
                articles=articles_list,          # JSON legacy per compatibilità frontend
                required_phases=actual_phases,   # Unione fasi per lookup rapido
                preventivo_minuti=preventivo_minuti,
                note=note
            )

            # Calcola total_quantity
            if articles_list:
                order.total_quantity = sum(a.get('qty', 0) for a in articles_list)

            session.add(order)
            session.flush()  # Ottieni order.id prima di creare articoli/step

            # Caso speciale: nessun articolo → crea articolo "default"
            if not articles_list:
                articles_list = [{
                    'name': 'Articolo Default',
                    'code': '',
                    'qty': 0,
                    'required_phases': actual_phases
                }]
                print(f"[DB] Ordine senza articoli: creato articolo default con fasi {actual_phases}")

            # Crea Article records + ProcessingStep per articolo+fase
            for art_data in articles_list:
                art_required_phases = art_data.get('required_phases', PHASE_ORDER)
                # Normalizza: mantieni ordine canonico
                art_phases = [p for p in PHASE_ORDER if p in art_required_phases]
                if not art_phases:
                    art_phases = PHASE_ORDER[:]

                article = Article(
                    id=str(uuid.uuid4()),
                    order_id=order.id,
                    name=art_data.get('name', ''),
                    code=art_data.get('code', ''),
                    qty=art_data.get('qty', 0),
                    required_phases=art_phases,
                    attributes={k: v for k, v in art_data.items()
                                if k not in ('name', 'code', 'qty', 'required_phases')}
                )
                session.add(article)
                session.flush()  # Ottieni article.id prima di creare gli step

                # Crea un ProcessingStep per ogni fase richiesta da questo articolo
                for phase in art_phases:
                    step = ProcessingStep(
                        id=str(uuid.uuid4()),
                        order_id=order.id,
                        article_id=article.id,   # FK verso l'articolo specifico (v1.1+)
                        fase=phase
                    )
                    session.add(step)

            session.commit()
            session.refresh(order)
            print(f"[DB] Ordine creato: {order.id} | cliente={cliente} | articoli={len(articles_list)}")
            return order

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def get_order(order_id: str) -> Order:
        """Recupera un ordine per ID"""
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if order:
                # Force load relazioni
                for step in order.processing_steps:
                    pass
            return order
        finally:
            session.close()

    @staticmethod
    def get_all_orders(cliente: str = None) -> list:
        """Recupera ordini, opzionalmente filtrati per cliente"""
        session = get_session()
        try:
            query = session.query(Order)
            if cliente:
                query = query.filter(Order.cliente == cliente)
            return query.all()
        finally:
            session.close()

    @staticmethod
    def get_all_orders_dict(cliente: str = None) -> list:
        """
        Recupera ordini come dizionari con processing_steps serializzati.
        Include conteggio articoli e riepilogo completamento per-articolo (v1.1+).
        """
        session = get_session()
        try:
            query = session.query(Order)
            if cliente:
                query = query.filter(Order.cliente == cliente)

            orders = query.all()
            result = []

            for order in orders:
                # Conta articoli dalla tabella articles (v1.1+)
                article_count = session.query(Article).filter(
                    Article.order_id == order.id
                ).count()

                # Recupera Article records per questo ordine (v1.1+)
                articles_db = session.query(Article).filter(
                    Article.order_id == order.id
                ).order_by(Article.id).all()

                article_records_list = []
                for art in articles_db:
                    # Controlla se almeno uno step di questo articolo e stato avviato
                    started_count = session.query(ProcessingStep).filter(
                        ProcessingStep.article_id == art.id,
                        ProcessingStep.timestamp_inizio.isnot(None)
                    ).count()

                    article_records_list.append({
                        'id': art.id,
                        'name': art.name,
                        'code': art.code,
                        'qty': art.qty,
                        'required_phases': art.required_phases,
                        'has_started_steps': started_count > 0
                    })

                # Serializza dentro la sessione per evitare lazy loading
                result.append({
                    'id': order.id,
                    'cliente': order.cliente,
                    'data_consegna': order.data_consegna.isoformat(),
                    'total_quantity': order.total_quantity,
                    'status': order.status,
                    'articles': order.articles,
                    'article_count': article_count,              # Numero articoli (v1.1+)
                    'article_records': article_records_list,     # Dati articoli per UI checkbox (v1.1+)
                    'processing_steps': [
                        {
                            'fase': ps.fase,
                            'article_id': ps.article_id,  # Nuovo campo v1.1+
                            'timestamp_inizio': ps.timestamp_inizio.isoformat() if ps.timestamp_inizio else None,
                            'timestamp_fine': ps.timestamp_fine.isoformat() if ps.timestamp_fine else None,
                            'operatore': ps.operatore
                        }
                        for ps in order.processing_steps
                    ] if order.processing_steps else []
                })

            return result
        finally:
            session.close()

    @staticmethod
    def get_orders_by_phase(phase: str) -> list:
        """
        Recupera ordini che hanno almeno un articolo con la fase specificata non completata.
        Usa query JOIN per efficienza (v1.1+).
        Per ordini senza Article records (pre-v1.1): fallback su required_phases JSON.
        """
        session = get_session()
        try:
            # Query v1.1+: articoli con la fase non ancora completata
            # JOIN Article -> ProcessingStep dove step.fase = phase e step.timestamp_fine IS NULL
            matching_order_ids = set()

            # Trova articoli che richiedono questa fase
            articles_with_phase = session.query(Article).filter(
                Article.required_phases.contains(phase)
            ).all()

            for article in articles_with_phase:
                # Controlla se esiste uno step non completato per questo articolo+fase
                step = session.query(ProcessingStep).filter(
                    ProcessingStep.article_id == article.id,
                    ProcessingStep.fase == phase,
                    ProcessingStep.timestamp_fine.is_(None)
                ).first()

                if step:
                    matching_order_ids.add(article.order_id)

            # Fallback per ordini pre-v1.1 (senza Article records)
            # Controlla ordini che non hanno Article records ma hanno required_phases
            orders_with_articles = session.query(Article.order_id).distinct().all()
            orders_with_articles_ids = {row[0] for row in orders_with_articles}

            orders_without_articles = session.query(Order).filter(
                Order.id.notin_(orders_with_articles_ids),
                Order.required_phases.contains(phase)
            ).all()

            for order in orders_without_articles:
                # Fallback: controlla ProcessingStep senza article_id
                step = session.query(ProcessingStep).filter(
                    ProcessingStep.order_id == order.id,
                    ProcessingStep.article_id.is_(None),
                    ProcessingStep.fase == phase,
                    ProcessingStep.timestamp_fine.is_(None)
                ).first()
                if step:
                    matching_order_ids.add(order.id)

            # Recupera gli Order completi
            if not matching_order_ids:
                return []

            matching_orders = session.query(Order).filter(
                Order.id.in_(matching_order_ids)
            ).all()

            return matching_orders
        finally:
            session.close()

    @staticmethod
    def start_phase(order_id: str, phase: str, operatore: str = "",
                    article_id: str = None) -> bool:
        """
        Inizia l'elaborazione di una fase.

        v1.1+:
        - Se article_id è fornito: avvia lo step specifico per quell'articolo+fase
        - Se article_id NON è fornito (backward compat): avvia TUTTI gli step
          per quell'ordine+fase che non sono ancora stati avviati (batch start)

        Ritorna True se almeno uno step è stato avviato.
        """
        session = get_session()
        try:
            started_any = False

            if article_id:
                # Modalità per-articolo (v1.1+)
                step = session.query(ProcessingStep).filter(
                    ProcessingStep.order_id == order_id,
                    ProcessingStep.article_id == article_id,
                    ProcessingStep.fase == phase
                ).first()

                if step and not step.timestamp_inizio:
                    step.timestamp_inizio = datetime.utcnow()
                    step.operatore = operatore
                    started_any = True
            else:
                # Modalità batch (backward compat + pre-v1.1)
                steps = session.query(ProcessingStep).filter(
                    ProcessingStep.order_id == order_id,
                    ProcessingStep.fase == phase
                ).all()

                for step in steps:
                    if not step.timestamp_inizio:
                        step.timestamp_inizio = datetime.utcnow()
                        step.operatore = operatore
                        started_any = True

            if started_any:
                session.commit()
                print(f"[DB] Fase avviata: ordine={order_id} fase={phase} article_id={article_id or 'batch'}")
            return started_any

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def complete_phase(order_id: str, phase: str, note: str = "",
                       article_id: str = None) -> dict:
        """
        Completa una fase e ritorna info sull'ordine.

        v1.1+:
        - Se article_id è fornito: completa lo step specifico per quell'articolo+fase
        - Se article_id NON è fornito (backward compat): completa TUTTI gli step
          per quell'ordine+fase (batch complete)

        Dopo il completamento controlla se l'ordine è completamente terminato:
        tutti i ProcessingStep di tutti gli articoli devono avere timestamp_fine.
        """
        session = get_session()
        try:
            completed_any = False

            if article_id:
                # Modalità per-articolo (v1.1+)
                steps_to_complete = session.query(ProcessingStep).filter(
                    ProcessingStep.order_id == order_id,
                    ProcessingStep.article_id == article_id,
                    ProcessingStep.fase == phase
                ).all()
            else:
                # Modalità batch (backward compat)
                steps_to_complete = session.query(ProcessingStep).filter(
                    ProcessingStep.order_id == order_id,
                    ProcessingStep.fase == phase
                ).all()

            for step in steps_to_complete:
                if not step.timestamp_fine:
                    step.timestamp_fine = datetime.utcnow()
                    step.note = note

                    # Compatibilità legacy: popola completed_articles con tutti gli indici
                    # (necessario per il frontend che legge ancora questo campo)
                    order_for_articles = session.query(Order).filter(
                        Order.id == order_id
                    ).first()
                    if order_for_articles and order_for_articles.articles:
                        step.completed_articles = list(range(len(order_for_articles.articles)))
                        flag_modified(step, 'completed_articles')

                    completed_any = True

            if not completed_any:
                return {"success": False, "error": "Fase non trovata o gia completata"}

            session.commit()
            print(f"[DB] Fase completata: ordine={order_id} fase={phase} article_id={article_id or 'batch'}")

            # Ricarica l'ordine per controllare completamento globale
            order = session.query(Order).filter(Order.id == order_id).first()

            # Verifica completamento ordine: TUTTI i ProcessingStep dell'ordine devono
            # avere timestamp_fine (include sia step per-articolo v1.1 che step legacy)
            all_steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id
            ).all()

            total_count = len(all_steps)
            completed_count = sum(1 for s in all_steps if s.timestamp_fine)
            all_completed = total_count > 0 and completed_count == total_count

            if all_completed:
                order.status = OrderStatus.SPEDITO.value
                notification = OrderNotification(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    tempi_totali="Ordine completato"
                )
                session.add(notification)
                session.commit()
                print(f"[DB] Ordine completato: {order_id}")

            # Fasi completate aggregate (backward compat)
            completed_phases = list({s.fase for s in all_steps if s.timestamp_fine})

            return {
                "success": True,
                "order_id": order_id,
                "phase": phase,
                "completed_phases": completed_phases,
                "all_completed": all_completed
            }

        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def complete_phase_partial(order_id: str, phase: str,
                               article_indices: list = None,
                               article_ids: list = None,
                               note: str = "") -> dict:
        """
        Completa una fase solo per specifici articoli (completamento parziale).

        v1.1+:
        - Se article_ids fornito: completa i ProcessingStep per quegli article UUID
        - Se article_indices fornito (backward compat): risolve gli indici in UUID
          dalle Article records ordinate per creazione, poi completa quelli

        Dopo il completamento controlla completamento per-articolo e ordine-livello.
        """
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Ordine non trovato"}

            # Determina i target article_ids
            target_article_ids = []

            if article_ids:
                # v1.1+ modalità UUID
                target_article_ids = list(article_ids)
            elif article_indices is not None:
                # Modalità legacy: risolvi indici in UUID
                articles_ordered = session.query(Article).filter(
                    Article.order_id == order_id
                ).order_by(Article.id).all()

                if articles_ordered:
                    # Indici verso UUID usando posizione nell'ordinamento
                    for idx in article_indices:
                        if 0 <= idx < len(articles_ordered):
                            target_article_ids.append(articles_ordered[idx].id)
                        else:
                            return {"success": False, "error": f"Indice articolo non valido: {idx}"}
                else:
                    # Fallback pre-v1.1: usa ProcessingStep legacy (senza article_id)
                    return OrderManager._complete_phase_partial_legacy(
                        session, order, order_id, phase, article_indices, note
                    )

            if not target_article_ids:
                return {"success": False, "error": "Nessun articolo selezionato"}

            # Completa gli step per gli articoli target
            completed_article_ids = []
            for art_id in target_article_ids:
                step = session.query(ProcessingStep).filter(
                    ProcessingStep.order_id == order_id,
                    ProcessingStep.article_id == art_id,
                    ProcessingStep.fase == phase
                ).first()

                if step and not step.timestamp_fine:
                    step.timestamp_fine = datetime.utcnow()
                    step.note = note
                    completed_article_ids.append(art_id)

                    # Legacy compat: aggiorna completed_articles sullo step
                    current = list(step.completed_articles or [])
                    # Trova l'indice dell'articolo per compatibilità legacy
                    articles_ordered = session.query(Article).filter(
                        Article.order_id == order_id
                    ).order_by(Article.id).all()
                    art_idx_map = {a.id: i for i, a in enumerate(articles_ordered)}
                    art_idx = art_idx_map.get(art_id)
                    if art_idx is not None and art_idx not in current:
                        current.append(art_idx)
                    step.completed_articles = current
                    flag_modified(step, 'completed_articles')

            session.commit()
            print(f"[DB] Completamento parziale: ordine={order_id} fase={phase} articoli={completed_article_ids}")

            # Controlla se la fase è completamente finita (tutti gli articoli con quella fase)
            all_steps_for_phase = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.fase == phase
            ).all()
            phase_complete = all(s.timestamp_fine for s in all_steps_for_phase) and len(all_steps_for_phase) > 0

            # Controlla completamento ordine
            all_steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id
            ).all()
            all_completed = all(s.timestamp_fine for s in all_steps) and len(all_steps) > 0

            if all_completed:
                order.status = OrderStatus.SPEDITO.value
                notification = OrderNotification(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    tempi_totali="Ordine completato"
                )
                session.add(notification)
                session.commit()
                print(f"[DB] Ordine completato (parziale→totale): {order_id}")

            return {
                "success": True,
                "order_id": order_id,
                "phase": phase,
                "articles_completed": completed_article_ids,
                "total_articles": len(all_steps_for_phase),
                "phase_complete": phase_complete,
                "order_complete": all_completed
            }

        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def _complete_phase_partial_legacy(session, order, order_id: str, phase: str,
                                       article_indices: list, note: str) -> dict:
        """
        Fallback per completamento parziale su ordini pre-v1.1 (senza Article records).
        Usa il ProcessingStep con completed_articles JSON (indici).
        """
        processing_step = session.query(ProcessingStep).filter(
            ProcessingStep.order_id == order_id,
            ProcessingStep.article_id.is_(None),
            ProcessingStep.fase == phase
        ).first()

        if not processing_step:
            # Cerca anche step senza article_id esplicito
            processing_step = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.fase == phase
            ).first()

        if not processing_step:
            return {"success": False, "error": "Fase non trovata"}

        # Aggiorna completed_articles legacy
        current = list(processing_step.completed_articles or [])
        for idx in article_indices:
            if idx not in current:
                current.append(idx)
        processing_step.completed_articles = current
        flag_modified(processing_step, 'completed_articles')

        all_articles_completed = (
            order.articles and
            len(processing_step.completed_articles) >= len(order.articles)
        )
        if all_articles_completed and not processing_step.timestamp_fine:
            processing_step.timestamp_fine = datetime.utcnow()
        processing_step.note = note
        session.commit()

        all_steps = session.query(ProcessingStep).filter(
            ProcessingStep.order_id == order_id
        ).all()
        all_completed = all(s.timestamp_fine for s in all_steps) and len(all_steps) > 0

        if all_completed:
            order.status = OrderStatus.SPEDITO.value
            notification = OrderNotification(
                id=str(uuid.uuid4()),
                order_id=order_id,
                tempi_totali="Ordine completato"
            )
            session.add(notification)
            session.commit()

        return {
            "success": True,
            "order_id": order_id,
            "phase": phase,
            "articles_completed": processing_step.completed_articles,
            "total_articles": len(order.articles) if order.articles else 0,
            "phase_complete": all_articles_completed,
            "order_complete": all_completed
        }

    @staticmethod
    def get_order_details(order_id: str) -> dict:
        """
        Recupera dettagli completi ordine con stato articoli e tracking per-articolo (v1.1+).

        Per ordini v1.1+:
        - Usa Article records dalla tabella articles
        - Deriva lo stato per-articolo dai ProcessingStep con article_id

        Per ordini pre-v1.1 (senza Article records):
        - Fallback alla logica legacy basata su JSON articles + completed_articles

        Mantiene la stessa forma della risposta API per backward compatibility:
        - articles: lista con idx, name, code, qty, required_phases, completed_phases,
                    next_phase, e (nuovo v1.1+) article_id
        - processing_steps: lista aggregata da tutti gli step (stessa forma di prima)
        """
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"error": "Ordine non trovato"}

            # Controlla se ci sono Article records per questo ordine (v1.1+)
            article_records = session.query(Article).filter(
                Article.order_id == order_id
            ).order_by(Article.id).all()

            # Recupera tutti i ProcessingStep dell'ordine
            all_steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id
            ).all()

            if article_records:
                # === Modalità v1.1+: usa Article records ===
                article_statuses = []
                for idx, article in enumerate(article_records):
                    # Step per questo articolo specifico
                    art_steps = [s for s in all_steps if s.article_id == article.id]

                    # Fasi completate per questo articolo
                    completed = [s.fase for s in art_steps if s.timestamp_fine]

                    # Fasi rimanenti
                    art_required = article.required_phases or PHASE_ORDER[:]
                    remaining = [p for p in art_required if p not in completed]

                    # Prossima fase = prima fase richiesta non completata
                    next_phase = None
                    for phase in art_required:
                        if phase not in completed:
                            next_phase = phase
                            break

                    # Articolo completato se tutte le fasi richieste sono complete
                    is_completed = len(remaining) == 0

                    article_statuses.append({
                        "idx": idx,                           # Indice per API parziale (backward compat)
                        "article_id": article.id,            # UUID articolo (nuovo v1.1+)
                        "name": article.name or 'N/A',
                        "code": article.code or '',
                        "qty": article.qty or 0,
                        "required_phases": art_required,
                        "completed_phases": completed,
                        "remaining_phases": remaining,        # Nuovo campo v1.1+
                        "next_phase": next_phase if next_phase else "Completato",
                        "is_completed": is_completed         # Nuovo campo v1.1+
                    })

            else:
                # === Fallback pre-v1.1: logica legacy JSON ===
                article_statuses = []
                for article_idx, article in enumerate(order.articles or []):
                    required_phases = article.get('required_phases', [])
                    if isinstance(required_phases, str):
                        required_phases = required_phases.split()

                    # Calcola fasi completate per questo articolo specifico
                    completed = []
                    for step in all_steps:
                        if article_idx in (step.completed_articles or []):
                            completed.append(step.fase)

                    # Prossima fase
                    next_phase = None
                    for phase in required_phases:
                        if phase not in completed:
                            next_phase = phase
                            break

                    remaining = [p for p in required_phases if p not in completed]

                    article_statuses.append({
                        "idx": article_idx,
                        "article_id": None,                  # Non disponibile in modalità legacy
                        "name": article.get('name', 'N/A'),
                        "code": article.get('code', ''),
                        "qty": article.get('qty', 0),
                        "required_phases": required_phases,
                        "completed_phases": completed,
                        "remaining_phases": remaining,
                        "next_phase": next_phase if next_phase else "Completato",
                        "is_completed": len(remaining) == 0
                    })

            # Serializza tutti gli step (forma identica all'API precedente + article_id)
            steps_serialized = [
                {
                    "fase": s.fase,
                    "article_id": s.article_id,          # Nuovo campo v1.1+ (None per step legacy)
                    "timestamp_inizio": s.timestamp_inizio.isoformat() if s.timestamp_inizio else None,
                    "timestamp_fine": s.timestamp_fine.isoformat() if s.timestamp_fine else None,
                    "operatore": s.operatore,
                    "note": s.note,
                    "completed_articles": s.completed_articles or []  # Legacy: indici articoli completati
                }
                for s in all_steps
            ]

            return {
                "id": order.id,
                "cliente": order.cliente,
                "data_ricezione": order.data_ricezione.isoformat(),
                "data_consegna": order.data_consegna.isoformat(),
                "status": order.status,
                "total_quantity": order.total_quantity,
                "preventivo_minuti": order.preventivo_minuti,
                "articles": article_statuses,
                "processing_steps": steps_serialized
            }

        finally:
            session.close()

    @staticmethod
    def update_order_articles(order_id: str, articles: list) -> bool:
        """
        Aggiorna gli articoli di un ordine.

        v1.1+: Sincronizza anche i record Article nella tabella articles:
        - Rimuove Article records non più presenti
        - Aggiunge nuovi Article records
        - Ricrea ProcessingStep per i nuovi articoli
        - Mantiene il JSON articles per compatibilità backward

        Il matching tra articoli vecchi e nuovi avviene per code+name o per posizione.
        """
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return False

            # Aggiorna il JSON legacy
            order.articles = articles
            order.total_quantity = sum(a.get('qty', 0) for a in articles)

            # Recupera i record Article esistenti
            existing_articles = session.query(Article).filter(
                Article.order_id == order_id
            ).order_by(Article.id).all()

            # Strategia: confronto per code+name
            def article_key(a_data):
                return (a_data.get('code', ''), a_data.get('name', ''))

            existing_keys = {
                (art.code, art.name): art for art in existing_articles
            }
            new_keys = {article_key(a): a for a in articles}

            # Rimuovi Article records non più presenti
            for key, art in list(existing_keys.items()):
                if key not in new_keys:
                    session.delete(art)
                    print(f"[DB] Articolo rimosso: {key} da ordine {order_id}")

            # Aggiungi nuovi Article records
            for key, art_data in new_keys.items():
                if key not in existing_keys:
                    art_phases = art_data.get('required_phases', PHASE_ORDER[:])
                    art_phases = [p for p in PHASE_ORDER if p in art_phases] or PHASE_ORDER[:]

                    new_article = Article(
                        id=str(uuid.uuid4()),
                        order_id=order_id,
                        name=art_data.get('name', ''),
                        code=art_data.get('code', ''),
                        qty=art_data.get('qty', 0),
                        required_phases=art_phases,
                        attributes={k: v for k, v in art_data.items()
                                    if k not in ('name', 'code', 'qty', 'required_phases')}
                    )
                    session.add(new_article)
                    session.flush()

                    # Crea ProcessingStep per il nuovo articolo
                    for phase in art_phases:
                        step = ProcessingStep(
                            id=str(uuid.uuid4()),
                            order_id=order_id,
                            article_id=new_article.id,
                            fase=phase
                        )
                        session.add(step)
                    print(f"[DB] Articolo aggiunto: {key} a ordine {order_id}")
                else:
                    # Aggiorna i campi dell'articolo esistente
                    art = existing_keys[key]
                    art.qty = art_data.get('qty', art.qty)
                    art_phases = art_data.get('required_phases', art.required_phases)
                    art_phases = [p for p in PHASE_ORDER if p in art_phases] or art.required_phases
                    art.required_phases = art_phases
                    flag_modified(art, 'required_phases')

            # Ricalcola required_phases dell'ordine come unione
            all_phases = set()
            for art_data in articles:
                for p in art_data.get('required_phases', PHASE_ORDER):
                    all_phases.add(p)
            order.required_phases = [p for p in PHASE_ORDER if p in all_phases] or PHASE_ORDER[:]
            flag_modified(order, 'required_phases')

            session.commit()
            print(f"[DB] Articoli aggiornati: ordine={order_id} totale={len(articles)}")
            return True

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

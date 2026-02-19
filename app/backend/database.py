"""CRUD operations for Order management"""
from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified
from .models import (
    Order, OrderFile, ProcessingStep, OrderNotification,
    OrderStatus, ProcessingPhase, get_session
)
import uuid
import json

class OrderManager:
    """Gestore operazioni su ordini con articoli"""
    
    @staticmethod
    def create_order(cliente: str, data_consegna: str, articles: list = None, 
                     required_phases: list = None, preventivo_minuti: int = 0, 
                     note: str = "") -> Order:
        """
        Crea un nuovo ordine con articoli
        
        articles = [
            {"name": "Staffa A", "code": "SA-001", "qty": 50, 
             "required_phases": ["LASER", "PIEGA", "SALDATURA"]},
            ...
        ]
        """
        session = get_session()
        
        try:
            # Calcola le fasi effettivamente richieste dagli articoli
            # SEMPRE derivare da articles se presenti (anche se required_phases è passato)
            if articles:
                phase_order = ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'SPEDIZIONE']
                all_phases = set()
                for article in articles:
                    for p in article.get('required_phases', []):
                        all_phases.add(p)
                # Mantieni l'ordine canonico
                actual_phases = [p for p in phase_order if p in all_phases]
                if not actual_phases:
                    actual_phases = required_phases or ['LASER', 'PIEGA', 'SALDATURA']
            else:
                actual_phases = required_phases or ['LASER', 'PIEGA', 'SALDATURA']

            order = Order(
                id=str(uuid.uuid4()),
                cliente=cliente,
                data_consegna=datetime.fromisoformat(data_consegna),
                articles=articles or [],
                required_phases=actual_phases,
                preventivo_minuti=preventivo_minuti,
                note=note
            )

            # Calcola total_quantity
            if articles:
                order.total_quantity = sum(article.get('qty', 0) for article in articles)

            # Inizializza ProcessingStep solo per le fasi effettivamente necessarie
            for phase in order.required_phases:
                step = ProcessingStep(
                    id=str(uuid.uuid4()),
                    order_id=order.id,
                    fase=phase
                )
                order.processing_steps.append(step)
            
            session.add(order)
            session.commit()
            session.refresh(order)
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
                # Carica relazioni
                for step in order.processing_steps:
                    pass  # Force load
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
        """Recupera ordini come dizionari con processing_steps serializzati"""
        session = get_session()
        try:
            query = session.query(Order)
            if cliente:
                query = query.filter(Order.cliente == cliente)
            
            orders = query.all()
            result = []
            
            for order in orders:
                # Serializza dentro la sessione per evitare lazy loading
                result.append({
                    'id': order.id,
                    'cliente': order.cliente,
                    'data_consegna': order.data_consegna.isoformat(),
                    'total_quantity': order.total_quantity,
                    'status': order.status,
                    'articles': order.articles,
                    'processing_steps': [
                        {
                            'fase': ps.fase,
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
        """Recupera ordini che hanno una specifica fase non completata"""
        session = get_session()
        try:
            # Recupera ordini con articoli che richiedono questa fase
            orders = session.query(Order).all()
            matching_orders = []
            
            for order in orders:
                # Controlla se la fase è richiesta dall'ordine
                if phase in order.required_phases:
                    # Controlla se la fase non è ancora completata
                    processing_step = session.query(ProcessingStep).filter(
                        ProcessingStep.order_id == order.id,
                        ProcessingStep.fase == phase
                    ).first()
                    
                    if processing_step and not processing_step.timestamp_fine:
                        matching_orders.append(order)
            
            return matching_orders
        finally:
            session.close()
    
    @staticmethod
    def start_phase(order_id: str, phase: str, operatore: str = "") -> bool:
        """Inizia l'elaborazione di una fase"""
        session = get_session()
        try:
            processing_step = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.fase == phase
            ).first()
            
            if processing_step and not processing_step.timestamp_inizio:
                processing_step.timestamp_inizio = datetime.utcnow()
                processing_step.operatore = operatore
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    @staticmethod
    def complete_phase(order_id: str, phase: str, note: str = "") -> dict:
        """Completa una fase e ritorna info sull'ordine"""
        session = get_session()
        try:
            processing_step = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.fase == phase
            ).first()
            
            if processing_step and not processing_step.timestamp_fine:
                processing_step.timestamp_fine = datetime.utcnow()
                processing_step.note = note

                # Ottieni l'ordine
                order = session.query(Order).filter(Order.id == order_id).first()

                # Popola completed_articles con tutti gli indici degli articoli
                if order and order.articles:
                    processing_step.completed_articles = list(range(len(order.articles)))
                    flag_modified(processing_step, 'completed_articles')
                
                # Commit prima di fare ulteriori query
                session.commit()
                
                # Adesso ricarica tutti gli step per controllare stato completo
                session.refresh(order)
                all_steps = session.query(ProcessingStep).filter(
                    ProcessingStep.order_id == order_id
                ).all()
                
                # Controlla quanti step hanno completamento
                completed_count = sum(1 for step in all_steps if step.timestamp_fine)
                total_count = len(all_steps)
                all_completed = completed_count == total_count and total_count > 0
                
                if all_completed:
                    order.status = OrderStatus.SPEDITO.value
                    
                    # Crea notifica di completamento
                    notification = OrderNotification(
                        id=str(uuid.uuid4()),
                        order_id=order_id,
                        tempi_totali="Ordine completato"
                    )
                    session.add(notification)
                    session.commit()
                
                # Calcola fasi completate per ogni articolo
                completed_phases = [step.fase for step in all_steps if step.timestamp_fine]
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "phase": phase,
                    "completed_phases": completed_phases,
                    "all_completed": all_completed
                }
            
            return {"success": False, "error": "Fase non trovata o già completata"}
            
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()
    
    @staticmethod
    def complete_phase_partial(order_id: str, phase: str, article_indices: list, note: str = "") -> dict:
        """
        Completa una fase solo per specifici articoli (completamento parziale)
        
        article_indices: lista di indici degli articoli da completare per questa fase
        Es: [0, 1, 3] = completa articoli con indice 0, 1, 3
        """
        session = get_session()
        try:
            processing_step = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.fase == phase
            ).first()
            
            if not processing_step:
                return {"success": False, "error": "Fase non trovata"}
            
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Ordine non trovato"}
            
            # Crea nuova lista per forzare il change-tracking di SQLAlchemy JSON
            current = list(processing_step.completed_articles or [])
            for idx in article_indices:
                if idx not in current:
                    current.append(idx)
            processing_step.completed_articles = current
            flag_modified(processing_step, 'completed_articles')

            # Controlla se TUTTI gli articoli sono stati completati per questa fase
            all_articles_completed = len(processing_step.completed_articles) == len(order.articles)
            
            # Se tutti gli articoli sono completati, segna la fase come completata
            if all_articles_completed and not processing_step.timestamp_fine:
                processing_step.timestamp_fine = datetime.utcnow()
            
            processing_step.note = note
            session.commit()
            
            # Controlla se l'ordine è completamente finito
            all_steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id
            ).all()
            
            all_completed = all(step.timestamp_fine for step in all_steps)
            
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
                "total_articles": len(order.articles),
                "phase_complete": all_articles_completed,
                "order_complete": all_completed
            }
            
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()
    
    @staticmethod
    def get_order_details(order_id: str) -> dict:
        """Recupera dettagli completi ordine con stato articoli e tracking parziale"""
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"error": "Ordine non trovato"}
            
            # Recupera fasi completate
            processing_steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id
            ).all()
            
            # Calcola stato per ogni articolo
            article_statuses = []
            for article_idx, article in enumerate(order.articles):
                required_phases = article.get('required_phases', [])
                
                # Se required_phases è stringa, convertila in lista
                if isinstance(required_phases, str):
                    required_phases = required_phases.split()
                
                # Calcola fasi completate per questo articolo specifico
                completed = []
                for step in processing_steps:
                    # Controlla se questo articolo è nel completed_articles per questo step
                    if article_idx in (step.completed_articles or []):
                        completed.append(step.fase)
                
                # Prossima fase = prima fase richiesta non completata
                next_phase = None
                for phase in required_phases:
                    if phase not in completed:
                        next_phase = phase
                        break
                
                article_statuses.append({
                    "idx": article_idx,  # Indice articolo (per API parziale)
                    "name": article.get('name', 'N/A'),
                    "code": article.get('code', ''),
                    "qty": article.get('qty', 0),
                    "required_phases": required_phases,
                    "completed_phases": completed,
                    "next_phase": next_phase if next_phase else "✅ Completato"
                })
            
            return {
                "id": order.id,
                "cliente": order.cliente,
                "data_ricezione": order.data_ricezione.isoformat(),
                "data_consegna": order.data_consegna.isoformat(),
                "status": order.status,
                "total_quantity": order.total_quantity,
                "preventivo_minuti": order.preventivo_minuti,
                "articles": article_statuses,
                "processing_steps": [
                    {
                        "fase": s.fase,
                        "timestamp_inizio": s.timestamp_inizio.isoformat() if s.timestamp_inizio else None,
                        "timestamp_fine": s.timestamp_fine.isoformat() if s.timestamp_fine else None,
                        "operatore": s.operatore,
                        "note": s.note,
                        "completed_articles": s.completed_articles or []  # Indici degli articoli completati
                    }
                    for s in processing_steps
                ]
            }
        finally:
            session.close()
    
    @staticmethod
    def update_order_articles(order_id: str, articles: list) -> bool:
        """Aggiorna gli articoli di un ordine"""
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if order:
                order.articles = articles
                order.total_quantity = sum(a.get('qty', 0) for a in articles)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

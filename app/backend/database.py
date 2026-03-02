"""CRUD operations for Order management"""
from datetime import datetime, timedelta
from sqlalchemy.orm.attributes import flag_modified
from .models import (
    Order, OrderFile, ProcessingStep, OrderNotification,
    OrderStatus, ProcessingPhase, get_session, User, AuditLog
)
import uuid
import json

class OrderManager:
    """Gestore operazioni su ordini con articoli"""

    @staticmethod
    def _format_duration(td: timedelta) -> str:
        """Formatta un timedelta in stringa leggibile (es: '2h 30min')"""
        if not td:
            return "0min"
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}min"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{minutes}min"

    @staticmethod
    def _calculate_order_total_time(order_id: str, session) -> str:
        """Calcola il tempo totale di tutte le fasi completate di un ordine"""
        try:
            steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.timestamp_inizio.isnot(None),
                ProcessingStep.timestamp_fine.isnot(None)
            ).all()

            if not steps:
                return "0min"

            total_duration = timedelta(0)
            for step in steps:
                duration = step.timestamp_fine - step.timestamp_inizio
                total_duration += duration

            return OrderManager._format_duration(total_duration)
        except Exception:
            return "Errore calcolo"

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
            # Se required_phases è esplicitamente fornito (anche se vuoto), usalo
            if required_phases is not None:
                actual_phases = required_phases
            elif articles:
                # Altrimenti, calcola dalle fasi richieste dagli articoli
                phase_order = ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'SPEDIZIONE']
                all_phases = set()
                for article in articles:
                    for p in article.get('required_phases', []):
                        all_phases.add(p)
                # Mantieni l'ordine canonico
                actual_phases = [p for p in phase_order if p in all_phases]
                if not actual_phases:
                    actual_phases = ['LASER', 'PIEGA', 'SALDATURA']
            else:
                # Se nessun articolo e required_phases non fornito, usa il default
                actual_phases = ['LASER', 'PIEGA', 'SALDATURA']

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

            # Inizializza ProcessingStep SOLO se ci sono fasi definite
            # Se required_phases è vuoto, aspetta l'approvazione del supervisore
            if order.required_phases:
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
                # Estrai PDF e DXF files
                pdf_file = None
                dxf_files = []
                if order.files:
                    for f in order.files:
                        if f.file_type == 'PDF':
                            pdf_file = f.filename
                        elif f.file_type == 'DXF':
                            dxf_files.append({'filename': f.filename, 'filepath': f.filepath})

                result.append({
                    'id': order.id,
                    'cliente': order.cliente,
                    'numero_ordine': order.numero_ordine if hasattr(order, 'numero_ordine') else None,
                    'data_consegna': order.data_consegna.isoformat(),
                    'total_quantity': order.total_quantity,
                    'status': order.status,
                    'articles': order.articles,
                    'required_phases': order.required_phases,
                    'pdf_file': pdf_file,  # Nome del PDF per il supervisore
                    'dxf_files': dxf_files,  # Lista DXF per il supervisore
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
        """Inizia l'elaborazione di una fase (o riprende se in pausa)"""
        session = get_session()
        try:
            processing_step = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.fase == phase
            ).first()

            if not processing_step:
                return False

            # HOTFIX v1.2.1: Permetti di riprendere una fase in pausa (timestamp_ultimo_partial settato, timestamp_fine NON settato)
            # Se timestamp_fine è settato, la fase è già completata → non permettere
            if processing_step.timestamp_fine:
                return False

            # Se timestamp_inizio NON è ancora settato, inizia la fase
            if not processing_step.timestamp_inizio:
                processing_step.timestamp_inizio = datetime.utcnow()
                processing_step.operatore = operatore
            # HOTFIX v1.2.1: Se timestamp_ultimo_partial è settato (fase in pausa), resettalo per riprendere
            elif processing_step.timestamp_ultimo_partial:
                processing_step.timestamp_ultimo_partial = None

            session.commit()
            return True
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

                # HOTFIX v1.2.1: Popola completed_articles solo con articoli che richiedono questa fase
                if order and order.articles:
                    # Articoli che richiedono questa fase
                    articles_requiring_phase = [
                        idx for idx, article in enumerate(order.articles)
                        if phase in article.get('required_phases', [])
                    ]
                    processing_step.completed_articles = articles_requiring_phase
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

                    # Crea notifica di completamento con tempi totali calcolati
                    total_time = OrderManager._calculate_order_total_time(order_id, session)
                    notification = OrderNotification(
                        id=str(uuid.uuid4()),
                        order_id=order_id,
                        tempi_totali=total_time
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

            # HOTFIX v1.2.1: Conta solo gli articoli che richiedono questa fase
            # (gli articoli potrebbero avere fasi diverse)
            articles_requiring_phase = sum(
                1 for article in order.articles
                if phase in article.get('required_phases', [])
            )
            all_articles_completed = len(processing_step.completed_articles) == articles_requiring_phase

            # Se tutti gli articoli sono completati, segna la fase come completata
            if all_articles_completed and not processing_step.timestamp_fine:
                processing_step.timestamp_fine = datetime.utcnow()
            # HOTFIX v1.2.1: Se solo alcuni articoli sono completati, traccia il partial completion
            elif not all_articles_completed:
                processing_step.timestamp_ultimo_partial = datetime.utcnow()
            
            processing_step.note = note
            session.commit()
            
            # Controlla se l'ordine è completamente finito
            all_steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id
            ).all()
            
            all_completed = all(step.timestamp_fine for step in all_steps)
            
            if all_completed:
                order.status = OrderStatus.SPEDITO.value
                # HOTFIX v1.2.1: Calcola i tempi totali di tutte le fasi
                total_time = OrderManager._calculate_order_total_time(order_id, session)
                notification = OrderNotification(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    tempi_totali=total_time
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
            
            # Estrai PDF e DXF files first
            pdf_file = None
            dxf_files = []
            if order.files:
                for f in order.files:
                    if f.file_type == 'PDF':
                        pdf_file = f.filename
                    elif f.file_type == 'DXF':
                        dxf_files.append({'filename': f.filename, 'filepath': f.filepath})

            # Helper function: match articolo code to DXF file
            def find_matching_dxf(article_code, dxf_list):
                """Trova il DXF che corrisponde al codice articolo"""
                if not article_code or not dxf_list:
                    return None

                for dxf in dxf_list:
                    dxf_name = dxf['filename'].replace('.dxf', '').lower()
                    code_lower = article_code.lower()

                    # Exact match
                    if code_lower == dxf_name:
                        return dxf

                    # Match ignoring suffix (-00, -01, etc)
                    code_base = code_lower.split('-')[0]
                    dxf_base = dxf_name.split('-')[0]
                    if code_base == dxf_base:
                        return dxf

                    # DXF name starts with code
                    if dxf_name.startswith(code_lower):
                        return dxf

                    # Code in DXF name
                    if code_lower in dxf_name:
                        return dxf

                return None

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

                # Find matching DXF file
                article_code = article.get('code', '')
                matching_dxf = find_matching_dxf(article_code, dxf_files)

                article_statuses.append({
                    "idx": article_idx,  # Indice articolo (per API parziale)
                    "name": article.get('name', 'N/A'),
                    "code": article_code,
                    "qty": article.get('qty', 0),
                    "required_phases": required_phases,
                    "completed_phases": completed,
                    "next_phase": next_phase if next_phase else "✅ Completato",
                    "dxf_file": matching_dxf  # DXF file associato all'articolo
                })

            return {
                "id": order.id,
                "cliente": order.cliente,
                "data_ricezione": order.data_ricezione.isoformat(),
                "data_consegna": order.data_consegna.isoformat(),
                "status": order.status,
                "total_quantity": order.total_quantity,
                "preventivo_minuti": order.preventivo_minuti,
                "pdf_file": pdf_file,  # Per il supervisore
                "dxf_files": dxf_files,  # Per il supervisore
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


class UserManager:
    """Gestore operazioni su utenti"""

    @staticmethod
    def get_user(user_id: str) -> dict | None:
        """Recupera un utente per ID, restituisce dict serializzabile"""
        session = get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                return {
                    'id': user.id,
                    'name': user.name,
                    'role': user.role,
                    'initials': user.initials,
                    'phase': user.phase,
                    'permissions': user.permissions,
                    'machines': user.machines,
                    'is_active': user.is_active,
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'created_at': user.created_at.isoformat() if user.created_at else None
                }
            return None
        finally:
            session.close()

    @staticmethod
    def get_all_users() -> list[dict]:
        """Recupera tutti gli utenti attivi"""
        session = get_session()
        try:
            users = session.query(User).filter(User.is_active == True).all()
            return [
                {
                    'id': u.id,
                    'name': u.name,
                    'role': u.role,
                    'initials': u.initials,
                    'phase': u.phase,
                    'permissions': u.permissions,
                    'machines': u.machines,
                    'is_active': u.is_active,
                    'last_login': u.last_login.isoformat() if u.last_login else None,
                    'created_at': u.created_at.isoformat() if u.created_at else None
                }
                for u in users
            ]
        finally:
            session.close()

    @staticmethod
    def authenticate(user_id: str) -> dict | None:
        """Autentica un utente (mock): aggiorna last_login e registra login nell'audit log"""
        session = get_session()
        try:
            user = session.query(User).filter(User.id == user_id, User.is_active == True).first()
            if user:
                user.last_login = datetime.utcnow()
                session.commit()

                # Log login in audit
                AuditManager.log(
                    user_id=user.id,
                    user_name=user.name,
                    action='LOGIN'
                )

                return {
                    'id': user.id,
                    'name': user.name,
                    'role': user.role,
                    'initials': user.initials,
                    'phase': user.phase,
                    'permissions': user.permissions,
                    'machines': user.machines,
                    'is_active': user.is_active,
                    'last_login': user.last_login.isoformat() if user.last_login else None
                }
            return None
        except Exception as e:
            session.rollback()
            return None
        finally:
            session.close()

    @staticmethod
    def create_user(user_id: str, name: str, role: str, phase: str,
                   permissions: list = None, machines: list = None,
                   initials: str = None) -> dict | None:
        """Crea un nuovo utente"""
        session = get_session()
        try:
            # Verifica che l'utente non esista già
            existing = session.query(User).filter(User.id == user_id).first()
            if existing:
                return None  # Utente esiste già

            user = User(
                id=user_id,
                name=name,
                role=role,
                phase=phase,
                permissions=permissions or [],
                machines=machines or [],
                initials=initials or name[:2].upper(),
                is_active=True,
                created_at=datetime.utcnow()
            )
            session.add(user)
            session.commit()

            # Log creazione utente
            AuditManager.log(
                user_id='admin',
                user_name='Sistema',
                action='CREA_UTENTE',
                entity_type='user',
                entity_id=user_id,
                detail=f'Creato utente {name} ({role})'
            )

            return {
                'id': user.id,
                'name': user.name,
                'role': user.role,
                'initials': user.initials,
                'phase': user.phase,
                'permissions': user.permissions,
                'machines': user.machines,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
        except Exception as e:
            session.rollback()
            return None
        finally:
            session.close()

    @staticmethod
    def update_user(user_id: str, name: str = None, role: str = None,
                   phase: str = None, permissions: list = None,
                   machines: list = None, is_active: bool = None) -> dict | None:
        """Modifica un utente esistente"""
        session = get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return None

            # Aggiorna solo i campi forniti
            if name:
                user.name = name
            if role:
                user.role = role
            if phase:
                user.phase = phase
            if permissions is not None:
                user.permissions = permissions
            if machines is not None:
                user.machines = machines
            if is_active is not None:
                user.is_active = is_active

            session.commit()

            # Log modifica utente
            AuditManager.log(
                user_id='admin',
                user_name='Sistema',
                action='MODIFICA_UTENTE',
                entity_type='user',
                entity_id=user_id,
                detail=f'Modificato utente {user.name}'
            )

            return {
                'id': user.id,
                'name': user.name,
                'role': user.role,
                'initials': user.initials,
                'phase': user.phase,
                'permissions': user.permissions,
                'machines': user.machines,
                'is_active': user.is_active,
                'last_login': user.last_login.isoformat() if user.last_login else None
            }
        except Exception as e:
            session.rollback()
            return None
        finally:
            session.close()

    @staticmethod
    def delete_user(user_id: str) -> bool:
        """Disattiva un utente (soft delete)"""
        session = get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return False

            user.is_active = False
            session.commit()

            # Log cancellazione utente
            AuditManager.log(
                user_id='admin',
                user_name='Sistema',
                action='DISATTIVA_UTENTE',
                entity_type='user',
                entity_id=user_id,
                detail=f'Disattivato utente {user.name}'
            )

            return True
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

class AuditManager:
    """Gestore operazioni di audit log"""

    @staticmethod
    def log(user_id: str = None, user_name: str = None, action: str = None,
            entity_type: str = None, entity_id: str = None, detail: str = None,
            ip_address: str = None) -> None:
        """Crea un record audit log (try/except silenzioso per non bloccare l'app)"""
        session = get_session()
        try:
            log_entry = AuditLog(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=user_id,
                user_name=user_name,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                detail=detail,
                ip_address=ip_address
            )
            session.add(log_entry)
            session.commit()
        except Exception as e:
            session.rollback()
            # Silenzioso: non bloccare l'app se l'audit fallisce
        finally:
            session.close()

    @staticmethod
    def get_recent(limit: int = 100, user_id: str = None) -> list[dict]:
        """Recupera log recenti, opzionalmente filtrati per utente"""
        session = get_session()
        try:
            query = session.query(AuditLog)
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)

            logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
            return [
                {
                    'id': log.id,
                    'timestamp': log.timestamp.isoformat(),
                    'user_id': log.user_id,
                    'user_name': log.user_name,
                    'action': log.action,
                    'entity_type': log.entity_type,
                    'entity_id': log.entity_id,
                    'detail': log.detail,
                    'ip_address': log.ip_address
                }
                for log in logs
            ]
        finally:
            session.close()

    @staticmethod
    def get_kpi_operai() -> list[dict]:
        """
        Calcola KPI per ogni operaio da processing_steps:
        - ordini completati (count WHERE timestamp_fine IS NOT NULL)
        - tempo medio per ordine
        - ultimo accesso (da users.last_login)
        """
        session = get_session()
        try:
            from sqlalchemy import func, and_

            # Query: JOIN processing_steps on operatore = user.name
            # WHERE timestamp_fine IS NOT NULL GROUP BY operatore
            query = session.query(
                User.name,
                User.id,
                User.role,
                User.initials,
                User.last_login,
                func.count(ProcessingStep.id).label('completed_phases_count')
            ).outerjoin(
                ProcessingStep,
                and_(
                    ProcessingStep.operatore == User.name,
                    ProcessingStep.timestamp_fine.isnot(None)
                )
            ).filter(
                User.is_active == True
            ).group_by(
                User.id
            ).all()

            kpi_list = []
            for row in query:
                name, user_id, role, initials, last_login, completed_count = row

                # Calcola tempo medio per operaio
                avg_time = session.query(
                    func.avg(ProcessingStep.timestamp_fine - ProcessingStep.timestamp_inizio)
                ).filter(
                    ProcessingStep.operatore == name,
                    ProcessingStep.timestamp_fine.isnot(None)
                ).scalar()

                tempo_medio = OrderManager._format_duration(avg_time) if avg_time else "N/A"

                # Conteggio ordini unici completati (non fasi, ma ordini)
                ordini_completati = session.query(
                    func.count(func.distinct(ProcessingStep.order_id))
                ).filter(
                    ProcessingStep.operatore == name,
                    ProcessingStep.timestamp_fine.isnot(None)
                ).scalar() or 0

                kpi_list.append({
                    'operaio': name,
                    'user_id': user_id,
                    'role': role,
                    'initials': initials,
                    'ordini_completati': ordini_completati,
                    'tempo_medio': tempo_medio,
                    'ultimo_accesso': last_login.isoformat() if last_login else 'Mai',
                    'efficienza': 85 + (ordini_completati % 15),  # Mock: 85-99%
                    'ritardi': max(0, 5 - (ordini_completati // 10)),  # Mock
                    'rating': min(5.0, 3.5 + (ordini_completati / 20))  # Mock: 3.5-5.0
                })

            return kpi_list
        finally:
            session.close()

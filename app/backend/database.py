"""CRUD operations for Order management"""
from datetime import datetime, timedelta
from sqlalchemy.orm.attributes import flag_modified
from .models import (
    Order, OrderFile, ProcessingStep, OrderNotification,
    FaseCorrente, get_session, User, AuditLog, Notification, OperatorClient
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
    def _calculate_total_hours(order_id: str, session) -> float:
        """Calcola le ore totali di lavorazione officina (escluso LASER)"""
        try:
            steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.fase != "LASER",
                ProcessingStep.timestamp_inizio.isnot(None),
                ProcessingStep.timestamp_fine.isnot(None)
            ).all()

            total_seconds = 0
            for step in steps:
                duration = step.timestamp_fine - step.timestamp_inizio
                total_seconds += int(duration.total_seconds())

            return total_seconds / 3600.0
        except Exception:
            return 0.0

    @staticmethod
    def create_order(cliente: str, data_consegna: str, destinazione: str = "LASER",
                     numero_ordine: str = None, prezzo_quotato: float = None,
                     note: str = "") -> Order:
        """
        Crea un nuovo ordine con routing dinamico.

        destinazione: "LASER" o "OFFICINA" — dove l'impiegata manda l'ordine.
        Se OFFICINA, auto-assegna operatore da operator_clients.
        """
        session = get_session()

        try:
            # Auto-assegna operatore se destinazione è OFFICINA
            operatore_assegnato = None
            if destinazione == "OFFICINA":
                # Cerca operatore assegnato a questo cliente
                assignment = session.query(OperatorClient).filter(
                    OperatorClient.client_name == cliente
                ).first()
                if assignment:
                    operatore_assegnato = assignment.operator_id

            # Determina fase_corrente
            fase_corrente = "LASER" if destinazione == "LASER" else "PIEGA"

            order = Order(
                id=str(uuid.uuid4()),
                cliente=cliente,
                numero_ordine=numero_ordine,
                data_consegna=datetime.fromisoformat(data_consegna),
                fase_corrente=fase_corrente,
                operatore_assegnato=operatore_assegnato,
                prezzo_quotato=prezzo_quotato,
                note=note
            )

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
    def get_all_orders_dict(cliente: str = None, status: str = None,
                            fase_corrente: str = None, operatore: str = None) -> list:
        """Recupera ordini come dizionari con filtri per il nuovo workflow"""
        session = get_session()
        try:
            query = session.query(Order)
            if cliente:
                query = query.filter(Order.cliente == cliente)
            if status:
                query = query.filter(Order.status == status)
            if fase_corrente:
                query = query.filter(Order.fase_corrente == fase_corrente)
            if operatore:
                query = query.filter(Order.operatore_assegnato == operatore)

            orders = query.order_by(Order.data_consegna.asc()).all()
            result = []

            for order in orders:
                pdf_file = None
                dxf_files = []
                if order.files:
                    for f in order.files:
                        if f.file_type == 'PDF':
                            pdf_file = f.filename
                        elif f.file_type == 'DXF':
                            dxf_files.append({'filename': f.filename, 'filepath': f.filepath})

                # Recupera nome operatore assegnato
                operatore_nome = None
                if order.operatore_assegnato:
                    user = session.query(User).filter(User.id == order.operatore_assegnato).first()
                    if user:
                        operatore_nome = user.name

                result.append({
                    'id': order.id,
                    'cliente': order.cliente,
                    'numero_ordine': order.numero_ordine,
                    'data_ricezione': order.data_ricezione.isoformat() if order.data_ricezione else None,
                    'data_consegna': order.data_consegna.isoformat(),
                    'status': order.status,
                    'fase_corrente': order.fase_corrente,
                    'operatore_assegnato': order.operatore_assegnato,
                    'operatore_nome': operatore_nome,
                    'prezzo_quotato': order.prezzo_quotato,
                    'pdf_file': pdf_file,
                    'dxf_files': dxf_files,
                    'note': order.note,
                    'processing_steps': [
                        {
                            'id': ps.id,
                            'fase': ps.fase,
                            'timestamp_inizio': ps.timestamp_inizio.isoformat() if ps.timestamp_inizio else None,
                            'timestamp_fine': ps.timestamp_fine.isoformat() if ps.timestamp_fine else None,
                            'operatore': ps.operatore,
                            'fase_successiva': ps.fase_successiva,
                            'completamento_parziale': ps.completamento_parziale,
                            'note': ps.note
                        }
                        for ps in order.processing_steps
                    ] if order.processing_steps else []
                })

            return result
        finally:
            session.close()
    
    @staticmethod
    def get_orders_by_phase(phase: str, operatore_id: str = None) -> list:
        """Recupera ordini per fase corrente (e opzionalmente per operatore)"""
        session = get_session()
        try:
            query = session.query(Order).filter(Order.fase_corrente == phase)
            if operatore_id:
                query = query.filter(Order.operatore_assegnato == operatore_id)
            return query.order_by(Order.data_consegna.asc()).all()
        finally:
            session.close()
    
    @staticmethod
    def start_phase(order_id: str, phase: str, operatore: str = "") -> bool:
        """Inizia una fase di lavorazione — crea ProcessingStep con timer"""
        session = get_session()
        try:
            # Crea nuovo ProcessingStep per questa fase
            step = ProcessingStep(
                id=str(uuid.uuid4()),
                order_id=order_id,
                fase=phase,
                timestamp_inizio=datetime.utcnow(),
                operatore=operatore
            )
            session.add(step)

            # Aggiorna fase_corrente dell'ordine
            order = session.query(Order).filter(Order.id == order_id).first()
            if order:
                order.fase_corrente = phase

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    @staticmethod
    def complete_phase(order_id: str, phase: str, fase_successiva: str = None,
                       completamento_parziale: bool = False, note: str = "",
                       operatore: str = "") -> dict:
        """
        Completa una fase con routing dinamico.

        fase_successiva: "PIEGA", "SALDATURA", "PULIZIA", "LASER", "COMPLETATO"
        completamento_parziale: True = ordine non del tutto finito (PARZIALE)
        """
        session = get_session()
        try:
            # Trova l'ultimo step attivo (non completato) per questa fase
            processing_step = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.fase == phase,
                ProcessingStep.timestamp_fine.is_(None)
            ).order_by(ProcessingStep.timestamp_inizio.desc()).first()

            if not processing_step:
                return {"success": False, "error": "Fase non trovata o già completata"}

            # Completa lo step
            processing_step.timestamp_fine = datetime.utcnow()
            processing_step.note = note
            processing_step.fase_successiva = fase_successiva
            processing_step.completamento_parziale = completamento_parziale
            if operatore and not processing_step.operatore:
                processing_step.operatore = operatore

            # Aggiorna l'ordine
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Ordine non trovato"}

            if completamento_parziale:
                order.fase_corrente = "PARZIALE"
                order.status = "PARZIALE"
            elif fase_successiva == "COMPLETATO":
                order.fase_corrente = "COMPLETATO"
                order.status = "COMPLETATO"
                # Calcola tempi totali e crea notifica
                total_time = OrderManager._calculate_order_total_time(order_id, session)
                notification = OrderNotification(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    tempi_totali=total_time
                )
                session.add(notification)
            elif fase_successiva == "LASER":
                order.fase_corrente = "LASER"
            elif fase_successiva:
                order.fase_corrente = fase_successiva

            session.commit()

            return {
                "success": True,
                "order_id": order_id,
                "phase": phase,
                "fase_successiva": fase_successiva,
                "completamento_parziale": completamento_parziale,
                "all_completed": fase_successiva == "COMPLETATO"
            }

        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()
    
    @staticmethod
    def complete_laser(order_id: str, operatore: str = "") -> dict:
        """Operatore laser: segna taglio completato (no timer, solo completamento)"""
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Ordine non trovato"}

            # Crea step LASER senza timestamp_inizio (no time tracking per laser)
            step = ProcessingStep(
                id=str(uuid.uuid4()),
                order_id=order_id,
                fase="LASER",
                timestamp_fine=datetime.utcnow(),
                operatore=operatore,
                fase_successiva="OFFICINA"
            )
            session.add(step)

            # L'ordine torna all'operatore officina assegnato
            # fase_corrente va a una fase generica "OFFICINA" che l'operatore poi specifica
            order.fase_corrente = "PIEGA"  # Default: dopo laser va in piega (operatore poi sceglie)

            session.commit()
            return {"success": True, "order_id": order_id}

        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def send_to_laser(order_id: str, operatore: str = "") -> dict:
        """Operatore officina rimanda ordine al laser"""
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Ordine non trovato"}

            order.fase_corrente = "LASER"
            session.commit()
            return {"success": True, "order_id": order_id}

        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def reassign_order(order_id: str, new_operator_id: str) -> dict:
        """Capo officina: riassegna ordine a un altro operatore"""
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Ordine non trovato"}

            order.operatore_assegnato = new_operator_id
            session.commit()
            return {"success": True, "order_id": order_id, "new_operator": new_operator_id}

        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def correct_time(step_id: str, new_start: str = None, new_end: str = None) -> dict:
        """Capo officina: corregge timestamp di un processing step"""
        session = get_session()
        try:
            step = session.query(ProcessingStep).filter(ProcessingStep.id == step_id).first()
            if not step:
                return {"success": False, "error": "Step non trovato"}

            if new_start:
                step.timestamp_inizio = datetime.fromisoformat(new_start)
            if new_end:
                step.timestamp_fine = datetime.fromisoformat(new_end)

            session.commit()
            return {"success": True, "step_id": step_id}

        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def move_phase(order_id: str, new_phase: str) -> dict:
        """Capo officina: sposta ordine a qualsiasi fase"""
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Ordine non trovato"}

            order.fase_corrente = new_phase
            if new_phase == "COMPLETATO":
                order.status = "COMPLETATO"
            elif new_phase == "PARZIALE":
                order.status = "PARZIALE"
            else:
                order.status = "IN_LAVORAZIONE"

            session.commit()
            return {"success": True, "order_id": order_id, "new_phase": new_phase}

        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def get_order_details(order_id: str) -> dict:
        """Recupera dettagli completi ordine con storico fasi"""
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"error": "Ordine non trovato"}

            processing_steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id
            ).order_by(ProcessingStep.timestamp_inizio.asc()).all()

            pdf_file = None
            dxf_files = []
            if order.files:
                for f in order.files:
                    if f.file_type == 'PDF':
                        pdf_file = f.filename
                    elif f.file_type == 'DXF':
                        dxf_files.append({'filename': f.filename, 'filepath': f.filepath})

            # Recupera nome operatore assegnato
            operatore_nome = None
            if order.operatore_assegnato:
                user = session.query(User).filter(User.id == order.operatore_assegnato).first()
                if user:
                    operatore_nome = user.name

            return {
                "id": order.id,
                "cliente": order.cliente,
                "numero_ordine": order.numero_ordine,
                "data_ricezione": order.data_ricezione.isoformat() if order.data_ricezione else None,
                "data_consegna": order.data_consegna.isoformat(),
                "status": order.status,
                "fase_corrente": order.fase_corrente,
                "operatore_assegnato": order.operatore_assegnato,
                "operatore_nome": operatore_nome,
                "prezzo_quotato": order.prezzo_quotato,
                "pdf_file": pdf_file,
                "dxf_files": dxf_files,
                "note": order.note,
                "processing_steps": [
                    {
                        "id": s.id,
                        "fase": s.fase,
                        "timestamp_inizio": s.timestamp_inizio.isoformat() + 'Z' if s.timestamp_inizio else None,
                        "timestamp_fine": s.timestamp_fine.isoformat() + 'Z' if s.timestamp_fine else None,
                        "operatore": s.operatore,
                        "note": s.note,
                        "fase_successiva": s.fase_successiva,
                        "completamento_parziale": s.completamento_parziale,
                        "durata": OrderManager._format_duration(
                            s.timestamp_fine - s.timestamp_inizio
                        ) if s.timestamp_inizio and s.timestamp_fine else None
                    }
                    for s in processing_steps
                ]
            }
        finally:
            session.close()


class UserManager:
    """Gestore operazioni su utenti"""

    @staticmethod
    def _serialize_user(user) -> dict:
        """Serializza un utente in dict"""
        return {
            'id': user.id,
            'name': user.name,
            'role': user.role,
            'initials': user.initials,
            'phase': user.phase,
            'permissions': user.permissions,
            'machines': user.machines,
            'is_capo': user.is_capo,
            'is_active': user.is_active,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'created_at': user.created_at.isoformat() if user.created_at else None
        }

    @staticmethod
    def get_user(user_id: str) -> dict | None:
        """Recupera un utente per ID, restituisce dict serializzabile"""
        session = get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                return UserManager._serialize_user(user)
            return None
        finally:
            session.close()

    @staticmethod
    def get_all_users() -> list[dict]:
        """Recupera tutti gli utenti attivi"""
        session = get_session()
        try:
            users = session.query(User).filter(User.is_active == True).all()
            return [UserManager._serialize_user(u) for u in users]
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

                AuditManager.log(
                    user_id=user.id,
                    user_name=user.name,
                    action='LOGIN'
                )

                return UserManager._serialize_user(user)
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

            AuditManager.log(
                user_id='admin',
                user_name='Sistema',
                action='CREA_UTENTE',
                entity_type='user',
                entity_id=user_id,
                detail=f'Creato utente {name} ({role})'
            )

            return UserManager._serialize_user(user)
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

            AuditManager.log(
                user_id='admin',
                user_name='Sistema',
                action='MODIFICA_UTENTE',
                entity_type='user',
                entity_id=user_id,
                detail=f'Modificato utente {user.name}'
            )

            return UserManager._serialize_user(user)
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


class ArchiveManager:
    """Gestore operazioni su archivio ordini completati"""

    @staticmethod
    def _calculate_phase_times(order_id: str, session) -> dict:
        """
        Calcola i tempi per ogni fase completata di un ordine
        Ritorna dict con fasi come chiavi e durate come valori (formato stringa)
        """
        try:
            steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.timestamp_inizio.isnot(None),
                ProcessingStep.timestamp_fine.isnot(None)
            ).all()

            phase_times = {}
            for step in steps:
                duration = step.timestamp_fine - step.timestamp_inizio
                phase_times[step.fase] = OrderManager._format_duration(duration)

            return phase_times
        except Exception:
            return {}

    @staticmethod
    def get_completed_orders(filters: dict = None, page: int = 1, limit: int = 10,
                            sort_by: str = 'data_consegna', sort_dir: str = 'desc') -> dict:
        """
        Recupera ordini completati (status = SPEDITO) con paginazione e filtri

        filters: {
            'cliente': 'nome cliente',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31'
        }

        Ritorna: {
            'orders': [...],
            'total': <count>,
            'page': <page>,
            'pages': <total_pages>
        }
        """
        session = get_session()
        try:
            from sqlalchemy import func

            # Query base: ordini completati o parziali
            query = session.query(Order).filter(
                Order.status.in_(["COMPLETATO", "PARZIALE"])
            )

            # Applica filtri
            if filters:
                if 'cliente' in filters and filters['cliente']:
                    query = query.filter(Order.cliente.ilike(f"%{filters['cliente']}%"))

                if 'date_from' in filters and filters['date_from']:
                    date_from = datetime.fromisoformat(filters['date_from'])
                    query = query.filter(Order.data_consegna >= date_from)

                if 'date_to' in filters and filters['date_to']:
                    date_to = datetime.fromisoformat(filters['date_to'])
                    date_to = date_to.replace(hour=23, minute=59, second=59)
                    query = query.filter(Order.data_consegna <= date_to)

            total = query.count()

            if sort_dir.lower() == 'asc':
                query = query.order_by(getattr(Order, sort_by).asc())
            else:
                query = query.order_by(getattr(Order, sort_by).desc())

            offset = (page - 1) * limit
            orders = query.offset(offset).limit(limit).all()

            orders_data = []
            for order in orders:
                notification = session.query(OrderNotification).filter(
                    OrderNotification.order_id == order.id
                ).first()

                total_time = notification.tempi_totali if notification else "N/A"

                last_step = session.query(ProcessingStep).filter(
                    ProcessingStep.order_id == order.id,
                    ProcessingStep.timestamp_fine.isnot(None)
                ).order_by(ProcessingStep.timestamp_fine.desc()).first()

                completion_date = last_step.timestamp_fine if last_step else None

                # Calcola tempi per fase e margine
                phase_times = ArchiveManager._calculate_phase_times(order.id, session)
                total_hours = OrderManager._calculate_total_hours(order.id, session)
                costo_orario = 25.0  # Configurabile
                costo_manodopera = total_hours * costo_orario
                margine = None
                margine_pct = None
                if order.prezzo_quotato and order.prezzo_quotato > 0:
                    margine = order.prezzo_quotato - costo_manodopera
                    margine_pct = round((margine / order.prezzo_quotato) * 100, 1)

                orders_data.append({
                    'id': order.id,
                    'numero_ordine': order.numero_ordine or order.id[:8],
                    'cliente': order.cliente,
                    'data_consegna': order.data_consegna.isoformat(),
                    'data_completamento': completion_date.isoformat() if completion_date else None,
                    'tempo_totale': total_time,
                    'prezzo_quotato': order.prezzo_quotato,
                    'costo_manodopera': round(costo_manodopera, 2),
                    'margine': round(margine, 2) if margine is not None else None,
                    'margine_pct': margine_pct,
                    'phase_times': phase_times,
                    'status': order.status
                })

            total_pages = (total + limit - 1) // limit

            return {
                'orders': orders_data,
                'total': total,
                'page': page,
                'pages': total_pages
            }
        finally:
            session.close()

    @staticmethod
    def get_order_details(order_id: str) -> dict | None:
        """
        Recupera dettagli completi di un ordine con fasi e tempi
        """
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return None

            # Recupera processing steps
            steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id
            ).order_by(ProcessingStep.fase).all()

            # Calcola tempi per fase
            phase_times = ArchiveManager._calculate_phase_times(order_id, session)

            # Recupera notifica di completamento
            notification = session.query(OrderNotification).filter(
                OrderNotification.order_id == order_id
            ).first()

            # Calcola data di completamento (ultima fase)
            completion_date = None
            if steps:
                last_completed = [s for s in steps if s.timestamp_fine]
                if last_completed:
                    completion_date = max(s.timestamp_fine for s in last_completed)

            # Calcola margine
            total_hours = OrderManager._calculate_total_hours(order_id, session)
            costo_orario = 25.0
            costo_manodopera = total_hours * costo_orario
            margine = None
            margine_pct = None
            if order.prezzo_quotato and order.prezzo_quotato > 0:
                margine = order.prezzo_quotato - costo_manodopera
                margine_pct = round((margine / order.prezzo_quotato) * 100, 1)

            return {
                'id': order.id,
                'numero_ordine': order.numero_ordine or order.id[:8],
                'cliente': order.cliente,
                'data_consegna': order.data_consegna.isoformat(),
                'data_completamento': completion_date.isoformat() if completion_date else None,
                'tempo_totale': notification.tempi_totali if notification else "N/A",
                'prezzo_quotato': order.prezzo_quotato,
                'costo_manodopera': round(costo_manodopera, 2),
                'margine': round(margine, 2) if margine is not None else None,
                'margine_pct': margine_pct,
                'note': order.note or '',
                'fasi': [
                    {
                        'fase': step.fase,
                        'operatore': step.operatore or 'N/A',
                        'data_inizio': step.timestamp_inizio.isoformat() if step.timestamp_inizio else None,
                        'data_fine': step.timestamp_fine.isoformat() if step.timestamp_fine else None,
                        'tempo': phase_times.get(step.fase, 'N/A'),
                        'fase_successiva': step.fase_successiva,
                        'completamento_parziale': step.completamento_parziale
                    }
                    for step in steps
                ],
                'status': order.status
            }
        finally:
            session.close()

    @staticmethod
    def export_csv_data(filters: dict = None) -> list[dict]:
        """
        Esporta dati di archivio in formato CSV (lista di dict serializzabili)

        Ritorna lista di dict pronta per conversione a CSV
        """
        session = get_session()
        try:
            from sqlalchemy import func

            query = session.query(Order).filter(
                Order.status.in_(["COMPLETATO", "PARZIALE"])
            )

            if filters:
                if 'cliente' in filters and filters['cliente']:
                    query = query.filter(Order.cliente.ilike(f"%{filters['cliente']}%"))
                if 'date_from' in filters and filters['date_from']:
                    date_from = datetime.fromisoformat(filters['date_from'])
                    query = query.filter(Order.data_consegna >= date_from)
                if 'date_to' in filters and filters['date_to']:
                    date_to = datetime.fromisoformat(filters['date_to'])
                    date_to = date_to.replace(hour=23, minute=59, second=59)
                    query = query.filter(Order.data_consegna <= date_to)

            orders = query.order_by(Order.data_consegna.desc()).all()

            csv_data = []
            for order in orders:
                notification = session.query(OrderNotification).filter(
                    OrderNotification.order_id == order.id
                ).first()

                last_step = session.query(ProcessingStep).filter(
                    ProcessingStep.order_id == order.id,
                    ProcessingStep.timestamp_fine.isnot(None)
                ).order_by(ProcessingStep.timestamp_fine.desc()).first()

                completion_date = last_step.timestamp_fine if last_step else None
                phase_times = ArchiveManager._calculate_phase_times(order.id, session)
                total_hours = OrderManager._calculate_total_hours(order.id, session)
                costo_orario = 25.0
                costo_manodopera = total_hours * costo_orario
                margine = None
                if order.prezzo_quotato and order.prezzo_quotato > 0:
                    margine = order.prezzo_quotato - costo_manodopera

                csv_data.append({
                    'ID Ordine': order.numero_ordine or order.id[:8],
                    'Cliente': order.cliente,
                    'Data Consegna': order.data_consegna.strftime('%Y-%m-%d'),
                    'Data Completamento': completion_date.strftime('%Y-%m-%d %H:%M') if completion_date else 'N/A',
                    'PIEGA': phase_times.get('PIEGA', '-'),
                    'SALDATURA': phase_times.get('SALDATURA', '-'),
                    'PULIZIA': phase_times.get('PULIZIA', '-'),
                    'Tempo Totale': notification.tempi_totali if notification else 'N/A',
                    'Prezzo Quotato': f"{order.prezzo_quotato:.2f}" if order.prezzo_quotato else 'N/A',
                    'Costo Manodopera': f"{costo_manodopera:.2f}",
                    'Margine': f"{margine:.2f}" if margine is not None else 'N/A',
                    'Status': order.status,
                    'Note': order.note or ''
                })

            return csv_data
        finally:
            session.close()


class NotificationManager:
    """Gestore notifiche UI tipo WhatsApp per supervisore/admin"""

    @staticmethod
    def create_notification(user_id: str, order_id: str, title: str, message: str, notification_type: str = 'order') -> dict:
        """Crea una notifica e la salva nel DB"""
        session = get_session()
        try:
            notification = Notification(
                id=str(uuid.uuid4()),
                user_id=user_id,
                order_id=order_id,
                title=title,
                message=message,
                notification_type=notification_type,
                is_read=False,
                is_deleted=False
            )
            session.add(notification)
            session.commit()
            return {
                'id': notification.id,
                'timestamp': notification.timestamp.isoformat() + 'Z',
                'user_id': user_id,
                'order_id': order_id,
                'title': title,
                'message': message,
                'notification_type': notification_type,
                'is_read': notification.is_read,
                'is_deleted': notification.is_deleted
            }
        except Exception as e:
            session.rollback()
            print(f"[ERROR] create_notification: {e}")
            return None
        finally:
            session.close()

    @staticmethod
    def get_notifications(user_id: str, limit: int = 50, unread_only: bool = False) -> list:
        """Recupera notifiche per un utente (non cancellate)"""
        session = get_session()
        try:
            query = session.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.is_deleted == False
            )

            if unread_only:
                query = query.filter(Notification.is_read == False)

            notifications = query.order_by(Notification.timestamp.desc()).limit(limit).all()

            result = []
            for n in notifications:
                result.append({
                    'id': n.id,
                    'timestamp': n.timestamp.isoformat() + 'Z',
                    'user_id': n.user_id,
                    'order_id': n.order_id,
                    'title': n.title,
                    'message': n.message,
                    'notification_type': n.notification_type,
                    'is_read': n.is_read,
                    'is_deleted': n.is_deleted
                })
            return result
        except Exception as e:
            print(f"[ERROR] get_notifications: {e}")
            return []
        finally:
            session.close()

    @staticmethod
    def delete_notification(notification_id: str) -> bool:
        """Soft delete di una notifica (is_deleted = True)"""
        session = get_session()
        try:
            notification = session.query(Notification).filter(
                Notification.id == notification_id
            ).first()

            if notification:
                notification.is_deleted = True
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f"[ERROR] delete_notification: {e}")
            return False
        finally:
            session.close()

    @staticmethod
    def delete_all_notifications(user_id: str) -> bool:
        """Cancella tutte le notifiche di un utente (soft delete)"""
        session = get_session()
        try:
            notifications = session.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.is_deleted == False
            ).all()

            for n in notifications:
                n.is_deleted = True

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"[ERROR] delete_all_notifications: {e}")
            return False
        finally:
            session.close()

    @staticmethod
    def mark_as_read(notification_id: str) -> bool:
        """Marca una notifica come letta"""
        session = get_session()
        try:
            notification = session.query(Notification).filter(
                Notification.id == notification_id
            ).first()

            if notification:
                notification.is_read = True
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f"[ERROR] mark_as_read: {e}")
            return False
        finally:
            session.close()

    @staticmethod
    def get_unread_count(user_id: str) -> int:
        """Conta notifiche non lette per un utente"""
        session = get_session()
        try:
            count = session.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.is_read == False,
                Notification.is_deleted == False
            ).count()
            return count
        except Exception as e:
            print(f"[ERROR] get_unread_count: {e}")
            return 0
        finally:
            session.close()


class OperatorClientManager:
    """Gestore assegnazioni operatore-cliente"""

    @staticmethod
    def get_all() -> list[dict]:
        """Recupera tutte le assegnazioni operatore-cliente"""
        session = get_session()
        try:
            assignments = session.query(OperatorClient).all()
            result = []
            for a in assignments:
                operator = session.query(User).filter(User.id == a.operator_id).first()
                result.append({
                    'id': a.id,
                    'operator_id': a.operator_id,
                    'operator_name': operator.name if operator else 'N/A',
                    'client_name': a.client_name
                })
            return result
        finally:
            session.close()

    @staticmethod
    def get_by_operator(operator_id: str) -> list[dict]:
        """Recupera clienti assegnati a un operatore"""
        session = get_session()
        try:
            assignments = session.query(OperatorClient).filter(
                OperatorClient.operator_id == operator_id
            ).all()
            return [{'id': a.id, 'client_name': a.client_name} for a in assignments]
        finally:
            session.close()

    @staticmethod
    def find_operator_for_client(client_name: str) -> str | None:
        """Trova l'operatore assegnato a un cliente"""
        session = get_session()
        try:
            assignment = session.query(OperatorClient).filter(
                OperatorClient.client_name == client_name
            ).first()
            return assignment.operator_id if assignment else None
        finally:
            session.close()

    @staticmethod
    def create(operator_id: str, client_name: str) -> dict:
        """Crea una nuova assegnazione operatore-cliente"""
        session = get_session()
        try:
            assignment = OperatorClient(
                id=str(uuid.uuid4()),
                operator_id=operator_id,
                client_name=client_name
            )
            session.add(assignment)
            session.commit()
            return {
                'id': assignment.id,
                'operator_id': operator_id,
                'client_name': client_name
            }
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def delete(assignment_id: str) -> bool:
        """Rimuovi un'assegnazione"""
        session = get_session()
        try:
            assignment = session.query(OperatorClient).filter(
                OperatorClient.id == assignment_id
            ).first()
            if assignment:
                session.delete(assignment)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()


class AlertManager:
    """Gestore alert automatici per capo officina"""

    @staticmethod
    def check_alerts() -> list[dict]:
        """Controlla condizioni di alert e genera notifiche se necessario"""
        session = get_session()
        alerts = []
        now = datetime.utcnow()

        try:
            # 1. Timer attivo da > 4 ore
            active_steps = session.query(ProcessingStep).filter(
                ProcessingStep.timestamp_inizio.isnot(None),
                ProcessingStep.timestamp_fine.is_(None)
            ).all()

            for step in active_steps:
                elapsed = now - step.timestamp_inizio
                hours = elapsed.total_seconds() / 3600

                if hours > 4:
                    order = session.query(Order).filter(Order.id == step.order_id).first()
                    alerts.append({
                        'type': 'warning',
                        'category': 'timer_lungo',
                        'order_id': step.order_id,
                        'cliente': order.cliente if order else 'N/A',
                        'fase': step.fase,
                        'operatore': step.operatore,
                        'ore': round(hours, 1),
                        'message': f'Timer attivo da {round(hours, 1)}h su {step.fase} — {order.cliente if order else "N/A"}'
                    })

            # 2. Ordine fermo nella stessa fase > 8 ore (senza step attivi)
            active_orders = session.query(Order).filter(
                Order.fase_corrente.notin_(['COMPLETATO', 'PARZIALE']),
                Order.status != 'ARCHIVIATO'
            ).all()

            for order in active_orders:
                # Ultimo step per questo ordine
                last_step = session.query(ProcessingStep).filter(
                    ProcessingStep.order_id == order.id
                ).order_by(ProcessingStep.timestamp_inizio.desc()).first()

                if last_step and last_step.timestamp_fine:
                    idle = now - last_step.timestamp_fine
                    idle_hours = idle.total_seconds() / 3600

                    if idle_hours > 8:
                        alerts.append({
                            'type': 'danger',
                            'category': 'ordine_fermo',
                            'order_id': order.id,
                            'cliente': order.cliente,
                            'fase': order.fase_corrente,
                            'operatore': order.operatore_assegnato,
                            'ore': round(idle_hours, 1),
                            'message': f'Ordine fermo in {order.fase_corrente} da {round(idle_hours, 1)}h — {order.cliente}'
                        })

            # 3. Scadenza domani e ordine non completato
            tomorrow = now.replace(hour=23, minute=59, second=59) + timedelta(days=1)

            urgent_orders = session.query(Order).filter(
                Order.data_consegna <= tomorrow,
                Order.fase_corrente.notin_(['COMPLETATO', 'PARZIALE']),
                Order.status != 'ARCHIVIATO'
            ).all()

            for order in urgent_orders:
                days_left = (order.data_consegna - now).days
                if days_left <= 1:
                    alerts.append({
                        'type': 'urgent',
                        'category': 'scadenza',
                        'order_id': order.id,
                        'cliente': order.cliente,
                        'fase': order.fase_corrente,
                        'operatore': order.operatore_assegnato,
                        'scadenza': order.data_consegna.isoformat(),
                        'message': f'Scadenza {"OGGI" if days_left <= 0 else "domani"}: {order.cliente} (fase {order.fase_corrente})'
                    })

            return alerts

        except Exception as e:
            print(f"[ERROR] check_alerts: {e}")
            return []
        finally:
            session.close()


class KPIManager:
    """Calcolo KPI per dashboard Capo Officina"""

    @staticmethod
    def get_dashboard_kpi() -> dict:
        session = get_session()
        try:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # === RIEPILOGO ===
            all_orders = session.query(Order).all()
            ordini_attivi = sum(1 for o in all_orders if o.status not in ('COMPLETATO', 'SPEDITO'))
            completati_oggi = sum(1 for o in all_orders if o.status == 'COMPLETATO' and
                session.query(ProcessingStep).filter(
                    ProcessingStep.order_id == o.id,
                    ProcessingStep.timestamp_fine != None,
                    ProcessingStep.timestamp_fine >= today_start
                ).first() is not None)
            in_ritardo = sum(1 for o in all_orders
                if o.data_consegna and o.data_consegna < now
                and o.status not in ('COMPLETATO', 'SPEDITO'))
            completati_totali = sum(1 for o in all_orders if o.status == 'COMPLETATO')
            completati_in_tempo = sum(1 for o in all_orders
                if o.status == 'COMPLETATO' and o.data_consegna
                and any(s.timestamp_fine and s.timestamp_fine <= o.data_consegna
                    for s in session.query(ProcessingStep).filter(ProcessingStep.order_id == o.id).all()))
            efficienza = round((completati_in_tempo / completati_totali * 100) if completati_totali > 0 else 100)

            riepilogo = {
                'ordini_attivi': ordini_attivi,
                'completati_oggi': completati_oggi,
                'in_ritardo': in_ritardo,
                'efficienza_puntualita': efficienza
            }

            # === KPI OPERATORI ===
            operatori_kpi = []
            operators = session.query(User).filter(
                User.role.in_(['Operaio Officina', 'Operaio Laser']),
                User.is_active == True
            ).all()

            for op in operators:
                # Steps completati da questo operatore
                completed_steps = session.query(ProcessingStep).filter(
                    ProcessingStep.operatore == op.name,
                    ProcessingStep.timestamp_fine != None
                ).all()

                # Steps completati oggi
                steps_oggi = [s for s in completed_steps if s.timestamp_fine >= today_start]

                # Tempo medio
                durations = []
                for s in completed_steps:
                    if s.timestamp_inizio and s.timestamp_fine:
                        durations.append((s.timestamp_fine - s.timestamp_inizio).total_seconds())
                tempo_medio_min = round(sum(durations) / len(durations) / 60) if durations else None

                # Ordini unici completati
                ordini_unici = len(set(s.order_id for s in completed_steps))

                # Step attivo (in corso)
                active_step = session.query(ProcessingStep).filter(
                    ProcessingStep.operatore == op.name,
                    ProcessingStep.timestamp_inizio != None,
                    ProcessingStep.timestamp_fine == None
                ).first()

                # Clienti assegnati
                clienti = session.query(OperatorClient).filter(
                    OperatorClient.operator_id == op.id
                ).count()

                # Online = last_login oggi
                is_online = op.last_login and op.last_login >= today_start

                # Efficienza: rapporto ordini completati / tempo
                eff = min(100, round((ordini_unici / max(len(durations), 1)) * 100)) if durations else 0

                operatori_kpi.append({
                    'id': op.id,
                    'name': op.name,
                    'initials': op.initials,
                    'role': op.role,
                    'phase': op.phase,
                    'is_online': is_online,
                    'ordini_completati': ordini_unici,
                    'ordini_oggi': len(set(s.order_id for s in steps_oggi)),
                    'tempo_medio_minuti': tempo_medio_min,
                    'clienti_assegnati': clienti,
                    'fase_attiva': active_step.fase if active_step else None,
                    'ordine_attivo': active_step.order_id if active_step else None,
                    'efficienza': eff
                })

            # === KPI FASI/MACCHINARI ===
            fasi_kpi = []
            for fase_nome in ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA']:
                # In coda: ordini con fase_corrente = questa fase, senza step attivo
                in_coda_orders = session.query(Order).filter(
                    Order.fase_corrente == fase_nome,
                    Order.status.notin_(['COMPLETATO', 'SPEDITO'])
                ).all()
                active_in_fase = session.query(ProcessingStep).filter(
                    ProcessingStep.fase == fase_nome,
                    ProcessingStep.timestamp_inizio != None,
                    ProcessingStep.timestamp_fine == None
                ).count()
                in_coda = max(0, len(in_coda_orders) - active_in_fase)

                # Completati
                completed_in_fase = session.query(ProcessingStep).filter(
                    ProcessingStep.fase == fase_nome,
                    ProcessingStep.timestamp_fine != None
                ).all()
                completati_oggi_fase = sum(1 for s in completed_in_fase if s.timestamp_fine >= today_start)

                # Tempo medio
                durations_fase = []
                for s in completed_in_fase:
                    if s.timestamp_inizio and s.timestamp_fine:
                        durations_fase.append((s.timestamp_fine - s.timestamp_inizio).total_seconds())
                tempo_medio_fase = round(sum(durations_fase) / len(durations_fase) / 60) if durations_fase else None

                fasi_kpi.append({
                    'fase': fase_nome,
                    'in_coda': in_coda,
                    'in_corso': active_in_fase,
                    'completati_totale': len(completed_in_fase),
                    'completati_oggi': completati_oggi_fase,
                    'tempo_medio_minuti': tempo_medio_fase
                })

            return {
                'success': True,
                'riepilogo': riepilogo,
                'operatori': operatori_kpi,
                'fasi': fasi_kpi
            }

        except Exception as e:
            print(f"[ERROR] get_dashboard_kpi: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            session.close()

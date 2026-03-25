"""CRUD operations for Order management"""
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified
from .models import (
    Order, OrderFile, ProcessingStep, OrderNotification, PhaseSession,
    FaseCorrente, get_session, User, AuditLog, Notification, OperatorClient,
    PhaseDelegation, SupportRequest
)
import uuid
import json
import logging

logger = logging.getLogger(__name__)

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
                     numero_ordine: str = "", note: str = "") -> Order:
        """
        Crea un nuovo ordine con routing dinamico.

        destinazione: "LASER" o "OFFICINA" — dove l'impiegata manda l'ordine.
        Se OFFICINA, auto-assegna operatore da operator_clients.
        numero_ordine: obbligatorio — riferimento univoco inserito dall'impiegata.
        """
        session = get_session()

        try:
            # Auto-assegna operatore se destinazione è OFFICINA
            operatore_assegnato = None
            if destinazione == "OFFICINA":
                # Cerca operatore assegnato a questo cliente (case-insensitive)
                assignments = session.query(OperatorClient).filter(
                    func.lower(OperatorClient.client_name) == func.lower(cliente)
                ).all()
                # Preferisci operatore non-LASER
                for assignment in assignments:
                    op_user = session.query(User).filter(User.id == assignment.operator_id).first()
                    if op_user and op_user.phase != 'LASER':
                        operatore_assegnato = assignment.operator_id
                        break
                # Fallback: primo mapping disponibile
                if not operatore_assegnato and assignments:
                    operatore_assegnato = assignments[0].operator_id
                # Fallback finale: assegna a un capo per non perdere l'ordine
                if not operatore_assegnato:
                    capo = session.query(User).filter(User.is_capo == True).first()
                    if capo:
                        operatore_assegnato = capo.id
                        logger.warning(f"Ordine {numero_ordine} ({cliente}): nessun operatore mappato per OFFICINA, assegnato al capo {capo.name}")

            # Determina fase_corrente
            fase_corrente = "LASER" if destinazione == "LASER" else "PIEGA"

            order = Order(
                id=str(uuid.uuid4()),
                cliente=cliente,
                numero_ordine=numero_ordine,
                data_consegna=datetime.fromisoformat(data_consegna),
                fase_corrente=fase_corrente,
                operatore_assegnato=operatore_assegnato,
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
        """Recupera ordini non eliminati, opzionalmente filtrati per cliente"""
        session = get_session()
        try:
            query = session.query(Order).filter(Order.is_deleted == False)
            if cliente:
                query = query.filter(Order.cliente == cliente)
            return query.all()
        finally:
            session.close()
    
    @staticmethod
    def get_all_orders_dict(cliente: str = None, status: str = None,
                            fase_corrente: str = None, operatore: str = None,
                            order_ids: list = None) -> list:
        """Recupera ordini non eliminati come dizionari con filtri per il nuovo workflow"""
        session = get_session()
        try:
            query = session.query(Order).filter(Order.is_deleted == False)
            if order_ids:
                query = query.filter(Order.id.in_(order_ids))
            if cliente:
                query = query.filter(Order.cliente == cliente)
            if status:
                query = query.filter(Order.status == status)
            if fase_corrente:
                query = query.filter(Order.fase_corrente == fase_corrente)
            if operatore:
                query = query.filter(Order.operatore_assegnato == operatore)

            orders = query.options(
                joinedload(Order.files),
                joinedload(Order.processing_steps)
            ).order_by(Order.data_consegna.asc()).all()

            # De-duplica ordini (joinedload può duplicare)
            seen_ids = set()
            unique_orders = []
            for o in orders:
                if o.id not in seen_ids:
                    seen_ids.add(o.id)
                    unique_orders.append(o)
            orders = unique_orders

            # Pre-carica tutte le sessioni per gli ordini trovati
            order_ids = [o.id for o in orders]
            all_sessions = session.query(PhaseSession).filter(
                PhaseSession.order_id.in_(order_ids)
            ).all() if order_ids else []
            step_sessions = {}
            for ps in all_sessions:
                step_sessions.setdefault(ps.step_id, []).append(ps)

            # Pre-carica tutti gli utenti (evita N+1 queries)
            all_users = session.query(User).all()
            name_to_id = {u.name: u.id for u in all_users}
            id_to_name = {u.id: u.name for u in all_users}

            # Pre-carica tutte le support requests attive
            all_support = session.query(SupportRequest).filter(
                SupportRequest.order_id.in_(order_ids),
                SupportRequest.stato.in_(['pending', 'accepted'])
            ).all() if order_ids else []
            support_by_order = {}
            for sr in all_support:
                support_by_order.setdefault(sr.order_id, []).append(sr)

            result = []
            for order in orders:
                pdf_file = None
                dxf_files = []
                if order.files:
                    for f in order.files:
                        if f.file_type == 'PDF':
                            pdf_file = f.filename
                        elif f.file_type == 'DXF':
                            dxf_files.append({'filename': f.filename})

                operatore_nome = id_to_name.get(order.operatore_assegnato)

                steps_data = []
                for ps in (order.processing_steps or []):
                    ss = step_sessions.get(ps.id, [])
                    closed = [x for x in ss if x.timestamp_fine]
                    cumul = sum(int((x.timestamp_fine - x.timestamp_inizio).total_seconds()) for x in closed)
                    active_list = [x for x in ss if x.timestamp_fine is None]
                    active = active_list[0] if active_list else None

                    # Info per-operatore: tempo e stato indipendenti (chiave = user ID)
                    op_groups = {}
                    for x in ss:
                        op = x.operatore or 'unknown'
                        op_groups.setdefault(op, []).append(x)
                    operatori_info = {}
                    for op_name, op_ss in op_groups.items():
                        op_closed = [x for x in op_ss if x.timestamp_fine]
                        op_active = [x for x in op_ss if x.timestamp_fine is None]
                        op_cumul = sum(int((x.timestamp_fine - x.timestamp_inizio).total_seconds()) for x in op_closed)
                        op_key = name_to_id.get(op_name, op_name)  # Usa ID utente come chiave
                        op_confermato = any(x.tipo_chiusura == 'totale' for x in op_ss)
                        operatori_info[op_key] = {
                            'sessione_attiva': len(op_active) > 0,
                            'sessione_attiva_inizio': op_active[0].timestamp_inizio.isoformat() if op_active else None,
                            'in_pausa': len(op_active) == 0 and len(op_closed) > 0,
                            'confermato': op_confermato,
                            'tempo_cumulativo_secondi': op_cumul,
                            'sessioni_count': len(op_ss)
                        }

                    steps_data.append({
                        'id': ps.id,
                        'fase': ps.fase,
                        'timestamp_inizio': ps.timestamp_inizio.isoformat() if ps.timestamp_inizio else None,
                        'timestamp_fine': ps.timestamp_fine.isoformat() if ps.timestamp_fine else None,
                        'operatore': ps.operatore,
                        'fase_successiva': ps.fase_successiva,
                        'completamento_parziale': ps.completamento_parziale,
                        'note': ps.note,
                        'sessione_attiva': len(active_list) > 0,
                        'sessione_attiva_inizio': active.timestamp_inizio.isoformat() if active else None,
                        'sessioni_count': len(ss),
                        'tempo_cumulativo_secondi': cumul,
                        'in_pausa': (ps.timestamp_fine is None and len(ss) > 0 and len(active_list) == 0),
                        'sessioni_attive': [{'operatore': a.operatore, 'inizio': a.timestamp_inizio.isoformat()} for a in active_list],
                        'operatori_info': operatori_info,
                    })

                # Support requests attivi per quest'ordine (pre-caricati)
                support_data = []
                for sr in support_by_order.get(order.id, []):
                    support_data.append({
                        'id': sr.id,
                        'operatore_principale': sr.operatore_principale,
                        'nome_principale': id_to_name.get(sr.operatore_principale, ''),
                        'operatore_supporto': sr.operatore_supporto,
                        'nome_supporto': id_to_name.get(sr.operatore_supporto, ''),
                        'stato': sr.stato,
                        'forzata': sr.forzata
                    })

                # Info lotti figli (pre-caricati)
                lotti_data = []
                lotti_count = 0
                all_lotti_completed = False
                if order.lotto_numero and order.lotto_numero > 0:
                    child_lotti = session.query(Order).filter(
                        Order.parent_order_id == order.id,
                        Order.is_deleted == False
                    ).order_by(Order.lotto_numero.asc()).all()
                    for l in child_lotti:
                        lotti_data.append({
                            'id': l.id,
                            'lotto_numero': l.lotto_numero,
                            'lotto_nome': l.lotto_nome or '',
                            'fase_corrente': l.fase_corrente,
                            'status': l.status
                        })
                    lotti_count = len(child_lotti) + 1
                    all_phases = [l.fase_corrente for l in child_lotti] + [order.fase_corrente]
                    all_lotti_completed = all(f == 'COMPLETATO' for f in all_phases)

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
                    'processing_steps': steps_data,
                    'support_requests': support_data,
                    'parent_order_id': order.parent_order_id,
                    'lotto_numero': order.lotto_numero or 0,
                    'lotto_nome': order.lotto_nome or '',
                    'lotti': lotti_data,
                    'lotti_count': lotti_count,
                    'all_lotti_completed': all_lotti_completed
                })

            return result
        finally:
            session.close()

    @staticmethod
    def get_orders_by_ids(order_ids: list) -> list:
        """Recupera ordini specifici per ID come dizionari"""
        if not order_ids:
            return []
        return OrderManager.get_all_orders_dict(order_ids=order_ids)

    @staticmethod
    def get_orders_by_phase(phase: str, operatore_id: str = None) -> list:
        """Recupera ordini per fase corrente (e opzionalmente per operatore)"""
        session = get_session()
        try:
            query = session.query(Order).filter(Order.fase_corrente == phase, Order.is_deleted == False)
            if operatore_id:
                query = query.filter(Order.operatore_assegnato == operatore_id)
            return query.order_by(Order.data_consegna.asc()).all()
        finally:
            session.close()

    @staticmethod
    def update_delivery_date(order_id: str, new_date: datetime) -> dict:
        """Aggiorna la data di consegna di un ordine (riprogrammazione calendario)"""
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {'success': False, 'error': 'Ordine non trovato'}
            old_date = order.data_consegna
            order.data_consegna = new_date
            session.commit()
            return {
                'success': True,
                'order_id': order_id,
                'data_consegna': order.data_consegna.isoformat(),
                'old_date': old_date.isoformat() if old_date else None
            }
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def update_order(order_id: str, updates: dict) -> dict:
        """Aggiorna i dati modificabili di un ordine: cliente, note, data_consegna, numero_ordine."""
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {'success': False, 'error': 'Ordine non trovato'}

            allowed = ['cliente', 'note', 'data_consegna', 'numero_ordine']
            for field in allowed:
                if field in updates and updates[field] is not None:
                    if field == 'data_consegna':
                        try:
                            val = datetime.strptime(str(updates[field])[:10], '%Y-%m-%d')
                            setattr(order, field, val)
                        except ValueError:
                            pass
                    else:
                        setattr(order, field, updates[field])

            session.commit()
            return {'success': True, 'order_id': order_id}
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def start_phase(order_id: str, phase: str, operatore: str = "") -> bool:
        """Inizia una fase di lavorazione — crea/riprende ProcessingStep + crea PhaseSession"""
        session = get_session()
        try:
            now = datetime.utcnow()

            # Verifica che la fase richiesta corrisponda alla fase corrente dell'ordine
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return False
            if order.fase_corrente != phase:
                raise ValueError(f"Fase '{phase}' non corrisponde alla fase corrente '{order.fase_corrente}' dell'ordine")

            # Cerca ProcessingStep aperto per questa fase (potrebbe essere in pausa)
            existing_step = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.fase == phase,
                ProcessingStep.timestamp_fine.is_(None)
            ).order_by(ProcessingStep.timestamp_inizio.desc()).first()

            if existing_step:
                # Controlla se QUESTO operatore ha già una sessione attiva
                my_active = session.query(PhaseSession).filter(
                    PhaseSession.step_id == existing_step.id,
                    PhaseSession.operatore == operatore,
                    PhaseSession.timestamp_fine.is_(None)
                ).first()
                if my_active:
                    return True  # Sessione già attiva per questo operatore
                # Se un altro operatore ha una sessione attiva, permetti sessione parallela
                step = existing_step
            else:
                # Crea nuovo ProcessingStep
                step = ProcessingStep(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    fase=phase,
                    timestamp_inizio=now,
                    operatore=operatore
                )
                session.add(step)
                session.flush()

            # Crea nuova PhaseSession
            new_sess = PhaseSession(
                id=str(uuid.uuid4()),
                step_id=step.id,
                order_id=order_id,
                fase=phase,
                operatore=operatore,
                timestamp_inizio=now
            )
            session.add(new_sess)

            # Aggiorna stato dell'ordine (order già caricato all'inizio)
            order.fase_corrente = phase
            if order.status in ("RICEVUTO", "PARZIALE"):
                order.status = "IN_LAVORAZIONE"

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
        Se completamento_parziale=True → salva parziale (chiude sessione, non lo step).
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

            now = datetime.utcnow()

            # Trova la sessione attiva di QUESTO operatore (per supporto parallelo)
            active_sess = None
            if operatore:
                active_sess = session.query(PhaseSession).filter(
                    PhaseSession.step_id == processing_step.id,
                    PhaseSession.operatore == operatore,
                    PhaseSession.timestamp_fine.is_(None)
                ).first()
            if not active_sess:
                # Fallback: qualsiasi sessione attiva
                active_sess = session.query(PhaseSession).filter(
                    PhaseSession.step_id == processing_step.id,
                    PhaseSession.timestamp_fine.is_(None)
                ).first()

            # --- BACKWARD COMPAT: completamento_parziale → save_partial ---
            if completamento_parziale:
                if active_sess:
                    active_sess.timestamp_fine = now
                    active_sess.tipo_chiusura = 'parziale'
                    if note:
                        active_sess.note = note
                # NON chiudere il ProcessingStep, NON cambiare fase_corrente
                session.commit()
                all_sess = session.query(PhaseSession).filter(
                    PhaseSession.step_id == processing_step.id,
                    PhaseSession.timestamp_fine.isnot(None)
                ).all()
                tempo_sec = sum(
                    int((s.timestamp_fine - s.timestamp_inizio).total_seconds())
                    for s in all_sess
                )
                return {
                    "success": True,
                    "order_id": order_id,
                    "phase": phase,
                    "completamento_parziale": True,
                    "sessioni_count": len(all_sess),
                    "tempo_cumulativo_secondi": tempo_sec,
                    "paused": True
                }

            # --- VERIFICA MULTI-OPERATORE ---
            # Conta operatori distinti su questo step
            distinct_ops = set(
                s[0] for s in session.query(PhaseSession.operatore).filter(
                    PhaseSession.step_id == processing_step.id,
                    PhaseSession.operatore.isnot(None)
                ).distinct().all()
            )

            if len(distinct_ops) > 1 and operatore:
                # Multi-operatore: conferma individuale
                # Chiudi solo la sessione di QUESTO operatore
                my_active = session.query(PhaseSession).filter(
                    PhaseSession.step_id == processing_step.id,
                    PhaseSession.operatore == operatore,
                    PhaseSession.timestamp_fine.is_(None)
                ).first()
                if my_active:
                    my_active.timestamp_fine = now
                    my_active.tipo_chiusura = 'totale'
                    if note:
                        my_active.note = note
                else:
                    # Operatore in pausa: segna ultima sessione come confermata
                    last_sess = session.query(PhaseSession).filter(
                        PhaseSession.step_id == processing_step.id,
                        PhaseSession.operatore == operatore
                    ).order_by(PhaseSession.timestamp_fine.desc()).first()
                    if last_sess:
                        last_sess.tipo_chiusura = 'totale'

                session.flush()

                # Verifica se TUTTI gli operatori hanno confermato
                all_confirmed = True
                pending_names = []
                for op_name in distinct_ops:
                    has_confirm = session.query(PhaseSession).filter(
                        PhaseSession.step_id == processing_step.id,
                        PhaseSession.operatore == op_name,
                        PhaseSession.tipo_chiusura == 'totale'
                    ).first()
                    if not has_confirm:
                        all_confirmed = False
                        pending_names.append(op_name)

                if not all_confirmed:
                    session.commit()
                    return {
                        "success": True,
                        "order_id": order_id,
                        "phase": phase,
                        "waiting_for_others": True,
                        "pending_operators": pending_names
                    }

                # Tutti hanno confermato → chiudi sessioni rimaste e prosegui
                remaining = session.query(PhaseSession).filter(
                    PhaseSession.step_id == processing_step.id,
                    PhaseSession.timestamp_fine.is_(None)
                ).all()
                for s in remaining:
                    s.timestamp_fine = now
                    s.tipo_chiusura = 'totale'
            else:
                # Singolo operatore: chiudi tutte le sessioni come prima
                all_active_sessions = session.query(PhaseSession).filter(
                    PhaseSession.step_id == processing_step.id,
                    PhaseSession.timestamp_fine.is_(None)
                ).all()
                for sess in all_active_sessions:
                    sess.timestamp_fine = now
                    sess.tipo_chiusura = 'totale'
                    if note and sess == active_sess:
                        sess.note = note

            # Completa lo step
            processing_step.timestamp_fine = now
            processing_step.note = note
            processing_step.fase_successiva = fase_successiva
            processing_step.completamento_parziale = False
            if operatore and not processing_step.operatore:
                processing_step.operatore = operatore

            # Aggiorna l'ordine
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Ordine non trovato"}

            # Auto-routing
            if not fase_successiva:
                phase_flow = {
                    'LASER': 'PIEGA',
                    'PIEGA': 'SALDATURA',
                    'SALDATURA': 'PULIZIA',
                    'PULIZIA': 'COMPLETATO'
                }
                fase_successiva = phase_flow.get(phase, 'COMPLETATO')
                processing_step.fase_successiva = fase_successiva

            if fase_successiva == "COMPLETATO":
                order.fase_corrente = "COMPLETATO"
                order.status = "COMPLETATO"
                total_time = OrderManager._calculate_order_total_time(order_id, session)
                notification = OrderNotification(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    tempi_totali=total_time
                )
                session.add(notification)
            elif fase_successiva == "LASER":
                order.fase_corrente = "LASER"
                order.status = "IN_LAVORAZIONE"
            elif fase_successiva:
                order.fase_corrente = fase_successiva
                order.status = "IN_LAVORAZIONE"

            # Auto-assegna operatore quando ordine esce dal laser e non ha operatore
            if phase == 'LASER' and fase_successiva not in ('LASER', 'COMPLETATO') and not order.operatore_assegnato:
                # Cerca mapping cliente→operatore, ma solo operatori officina (non LASER)
                assignments = session.query(OperatorClient).filter(
                    func.lower(OperatorClient.client_name) == func.lower(order.cliente)
                ).all()
                assigned = False
                for assignment in assignments:
                    op_user = session.query(User).filter(User.id == assignment.operator_id).first()
                    if op_user and op_user.phase != 'LASER':
                        order.operatore_assegnato = assignment.operator_id
                        assigned = True
                        break
                # Fallback: assegna a un capo se nessun mapping trovato
                if not assigned:
                    capo = session.query(User).filter(User.is_capo == True).first()
                    if capo:
                        order.operatore_assegnato = capo.id
                        logger.warning(f"Ordine {order.numero_ordine} ({order.cliente}): nessun operatore mappato, assegnato al capo {capo.name}")

            session.commit()

            # Calcola tempi per-operatore per il riepilogo
            all_step_sessions = session.query(PhaseSession).filter(
                PhaseSession.step_id == processing_step.id
            ).all()
            all_users_db = session.query(User).all()
            n2id = {u.name: u.id for u in all_users_db}
            id2name = {u.id: u.name for u in all_users_db}
            op_tempi = {}
            for s in all_step_sessions:
                if s.timestamp_fine and s.timestamp_inizio:
                    op = s.operatore or 'unknown'
                    op_id = n2id.get(op, op)
                    op_tempi.setdefault(op_id, 0)
                    op_tempi[op_id] += int((s.timestamp_fine - s.timestamp_inizio).total_seconds())

            operatori_tempi = []
            for op_id, sec in op_tempi.items():
                operatori_tempi.append({
                    'operatore_id': op_id,
                    'nome': id2name.get(op_id, op_id),
                    'secondi': sec
                })

            return {
                "success": True,
                "order_id": order_id,
                "phase": phase,
                "fase_successiva": fase_successiva,
                "completamento_parziale": False,
                "all_completed": fase_successiva == "COMPLETATO",
                "operatori_tempi": operatori_tempi
            }

        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def save_partial(order_id: str, phase: str, note: str = "", operatore: str = "") -> dict:
        """Salva parziale: chiude sessione corrente, NON chiude il ProcessingStep."""
        session = get_session()
        try:
            processing_step = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.fase == phase,
                ProcessingStep.timestamp_fine.is_(None)
            ).order_by(ProcessingStep.timestamp_inizio.desc()).first()

            if not processing_step:
                return {"success": False, "error": "Nessuna fase attiva trovata"}

            # Cerca sessione attiva di QUESTO operatore (supporto parallelo)
            active_sess = None
            if operatore:
                active_sess = session.query(PhaseSession).filter(
                    PhaseSession.step_id == processing_step.id,
                    PhaseSession.operatore == operatore,
                    PhaseSession.timestamp_fine.is_(None)
                ).first()
            if not active_sess:
                # Fallback: qualsiasi sessione attiva
                active_sess = session.query(PhaseSession).filter(
                    PhaseSession.step_id == processing_step.id,
                    PhaseSession.timestamp_fine.is_(None)
                ).first()

            if not active_sess:
                return {"success": False, "error": "Nessuna sessione attiva trovata"}

            now = datetime.utcnow()
            active_sess.timestamp_fine = now
            active_sess.tipo_chiusura = 'parziale'
            if note:
                active_sess.note = note
            if operatore and not active_sess.operatore:
                active_sess.operatore = operatore

            # Calcola tempo cumulativo
            all_sess = session.query(PhaseSession).filter(
                PhaseSession.step_id == processing_step.id,
                PhaseSession.timestamp_fine.isnot(None)
            ).all()
            tempo_sec = sum(
                int((s.timestamp_fine - s.timestamp_inizio).total_seconds())
                for s in all_sess
            )

            session.commit()
            return {
                "success": True,
                "order_id": order_id,
                "phase": phase,
                "sessioni_count": len(all_sess),
                "tempo_cumulativo_secondi": tempo_sec,
                "tempo_cumulativo": OrderManager._format_duration(timedelta(seconds=tempo_sec))
            }
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()
    
    @staticmethod
    def split_order(order_id: str, operatore_id: str, lotto_nome: str = None) -> dict:
        """
        Divide un ordine in lotti: il padre resta nella fase corrente (L1),
        viene creato un figlio (L2+) che avanza alla fase successiva.
        """
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Ordine non trovato"}

            if order.fase_corrente in ("COMPLETATO", "PARZIALE"):
                return {"success": False, "error": "Non puoi dividere un ordine completato"}

            # Verifica permessi: operatore assegnato al cliente o capo
            user = session.query(User).filter(User.id == operatore_id).first()
            if not user:
                return {"success": False, "error": "Utente non trovato"}
            if not user.is_capo:
                is_assigned = session.query(OperatorClient).filter(
                    func.lower(OperatorClient.client_name) == func.lower(order.cliente),
                    OperatorClient.operator_id == operatore_id
                ).first()
                if not is_assigned:
                    return {"success": False, "error": "Non hai i permessi per dividere questo ordine"}

            # Determina il padre reale (se si splitta un lotto, il padre è il root)
            root_id = order.parent_order_id if order.parent_order_id else order.id

            # Se il padre non è ancora un lotto, diventa L1
            root_order = session.query(Order).filter(Order.id == root_id).first()
            if root_order and root_order.lotto_numero == 0:
                root_order.lotto_numero = 1

            # Se anche l'ordine corrente non è ancora un lotto (primo split), diventa L1
            if order.lotto_numero == 0:
                order.lotto_numero = 1

            # Calcola prossimo numero lotto
            max_lotto = session.query(func.max(Order.lotto_numero)).filter(
                ((Order.id == root_id) | (Order.parent_order_id == root_id))
            ).scalar() or 1
            nuovo_lotto_num = max_lotto + 1

            # Fase successiva per il nuovo lotto
            phase_flow = {
                'LASER': 'PIEGA',
                'PIEGA': 'SALDATURA',
                'SALDATURA': 'PULIZIA',
                'PULIZIA': 'COMPLETATO'
            }
            fase_succ = phase_flow.get(order.fase_corrente, 'COMPLETATO')
            if fase_succ == 'COMPLETATO':
                return {"success": False, "error": "Non puoi dividere un ordine nell'ultima fase"}

            # Copia i file PDF dell'ordine originale
            original_files = session.query(OrderFile).filter(
                OrderFile.order_id == order.id,
                OrderFile.file_type == 'PDF'
            ).all()

            # Auto-assign operatore per il nuovo lotto (se esce da LASER)
            new_operatore = order.operatore_assegnato
            if order.fase_corrente == 'LASER' and not new_operatore:
                assignments = session.query(OperatorClient).filter(
                    func.lower(OperatorClient.client_name) == func.lower(order.cliente)
                ).all()
                for assignment in assignments:
                    op_user = session.query(User).filter(User.id == assignment.operator_id).first()
                    if op_user and op_user.phase != 'LASER':
                        new_operatore = assignment.operator_id
                        break
                if not new_operatore:
                    capo = session.query(User).filter(User.is_capo == True).first()
                    if capo:
                        new_operatore = capo.id

            # Crea il nuovo lotto
            new_order = Order(
                id=str(uuid.uuid4()),
                cliente=order.cliente,
                numero_ordine=order.numero_ordine,
                data_ricezione=order.data_ricezione,
                data_consegna=order.data_consegna,
                status="RICEVUTO",
                fase_corrente=fase_succ,
                operatore_assegnato=new_operatore,
                prezzo_quotato=None,  # Il prezzo resta solo sul padre
                note=f"Lotto {nuovo_lotto_num} — creato da split",
                parent_order_id=root_id,
                lotto_numero=nuovo_lotto_num,
                lotto_nome=lotto_nome or None
            )
            session.add(new_order)

            # Copia riferimenti file PDF al nuovo lotto
            for f in original_files:
                new_file = OrderFile(
                    id=str(uuid.uuid4()),
                    order_id=new_order.id,
                    filename=f.filename,
                    filepath=f.filepath,
                    file_type=f.file_type
                )
                session.add(new_file)

            session.commit()

            return {
                "success": True,
                "parent_order_id": root_id,
                "new_lotto_id": new_order.id,
                "new_lotto_numero": nuovo_lotto_num,
                "new_lotto_nome": new_order.lotto_nome or f"Lotto {nuovo_lotto_num}",
                "fase_corrente_padre": order.fase_corrente,
                "fase_corrente_lotto": fase_succ
            }

        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def confirm_lotti_completion(order_id: str, operatore_id: str) -> dict:
        """
        Conferma manuale completamento ordine quando tutti i lotti sono COMPLETATO.
        Solo l'operatore assegnato al cliente o un capo può confermare.
        """
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Ordine non trovato"}

            # Verifica permessi
            user = session.query(User).filter(User.id == operatore_id).first()
            if not user:
                return {"success": False, "error": "Utente non trovato"}
            if not user.is_capo:
                is_assigned = session.query(OperatorClient).filter(
                    func.lower(OperatorClient.client_name) == func.lower(order.cliente),
                    OperatorClient.operator_id == operatore_id
                ).first()
                if not is_assigned:
                    return {"success": False, "error": "Non hai i permessi"}

            # Verifica che il padre (L1) sia COMPLETATO
            if order.fase_corrente != "COMPLETATO":
                return {"success": False, "error": "L'ordine padre non è ancora completato"}

            # Verifica che TUTTI i lotti figli siano COMPLETATO
            lotti = session.query(Order).filter(
                Order.parent_order_id == order_id
            ).all()
            non_completati = [l for l in lotti if l.fase_corrente != "COMPLETATO"]
            if non_completati:
                nomi = [f"L{l.lotto_numero}" for l in non_completati]
                return {"success": False, "error": f"Lotti non completati: {', '.join(nomi)}"}

            # Calcola tempo totale (padre + tutti i lotti)
            all_order_ids = [order_id] + [l.id for l in lotti]
            total_seconds = 0
            for oid in all_order_ids:
                steps = session.query(ProcessingStep).filter(
                    ProcessingStep.order_id == oid,
                    ProcessingStep.timestamp_inizio.isnot(None),
                    ProcessingStep.timestamp_fine.isnot(None)
                ).all()
                for step in steps:
                    total_seconds += int((step.timestamp_fine - step.timestamp_inizio).total_seconds())

            total_time = OrderManager._format_duration(timedelta(seconds=total_seconds))

            # Crea notifica di completamento
            notification = OrderNotification(
                id=str(uuid.uuid4()),
                order_id=order_id,
                tempi_totali=total_time
            )
            session.add(notification)

            # Marca ordine come completato definitivamente (status speciale)
            order.status = "COMPLETATO"
            session.commit()

            return {"success": True, "tempi_totali": total_time}

        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def complete_order(order_id: str, current_phase: str, note: str = "", operatore: str = "") -> dict:
        """
        Completa un ordine anticipatamente dalla fase corrente.
        Chiude step/sessione attivi, marca ordine COMPLETATO,
        le fasi senza ProcessingStep sono 'non necessarie' per assenza.
        """
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Ordine non trovato"}

            if order.status == "COMPLETATO":
                return {"success": False, "error": "Ordine già completato"}

            now = datetime.utcnow()

            # Chiudi eventuali step aperti (potrebbe essere la fase corrente)
            open_steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.timestamp_fine.is_(None)
            ).all()

            for step in open_steps:
                # Chiudi TUTTE le sessioni attive (anche parallele da supporto)
                active_sessions = session.query(PhaseSession).filter(
                    PhaseSession.step_id == step.id,
                    PhaseSession.timestamp_fine.is_(None)
                ).all()
                for active_sess in active_sessions:
                    active_sess.timestamp_fine = now
                    active_sess.tipo_chiusura = 'totale'

                step.timestamp_fine = now
                step.fase_successiva = 'COMPLETATO'
                step.completamento_parziale = False
                if operatore and not step.operatore:
                    step.operatore = operatore
                if note:
                    step.note = note

            # Marca ordine come completato
            order.fase_corrente = "COMPLETATO"
            order.status = "COMPLETATO"

            # Crea OrderNotification con tempo totale
            total_time = OrderManager._calculate_order_total_time(order_id, session)
            notification = OrderNotification(
                id=str(uuid.uuid4()),
                order_id=order_id,
                tempi_totali=total_time
            )
            session.add(notification)

            # Riepilogo fasi
            all_phases = ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA']
            all_steps = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == order_id,
                ProcessingStep.timestamp_fine.isnot(None)
            ).all()

            executed_set = set(s.fase for s in all_steps)
            fasi_eseguite = []
            for s in all_steps:
                dur = int((s.timestamp_fine - s.timestamp_inizio).total_seconds()) if s.timestamp_inizio and s.timestamp_fine else 0
                fasi_eseguite.append({
                    'fase': s.fase,
                    'operatore': s.operatore or '',
                    'durata_secondi': dur
                })

            fasi_non_necessarie = [p for p in all_phases if p not in executed_set]

            session.commit()
            return {
                "success": True,
                "all_completed": True,
                "order_id": order_id,
                "fasi_eseguite": fasi_eseguite,
                "fasi_non_necessarie": fasi_non_necessarie
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

            # Carica tutte le sessioni per questo ordine
            all_sessions = session.query(PhaseSession).filter(
                PhaseSession.order_id == order_id
            ).order_by(PhaseSession.timestamp_inizio.asc()).all()
            step_sessions = {}
            for ps in all_sessions:
                step_sessions.setdefault(ps.step_id, []).append(ps)

            # Mapping nome→ID utente per operatori_info
            all_users_detail = session.query(User).all()
            name_to_id = {u.name: u.id for u in all_users_detail}

            pdf_file = None
            dxf_files = []
            if order.files:
                for f in order.files:
                    if f.file_type == 'PDF':
                        pdf_file = f.filename
                    elif f.file_type == 'DXF':
                        dxf_files.append({'filename': f.filename})

            # Recupera nome operatore assegnato
            operatore_nome = None
            if order.operatore_assegnato:
                user = session.query(User).filter(User.id == order.operatore_assegnato).first()
                if user:
                    operatore_nome = user.name

            def _step_session_data(s):
                ss = step_sessions.get(s.id, [])
                closed = [x for x in ss if x.timestamp_fine]
                cumul = sum(int((x.timestamp_fine - x.timestamp_inizio).total_seconds()) for x in closed)
                active_list = [x for x in ss if x.timestamp_fine is None]
                active = active_list[0] if active_list else None

                # Info per-operatore: tempo e stato indipendenti (chiave = user ID)
                op_groups = {}
                for x in ss:
                    op = x.operatore or 'unknown'
                    op_groups.setdefault(op, []).append(x)
                operatori_info = {}
                for op_name, op_ss in op_groups.items():
                    op_closed = [x for x in op_ss if x.timestamp_fine]
                    op_active = [x for x in op_ss if x.timestamp_fine is None]
                    op_cumul = sum(int((x.timestamp_fine - x.timestamp_inizio).total_seconds()) for x in op_closed)
                    op_key = name_to_id.get(op_name, op_name)
                    op_confermato2 = any(x.tipo_chiusura == 'totale' for x in op_ss)
                    operatori_info[op_key] = {
                        'sessione_attiva': len(op_active) > 0,
                        'sessione_attiva_inizio': (op_active[0].timestamp_inizio.isoformat() + 'Z') if op_active else None,
                        'in_pausa': len(op_active) == 0 and len(op_closed) > 0,
                        'confermato': op_confermato2,
                        'tempo_cumulativo_secondi': op_cumul,
                        'sessioni_count': len(op_ss)
                    }

                return {
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
                    ) if s.timestamp_inizio and s.timestamp_fine else None,
                    "sessione_attiva": len(active_list) > 0,
                    "sessione_attiva_inizio": active.timestamp_inizio.isoformat() + 'Z' if active else None,
                    "sessioni_count": len(ss),
                    "tempo_cumulativo_secondi": cumul,
                    "in_pausa": (s.timestamp_fine is None and len(ss) > 0 and len(active_list) == 0),
                    "sessioni_attive": [{'operatore': a.operatore, 'inizio': a.timestamp_inizio.isoformat() + 'Z'} for a in active_list],
                    "operatori_info": operatori_info,
                    "sessioni": [
                        {
                            "id": x.id,
                            "timestamp_inizio": x.timestamp_inizio.isoformat() + 'Z',
                            "timestamp_fine": x.timestamp_fine.isoformat() + 'Z' if x.timestamp_fine else None,
                            "tipo_chiusura": x.tipo_chiusura,
                            "operatore": x.operatore,
                            "note": x.note,
                            "durata": OrderManager._format_duration(
                                x.timestamp_fine - x.timestamp_inizio
                            ) if x.timestamp_fine else None,
                            "durata_secondi": int((x.timestamp_fine - x.timestamp_inizio).total_seconds()) if x.timestamp_fine else None
                        }
                        for x in ss
                    ]
                }

            # Support requests attivi
            active_support = session.query(SupportRequest).filter(
                SupportRequest.order_id == order.id,
                SupportRequest.stato.in_(['pending', 'accepted'])
            ).all()
            support_data = []
            for sr in active_support:
                sr_principale = session.query(User).filter(User.id == sr.operatore_principale).first()
                sr_supporto = session.query(User).filter(User.id == sr.operatore_supporto).first()
                support_data.append({
                    'id': sr.id,
                    'operatore_principale': sr.operatore_principale,
                    'nome_principale': sr_principale.name if sr_principale else '',
                    'operatore_supporto': sr.operatore_supporto,
                    'nome_supporto': sr_supporto.name if sr_supporto else '',
                    'stato': sr.stato,
                    'forzata': sr.forzata
                })

            # Info lotti
            lotti_data = []
            lotti_count = 0
            all_lotti_completed = False
            root_id = order.parent_order_id or order.id
            if order.lotto_numero > 0 or order.parent_order_id:
                # Questo ordine fa parte di un sistema di lotti
                lotti_query = session.query(Order).filter(
                    ((Order.id == root_id) | (Order.parent_order_id == root_id)),
                    Order.id != order.id
                ).order_by(Order.lotto_numero.asc()).all()
                for l in lotti_query:
                    lotti_data.append({
                        'id': l.id,
                        'lotto_numero': l.lotto_numero,
                        'lotto_nome': l.lotto_nome or '',
                        'fase_corrente': l.fase_corrente,
                        'status': l.status
                    })
                lotti_count = len(lotti_query) + 1  # +1 per l'ordine corrente
                # Controlla se tutti i lotti (compreso questo) sono completati
                all_phases = [l.fase_corrente for l in lotti_query] + [order.fase_corrente]
                all_lotti_completed = all(f == 'COMPLETATO' for f in all_phases)

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
                "processing_steps": [_step_session_data(s) for s in processing_steps],
                "support_requests": support_data,
                "parent_order_id": order.parent_order_id,
                "lotto_numero": order.lotto_numero,
                "lotto_nome": order.lotto_nome or '',
                "lotti": lotti_data,
                "lotti_count": lotti_count,
                "all_lotti_completed": all_lotti_completed
            }
        finally:
            session.close()


class UserManager:
    """Gestore operazioni su utenti"""

    @staticmethod
    def _serialize_user(user) -> dict:
        """Serializza un utente in dict"""
        # Recupera clienti assegnati da operator_clients
        session = get_session()
        try:
            assigned = session.query(OperatorClient.client_name).filter(
                OperatorClient.operator_id == user.id
            ).all()
            assigned_clients = [a.client_name for a in assigned]
        except Exception:
            assigned_clients = []
        finally:
            session.close()

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
            'assigned_clients': assigned_clients,
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
    def get_all_users(include_inactive: bool = False) -> list[dict]:
        """Recupera tutti gli utenti (attivi, o tutti se include_inactive=True)"""
        session = get_session()
        try:
            query = session.query(User)
            if not include_inactive:
                query = query.filter(User.is_active == True)
            users = query.all()
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
        Calcola KPI reali per ogni operaio:
        - ordini completati (count distinct order_id)
        - tempo medio per ordine (da PhaseSession o fallback ProcessingStep)
        - puntualita: % ordini completati entro data_consegna
        - ritardi: ordini attivi scaduti assegnati all'operatore
        - saturazione: ore lavorate oggi / 8h turno
        """
        session = get_session()
        try:
            from sqlalchemy import func, and_
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            TURNO_ORE = 8

            # Pre-carica dati per evitare N+1
            all_orders = {o.id: o for o in session.query(Order).all()}
            all_steps = session.query(ProcessingStep).all()
            steps_by_order = {}
            for s in all_steps:
                steps_by_order.setdefault(s.order_id, []).append(s)
            steps_by_operator = {}
            for s in all_steps:
                if s.operatore:
                    steps_by_operator.setdefault(s.operatore, []).append(s)

            # Sessioni chiuse per tempo reale
            all_closed_sessions = session.query(PhaseSession).filter(
                PhaseSession.timestamp_fine != None
            ).all()
            sessions_by_step = {}
            for ps in all_closed_sessions:
                sessions_by_step.setdefault(ps.step_id, []).append(ps)
            sessions_by_operator = {}
            for ps in all_closed_sessions:
                op_name = ps.operatore or 'unknown'
                sessions_by_operator.setdefault(op_name, []).append(ps)

            users = session.query(User).filter(User.is_active == True).all()

            kpi_list = []
            for user in users:
                name = user.name
                op_steps = steps_by_operator.get(name, [])
                completed_steps = [s for s in op_steps if s.timestamp_fine]

                # Ordini unici completati
                ordini_completati = len(set(s.order_id for s in completed_steps))

                # Tempo medio reale per step (da sessioni)
                step_durations = []
                for s in completed_steps:
                    step_ss = sessions_by_step.get(s.id, [])
                    op_ss = [x for x in step_ss if x.operatore == name]
                    if op_ss:
                        secs = sum((x.timestamp_fine - x.timestamp_inizio).total_seconds() for x in op_ss)
                        step_durations.append(secs)
                    elif s.timestamp_inizio and s.timestamp_fine:
                        step_durations.append((s.timestamp_fine - s.timestamp_inizio).total_seconds())
                if step_durations:
                    avg_secs = sum(step_durations) / len(step_durations)
                    tempo_medio = OrderManager._format_duration(timedelta(seconds=avg_secs))
                else:
                    tempo_medio = "N/A"

                # Puntualita: % ordini COMPLETATI in tempo
                op_order_ids = set(s.order_id for s in completed_steps)
                tot_completati = 0
                in_tempo = 0
                for oid in op_order_ids:
                    order = all_orders.get(oid)
                    if not order or order.status != 'COMPLETATO':
                        continue
                    tot_completati += 1
                    if not order.data_consegna:
                        continue
                    order_steps = steps_by_order.get(oid, [])
                    finished = [st.timestamp_fine for st in order_steps if st.timestamp_fine]
                    if finished and max(finished) <= order.data_consegna:
                        in_tempo += 1
                puntualita = round((in_tempo / tot_completati * 100) if tot_completati > 0 else 100)

                # Ritardi: ordini attivi scaduti dove l'operatore ha step non completato
                active_steps = [s for s in op_steps if s.timestamp_inizio and not s.timestamp_fine]
                ritardi = 0
                for s in active_steps:
                    order = all_orders.get(s.order_id)
                    if order and order.data_consegna and order.data_consegna < now and order.status not in ('COMPLETATO', 'SPEDITO'):
                        ritardi += 1

                # Saturazione oggi: ore lavorate / 8h turno
                op_sessions_oggi = [x for x in sessions_by_operator.get(name, []) if x.timestamp_fine >= today_start]
                tempo_oggi_sec = sum((x.timestamp_fine - x.timestamp_inizio).total_seconds() for x in op_sessions_oggi)
                saturazione = min(100, round(tempo_oggi_sec / (TURNO_ORE * 3600) * 100)) if tempo_oggi_sec > 0 else 0

                kpi_list.append({
                    'operaio': name,
                    'user_id': user.id,
                    'role': user.role,
                    'initials': user.initials,
                    'ordini_completati': ordini_completati,
                    'tempo_medio': tempo_medio,
                    'ultimo_accesso': user.last_login.isoformat() if user.last_login else 'Mai',
                    'puntualita': puntualita,
                    'ritardi': ritardi,
                    'saturazione': saturazione
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
    def _apply_archive_filters(query, filters, session):
        """Applica filtri comuni alle query archivio"""
        if not filters:
            return query
        if filters.get('cliente'):
            query = query.filter(Order.cliente.ilike(f"%{filters['cliente']}%"))
        if filters.get('date_from'):
            date_from = datetime.fromisoformat(filters['date_from'])
            query = query.filter(Order.data_consegna >= date_from)
        if filters.get('date_to'):
            date_to = datetime.fromisoformat(filters['date_to'])
            date_to = date_to.replace(hour=23, minute=59, second=59)
            query = query.filter(Order.data_consegna <= date_to)
        if filters.get('operatore'):
            op_name = filters['operatore']
            order_ids = [s.order_id for s in session.query(ProcessingStep.order_id).filter(
                ProcessingStep.operatore.ilike(f"%{op_name}%")
            ).distinct()]
            query = query.filter(Order.id.in_(order_ids))
        return query

    @staticmethod
    def get_completed_orders(filters: dict = None, page: int = 1, limit: int = 10,
                            sort_by: str = 'data_consegna', sort_dir: str = 'desc') -> dict:
        """
        Recupera ordini completati con paginazione e filtri
        """
        session = get_session()
        try:
            from sqlalchemy import func

            query = session.query(Order).filter(
                Order.status.in_(["COMPLETATO", "PARZIALE"]),
                Order.parent_order_id.is_(None)  # Escludi lotti figli
            )

            query = ArchiveManager._apply_archive_filters(query, filters, session)

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

                # Info lotti per archivio (tempi aggregati)
                lotti_detail = []
                if order.lotto_numero and order.lotto_numero > 0:
                    child_lotti = session.query(Order).filter(
                        Order.parent_order_id == order.id,
                        Order.is_deleted == False
                    ).order_by(Order.lotto_numero.asc()).all()
                    # Aggiungi tempi dei lotti figli ai tempi fase del padre
                    for l in child_lotti:
                        l_phase_times = ArchiveManager._calculate_phase_times(l.id, session)
                        l_total_hours = OrderManager._calculate_total_hours(l.id, session)
                        lotti_detail.append({
                            'lotto_numero': l.lotto_numero,
                            'lotto_nome': l.lotto_nome or '',
                            'phase_times': l_phase_times,
                            'total_hours': round(l_total_hours, 2)
                        })
                        # Somma ai tempi totali
                        for fase_key, tempo in l_phase_times.items():
                            if fase_key in phase_times:
                                # Somma secondi
                                phase_times[fase_key] = (phase_times.get(fase_key, 0) or 0) + (tempo or 0) if isinstance(tempo, (int, float)) else phase_times[fase_key]
                        total_hours += l_total_hours
                    # Ricalcola costo e margine con lotti inclusi
                    costo_manodopera = total_hours * costo_orario
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
                    'status': order.status,
                    'lotto_numero': order.lotto_numero or 0,
                    'lotto_nome': order.lotto_nome or '',
                    'lotti_detail': lotti_detail
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
                        'completamento_parziale': step.completamento_parziale,
                        'sessioni': [
                            {
                                'timestamp_inizio': s.timestamp_inizio.isoformat() if s.timestamp_inizio else None,
                                'timestamp_fine': s.timestamp_fine.isoformat() if s.timestamp_fine else None,
                                'tipo_chiusura': s.tipo_chiusura,
                                'operatore': s.operatore,
                                'durata_secondi': int((s.timestamp_fine - s.timestamp_inizio).total_seconds()) if s.timestamp_fine and s.timestamp_inizio else None
                            }
                            for s in session.query(PhaseSession).filter(
                                PhaseSession.step_id == step.id
                            ).order_by(PhaseSession.timestamp_inizio).all()
                        ]
                    }
                    for step in steps
                ],
                'status': order.status,
                'support_requests': [{
                    'id': sr.id,
                    'operatore_principale': sr.operatore_principale,
                    'nome_principale': (session.query(User).filter(User.id == sr.operatore_principale).first() or User(name='')).name,
                    'operatore_supporto': sr.operatore_supporto,
                    'nome_supporto': (session.query(User).filter(User.id == sr.operatore_supporto).first() or User(name='')).name,
                    'stato': sr.stato
                } for sr in session.query(SupportRequest).filter(
                    SupportRequest.order_id == order.id,
                    SupportRequest.stato.in_(['pending', 'accepted'])
                ).all()]
            }
        finally:
            session.close()

    @staticmethod
    def export_csv_data(filters: dict = None) -> list[dict]:
        """Esporta dati di archivio in formato CSV (una riga per ordine)"""
        session = get_session()
        try:
            query = session.query(Order).filter(
                Order.status.in_(["COMPLETATO", "PARZIALE"])
            )
            query = ArchiveManager._apply_archive_filters(query, filters, session)
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

    @staticmethod
    def export_excel_data(filters: dict = None) -> list[dict]:
        """
        Esporta dati di archivio con UNA RIGA PER OPERATORE PER FASE.
        Ogni operatore (principale, supporto, delegato) ha la sua riga.
        A fine ordine, riga riepilogativa con somma tempi.
        Ritorna (rows, summary_row_indices) per formattazione Excel.
        """
        session = get_session()
        try:
            query = session.query(Order).filter(
                Order.status.in_(["COMPLETATO", "PARZIALE"]),
                Order.parent_order_id.is_(None)  # Solo ordini padre/normali
            )
            query = ArchiveManager._apply_archive_filters(query, filters, session)
            orders = query.order_by(Order.data_consegna.desc()).all()

            rows = []
            summary_indices = []  # indici righe riepilogo

            for order in orders:
                # Raccoglie tutti gli ordini da processare (padre + eventuali lotti figli)
                all_order_objs = [order]
                if order.lotto_numero and order.lotto_numero > 0:
                    child_lotti = session.query(Order).filter(
                        Order.parent_order_id == order.id,
                        Order.is_deleted == False
                    ).order_by(Order.lotto_numero.asc()).all()
                    all_order_objs.extend(child_lotti)
                order_total_sec = 0

                for current_order in all_order_objs:
                    lotto_label = f" (L{current_order.lotto_numero})" if current_order.lotto_numero and current_order.lotto_numero > 0 else ""
                    lotto_col = (current_order.lotto_nome or f'L{current_order.lotto_numero}') if current_order.lotto_numero and current_order.lotto_numero > 0 else ''

                    notification = session.query(OrderNotification).filter(
                        OrderNotification.order_id == current_order.id
                    ).first()

                    last_step = session.query(ProcessingStep).filter(
                        ProcessingStep.order_id == current_order.id,
                        ProcessingStep.timestamp_fine.isnot(None)
                    ).order_by(ProcessingStep.timestamp_fine.desc()).first()
                    completion_date = last_step.timestamp_fine if last_step else None

                    steps = session.query(ProcessingStep).filter(
                        ProcessingStep.order_id == current_order.id
                    ).order_by(ProcessingStep.timestamp_inizio).all()

                    base_info = {
                        'Cliente': order.cliente,
                        'Numero Ordine': (order.numero_ordine or order.id[:8]) + lotto_label,
                        'Lotto': lotto_col,
                        'Data Caricamento': order.data_ricezione.strftime('%d/%m/%Y %H:%M') if order.data_ricezione else '',
                        'Data Completamento': completion_date.strftime('%d/%m/%Y %H:%M') if completion_date else '',
                    }

                    if not steps:
                        continue

                    for step in steps:
                        sessions_list = session.query(PhaseSession).filter(
                            PhaseSession.step_id == step.id
                        ).order_by(PhaseSession.timestamp_inizio).all()

                        # Raggruppa sessioni per operatore
                        op_sessions = {}
                        for s in sessions_list:
                            op_name = s.operatore or 'Sconosciuto'
                            op_sessions.setdefault(op_name, []).append(s)

                        main_op = step.operatore or ''
                        fase_inizio = step.timestamp_inizio.strftime('%d/%m/%Y %H:%M') if step.timestamp_inizio else ''
                        fase_fine = step.timestamp_fine.strftime('%d/%m/%Y %H:%M') if step.timestamp_fine else ''

                        if op_sessions:
                            for op_name, op_ss in op_sessions.items():
                                op_sec = sum(
                                    int((s.timestamp_fine - s.timestamp_inizio).total_seconds())
                                    for s in op_ss if s.timestamp_fine
                                )
                                order_total_sec += op_sec
                                ruolo = 'Principale' if op_name == main_op else 'Supporto'

                                rows.append({
                                    **base_info,
                                    'Fase': step.fase + lotto_label,
                                    'Operatore': op_name,
                                    'Ruolo': ruolo,
                                    'Inizio': fase_inizio,
                                    'Fine': fase_fine,
                                    'Tempo Lavorato': ArchiveManager._format_seconds(op_sec),
                                    'Sessioni': str(len(op_ss)),
                                })
                        elif step.timestamp_inizio and step.timestamp_fine:
                            dur_sec = int((step.timestamp_fine - step.timestamp_inizio).total_seconds())
                            order_total_sec += dur_sec
                            rows.append({
                                **base_info,
                                'Fase': step.fase + lotto_label,
                                'Operatore': main_op,
                                'Ruolo': 'Principale',
                                'Inizio': fase_inizio,
                                'Fine': fase_fine,
                                'Tempo Lavorato': ArchiveManager._format_seconds(dur_sec),
                                'Sessioni': '1',
                            })
                        else:
                            rows.append({
                                **base_info,
                                'Fase': step.fase + lotto_label,
                                'Operatore': main_op,
                                'Ruolo': 'Principale',
                                'Inizio': fase_inizio,
                                'Fine': fase_fine,
                                'Tempo Lavorato': '',
                                'Sessioni': '',
                            })

                        # Riga delegato se presente
                        delega = session.query(PhaseDelegation).filter(
                            PhaseDelegation.order_id == current_order.id,
                            PhaseDelegation.fase == step.fase,
                            PhaseDelegation.stato == 'completed'
                        ).first()
                        if delega:
                            delegato_user = session.query(User).filter(User.id == delega.operatore_delegato).first()
                            del_name = delegato_user.name if delegato_user else delega.operatore_delegato
                            del_sec = delega.durata_effettiva or 0
                            order_total_sec += del_sec
                            rows.append({
                                **base_info,
                                'Fase': step.fase + lotto_label,
                                'Operatore': del_name,
                                'Ruolo': 'Delegato',
                                'Inizio': '',
                                'Fine': '',
                                'Tempo Lavorato': ArchiveManager._format_seconds(del_sec) if del_sec else '',
                                'Sessioni': '',
                            })

                # Riga riepilogativa ordine (totale di tutti i lotti)
                summary_indices.append(len(rows))
                rows.append({
                    'Cliente': '',
                    'Numero Ordine': '',
                    'Lotto': '',
                    'Data Caricamento': '',
                    'Data Completamento': '',
                    'Fase': 'RIEPILOGO',
                    'Operatore': f"{order.cliente} #{order.numero_ordine or order.id[:8]}",
                    'Ruolo': '',
                    'Inizio': '',
                    'Fine': '',
                    'Tempo Lavorato': ArchiveManager._format_seconds(order_total_sec) if order_total_sec > 0 else '',
                    'Sessioni': '',
                })

            return rows, summary_indices
        finally:
            session.close()

    @staticmethod
    def _format_seconds(total_sec: int) -> str:
        """Formatta secondi in 'Xh YYmin'"""
        if total_sec <= 0:
            return '0min'
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes:02d}min"
        return f"{minutes}min"

    @staticmethod
    def get_archive_operators() -> list[str]:
        """Ritorna lista nomi operatori che hanno lavorato su ordini completati"""
        session = get_session()
        try:
            operators = session.query(ProcessingStep.operatore).join(
                Order, Order.id == ProcessingStep.order_id
            ).filter(
                Order.status.in_(["COMPLETATO", "PARZIALE"]),
                ProcessingStep.operatore.isnot(None)
            ).distinct().all()
            return sorted([op[0] for op in operators if op[0]])
        finally:
            session.close()

    @staticmethod
    def get_archive_clients() -> list[str]:
        """Ritorna lista clienti con ordini completati"""
        session = get_session()
        try:
            clients = session.query(Order.cliente).filter(
                Order.status.in_(["COMPLETATO", "PARZIALE"])
            ).distinct().all()
            return sorted([c[0] for c in clients if c[0]])
        finally:
            session.close()


class NotificationManager:
    """Gestore notifiche UI tipo WhatsApp per supervisore/admin"""

    @staticmethod
    def create_notification(user_id: str, order_id: str, title: str, message: str,
                           notification_type: str = 'order', notification_category: str = 'informativa') -> dict:
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
                notification_category=notification_category,
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
                'notification_category': notification_category,
                'is_read': notification.is_read,
                'is_deleted': notification.is_deleted
            }
        except Exception as e:
            session.rollback()
            logger.error(f"create_notification: {e}")
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
                    'notification_category': getattr(n, 'notification_category', 'informativa') or 'informativa',
                    'is_read': n.is_read,
                    'is_deleted': n.is_deleted
                })
            return result
        except Exception as e:
            logger.error(f"get_notifications: {e}")
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
            logger.error(f"delete_notification: {e}")
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
            logger.error(f"delete_all_notifications: {e}")
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
            logger.error(f"mark_as_read: {e}")
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
            logger.error(f"get_unread_count: {e}")
            return 0
        finally:
            session.close()

    @staticmethod
    def cleanup_old_notifications(days: int = 30) -> int:
        """Elimina notifiche lette più vecchie di N giorni. Ritorna il numero eliminato."""
        session = get_session()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            deleted = session.query(Notification).filter(
                Notification.is_read == True,
                Notification.timestamp < cutoff
            ).delete()
            session.commit()
            return deleted
        except Exception as e:
            session.rollback()
            logging.error(f"[NOTIF] Errore cleanup: {e}")
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
            logger.error(f"check_alerts: {e}")
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
            TURNO_ORE = 8  # Durata turno standard in ore

            # === PRE-CARICAMENTO DATI (eliminare N+1) ===
            all_orders = session.query(Order).all()
            all_steps = session.query(ProcessingStep).all()

            # Mappa order_id -> lista steps
            steps_by_order = {}
            for s in all_steps:
                steps_by_order.setdefault(s.order_id, []).append(s)

            # Pre-carica tutte le sessioni chiuse
            all_closed_sessions = session.query(PhaseSession).filter(
                PhaseSession.timestamp_fine != None
            ).all()
            sessions_by_step = {}
            for ps in all_closed_sessions:
                sessions_by_step.setdefault(ps.step_id, []).append(ps)
            sessions_by_operator = {}
            for ps in all_closed_sessions:
                op_name = ps.operatore or 'unknown'
                sessions_by_operator.setdefault(op_name, []).append(ps)

            # === RIEPILOGO ===
            ordini_attivi = sum(1 for o in all_orders if o.status not in ('COMPLETATO', 'SPEDITO'))

            # Completati oggi: ordine COMPLETATO con ultimo step finito oggi
            completati_oggi = 0
            for o in all_orders:
                if o.status != 'COMPLETATO':
                    continue
                order_steps = steps_by_order.get(o.id, [])
                finished = [s.timestamp_fine for s in order_steps if s.timestamp_fine]
                if finished and max(finished) >= today_start:
                    completati_oggi += 1

            in_ritardo = sum(1 for o in all_orders
                if o.data_consegna and o.data_consegna < now
                and o.status not in ('COMPLETATO', 'SPEDITO'))

            # Efficienza puntualita: ordini dove ULTIMO step completato <= data_consegna
            completati_totali = 0
            completati_in_tempo = 0
            for o in all_orders:
                if o.status != 'COMPLETATO':
                    continue
                completati_totali += 1
                if not o.data_consegna:
                    continue
                order_steps = steps_by_order.get(o.id, [])
                finished = [s.timestamp_fine for s in order_steps if s.timestamp_fine]
                if finished and max(finished) <= o.data_consegna:
                    completati_in_tempo += 1
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
                User.role.in_(['Operaio Officina', 'Operaio Laser', 'Capo Officina']),
                User.is_active == True
            ).all()

            # Pre-carica steps completati per operatore (evita query nel loop)
            all_completed_steps_by_op = {}
            for s in all_steps:
                if s.operatore and s.timestamp_fine:
                    all_completed_steps_by_op.setdefault(s.operatore, []).append(s)

            # Mappa order_id -> Order per lookup puntualita
            orders_by_id = {o.id: o for o in all_orders}

            for op in operators:
                op_sessions = sessions_by_operator.get(op.name, [])
                completed_steps = all_completed_steps_by_op.get(op.name, [])
                steps_oggi = [s for s in completed_steps if s.timestamp_fine >= today_start]

                # Tempo medio per step: somma sessioni reali / numero step
                step_real_times = []
                for s in completed_steps:
                    step_ss = sessions_by_step.get(s.id, [])
                    op_step_ss = [x for x in step_ss if x.operatore == op.name]
                    if op_step_ss:
                        real_secs = sum((x.timestamp_fine - x.timestamp_inizio).total_seconds() for x in op_step_ss)
                        step_real_times.append(real_secs)
                    elif s.timestamp_inizio and s.timestamp_fine:
                        step_real_times.append((s.timestamp_fine - s.timestamp_inizio).total_seconds())
                tempo_medio_min = round(sum(step_real_times) / len(step_real_times) / 60) if step_real_times else None

                # Tempo totale lavorato oggi (dalle sessioni)
                sessioni_oggi = [x for x in op_sessions if x.timestamp_fine >= today_start]
                tempo_oggi_sec = sum((x.timestamp_fine - x.timestamp_inizio).total_seconds() for x in sessioni_oggi)

                ordini_unici = len(set(s.order_id for s in completed_steps))

                # Step attivo (in corso)
                active_session = session.query(PhaseSession).filter(
                    PhaseSession.operatore == op.name,
                    PhaseSession.timestamp_fine == None
                ).first()
                active_step = None
                if active_session:
                    active_step = session.query(ProcessingStep).filter(
                        ProcessingStep.id == active_session.step_id
                    ).first()

                clienti = session.query(OperatorClient).filter(
                    OperatorClient.operator_id == op.id
                ).count()

                is_online = op.last_login and op.last_login >= today_start

                # SATURAZIONE: ore lavorate oggi / turno 8h * 100
                saturazione = min(100, round(tempo_oggi_sec / (TURNO_ORE * 3600) * 100)) if tempo_oggi_sec > 0 else 0

                # PUNTUALITA: % ordini completati in tempo dall'operatore
                # Per ogni ordine unico dell'operatore che e' COMPLETATO,
                # verifica se l'ultimo step globale e' entro data_consegna
                ordini_completati_op = set(s.order_id for s in completed_steps)
                op_totale_completati = 0
                op_in_tempo = 0
                for oid in ordini_completati_op:
                    order = orders_by_id.get(oid)
                    if not order or order.status != 'COMPLETATO':
                        continue
                    op_totale_completati += 1
                    if not order.data_consegna:
                        continue
                    order_steps = steps_by_order.get(oid, [])
                    finished = [st.timestamp_fine for st in order_steps if st.timestamp_fine]
                    if finished and max(finished) <= order.data_consegna:
                        op_in_tempo += 1
                puntualita = round((op_in_tempo / op_totale_completati * 100) if op_totale_completati > 0 else 100)

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
                    'tempo_oggi_minuti': round(tempo_oggi_sec / 60) if tempo_oggi_sec > 0 else 0,
                    'clienti_assegnati': clienti,
                    'fase_attiva': active_step.fase if active_step else None,
                    'ordine_attivo': active_step.order_id if active_step else None,
                    'saturazione': saturazione,
                    'puntualita': puntualita
                })

            # === KPI FASI/MACCHINARI ===
            fasi_kpi = []
            for fase_nome in ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA']:
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

                completed_in_fase = [s for s in all_steps if s.fase == fase_nome and s.timestamp_fine]
                completati_oggi_fase = sum(1 for s in completed_in_fase if s.timestamp_fine >= today_start)

                durations_fase = []
                for s in completed_in_fase:
                    step_ss = sessions_by_step.get(s.id, [])
                    if step_ss:
                        real_secs = sum((x.timestamp_fine - x.timestamp_inizio).total_seconds() for x in step_ss)
                        durations_fase.append(real_secs)
                    elif s.timestamp_inizio and s.timestamp_fine:
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
            logger.error(f"get_dashboard_kpi: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            session.close()


class DelegationManager:
    """Gestore deleghe di fase tra operatori"""

    @staticmethod
    def create_delegation(order_id: str, fase: str, op_principale: str,
                          op_delegato: str, delegata_da: str,
                          forzata: bool = False, note: str = "") -> dict:
        """Crea una delega di fase. Se forzata (dal capo), stato = accepted."""
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Ordine non trovato"}

            # Verifica che non esista già una delega attiva per questa fase/ordine
            existing = session.query(PhaseDelegation).filter(
                PhaseDelegation.order_id == order_id,
                PhaseDelegation.fase == fase,
                PhaseDelegation.stato.notin_(['rejected', 'completed'])
            ).first()
            if existing:
                return {"success": False, "error": "Esiste già una delega attiva per questa fase"}

            delegation = PhaseDelegation(
                id=str(uuid.uuid4()),
                order_id=order_id,
                fase=fase,
                operatore_principale=op_principale,
                operatore_delegato=op_delegato,
                stato='accepted' if forzata else 'pending',
                delegata_da=delegata_da,
                forzata=forzata,
                scadenza=order.data_consegna,
                note=note
            )
            session.add(delegation)
            session.commit()

            # Notifica operatore delegato
            op_princ = session.query(User).filter(User.id == op_principale).first()
            princ_name = op_princ.name if op_princ else op_principale
            NotificationManager.create_notification(
                user_id=op_delegato,
                order_id=order_id,
                title='Nuova delega fase' if not forzata else 'Delega fase (forzata)',
                message=f'{princ_name} ti ha delegato {fase} per {order.cliente}',
                notification_type='delegation'
            )

            return {"success": True, "delegation_id": delegation.id}
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def accept_delegation(delegation_id: str, operatore_id: str) -> dict:
        """Accetta una delega pending."""
        session = get_session()
        try:
            d = session.query(PhaseDelegation).filter(PhaseDelegation.id == delegation_id).first()
            if not d:
                return {"success": False, "error": "Delega non trovata"}
            if d.operatore_delegato != operatore_id:
                return {"success": False, "error": "Non sei il delegato"}
            if d.stato != 'pending':
                return {"success": False, "error": f"Stato attuale: {d.stato}"}

            d.stato = 'accepted'
            session.commit()

            # Notifica operatore principale
            NotificationManager.create_notification(
                user_id=d.operatore_principale,
                order_id=d.order_id,
                title='Delega accettata',
                message=f'La delega {d.fase} è stata accettata',
                notification_type='delegation'
            )
            return {"success": True}
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def reject_delegation(delegation_id: str, operatore_id: str) -> dict:
        """Rifiuta una delega pending."""
        session = get_session()
        try:
            d = session.query(PhaseDelegation).filter(PhaseDelegation.id == delegation_id).first()
            if not d:
                return {"success": False, "error": "Delega non trovata"}
            if d.operatore_delegato != operatore_id:
                return {"success": False, "error": "Non sei il delegato"}
            if d.stato != 'pending':
                return {"success": False, "error": f"Stato attuale: {d.stato}"}

            d.stato = 'rejected'
            session.commit()

            # Notifica operatore principale + capi
            op_deleg = session.query(User).filter(User.id == operatore_id).first()
            deleg_name = op_deleg.name if op_deleg else operatore_id
            for uid in [d.operatore_principale, 'paolo-responsabile', 'stefano-responsabile']:
                NotificationManager.create_notification(
                    user_id=uid,
                    order_id=d.order_id,
                    title='Delega rifiutata',
                    message=f'{deleg_name} ha rifiutato la delega {d.fase}',
                    notification_type='delegation'
                )
            return {"success": True}
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def start_delegated_phase(delegation_id: str, operatore_id: str) -> dict:
        """Inizia la fase delegata (accepted → in_progress). Chiama OrderManager.start_phase."""
        session = get_session()
        try:
            d = session.query(PhaseDelegation).filter(PhaseDelegation.id == delegation_id).first()
            if not d:
                return {"success": False, "error": "Delega non trovata"}
            if d.operatore_delegato != operatore_id:
                return {"success": False, "error": "Non sei il delegato"}
            if d.stato != 'accepted':
                return {"success": False, "error": f"Stato attuale: {d.stato}"}

            d.stato = 'in_progress'
            d.tempo_inizio_delegato = datetime.utcnow()
            session.commit()

            # Avvia la fase tramite OrderManager
            op = session.query(User).filter(User.id == operatore_id).first()
            op_name = op.name if op else operatore_id
            OrderManager.start_phase(d.order_id, d.fase, op_name)
            return {"success": True, "tempo_inizio": d.tempo_inizio_delegato.isoformat() + 'Z'}
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def complete_delegated_phase(delegation_id: str, operatore_id: str, note: str = "") -> dict:
        """Completa la fase delegata. Chiama OrderManager.complete_phase."""
        session = get_session()
        try:
            d = session.query(PhaseDelegation).filter(PhaseDelegation.id == delegation_id).first()
            if not d:
                return {"success": False, "error": "Delega non trovata"}
            if d.operatore_delegato != operatore_id:
                return {"success": False, "error": "Non sei il delegato"}
            if d.stato != 'in_progress':
                return {"success": False, "error": f"Stato attuale: {d.stato}"}

            d.stato = 'completed'
            d.tempo_fine_delegato = datetime.utcnow()
            if note:
                d.note_delegato = note
            session.commit()

            # Completa la fase tramite OrderManager
            result = OrderManager.complete_phase(d.order_id, d.fase, operatore=operatore_id)

            # Calcola durata_effettiva da sessioni cumulative (non wall-clock)
            try:
                sess2 = get_session()
                order = sess2.query(Order).filter(Order.id == d.order_id).first()
                if order:
                    step = sess2.query(ProcessingStep).filter(
                        ProcessingStep.order_id == d.order_id,
                        ProcessingStep.fase == d.fase
                    ).order_by(ProcessingStep.timestamp_inizio.desc()).first()
                    if step:
                        sessions_list = sess2.query(PhaseSession).filter(
                            PhaseSession.step_id == step.id
                        ).all()
                        cumul = sum(
                            int((s.timestamp_fine - s.timestamp_inizio).total_seconds())
                            for s in sessions_list if s.timestamp_fine
                        )
                        d2 = sess2.query(PhaseDelegation).filter(PhaseDelegation.id == delegation_id).first()
                        if d2:
                            d2.durata_effettiva = cumul
                            sess2.commit()
                sess2.close()
            except Exception:
                pass

            # Notifica operatore principale
            NotificationManager.create_notification(
                user_id=d.operatore_principale,
                order_id=d.order_id,
                title='Fase delegata completata',
                message=f'{d.fase} completata dal delegato',
                notification_type='delegation'
            )
            return result
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def save_partial_delegated_phase(delegation_id: str, operatore_id: str, note: str = "") -> dict:
        """Salva parziale su fase delegata. Chiude sessione ma non lo step."""
        session = get_session()
        try:
            d = session.query(PhaseDelegation).filter(PhaseDelegation.id == delegation_id).first()
            if not d:
                return {"success": False, "error": "Delega non trovata"}
            if d.operatore_delegato != operatore_id:
                return {"success": False, "error": "Non sei il delegato"}
            if d.stato != 'in_progress':
                return {"success": False, "error": f"Stato attuale: {d.stato}"}

            result = OrderManager.save_partial(d.order_id, d.fase, note=note, operatore=operatore_id)
            return result
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def resume_delegated_phase(delegation_id: str, operatore_id: str) -> dict:
        """Riprende una fase delegata in pausa. Crea nuova PhaseSession."""
        session = get_session()
        try:
            d = session.query(PhaseDelegation).filter(PhaseDelegation.id == delegation_id).first()
            if not d:
                return {"success": False, "error": "Delega non trovata"}
            if d.operatore_delegato != operatore_id:
                return {"success": False, "error": "Non sei il delegato"}
            if d.stato != 'in_progress':
                return {"success": False, "error": f"Stato attuale: {d.stato}"}

            # start_phase gestisce il resume: trova step aperto, crea nuova sessione
            op = session.query(User).filter(User.id == operatore_id).first()
            op_name = op.name if op else operatore_id
            OrderManager.start_phase(d.order_id, d.fase, op_name)
            return {"success": True}
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def revoke_delegation(delegation_id: str, revocata_da: str) -> dict:
        """Revoca una delega (solo capo o op_principale)."""
        session = get_session()
        try:
            d = session.query(PhaseDelegation).filter(PhaseDelegation.id == delegation_id).first()
            if not d:
                return {"success": False, "error": "Delega non trovata"}

            # Solo capo o operatore principale può revocare
            user = session.query(User).filter(User.id == revocata_da).first()
            if not user:
                return {"success": False, "error": "Utente non trovato"}
            if not user.is_capo and revocata_da != d.operatore_principale:
                return {"success": False, "error": "Non autorizzato a revocare"}

            if d.stato in ['completed', 'rejected']:
                return {"success": False, "error": f"Impossibile revocare: stato {d.stato}"}

            d.stato = 'rejected'
            session.commit()

            # Notifica delegato
            NotificationManager.create_notification(
                user_id=d.operatore_delegato,
                order_id=d.order_id,
                title='Delega revocata',
                message=f'La delega {d.fase} è stata revocata da {user.name}',
                notification_type='delegation'
            )
            return {"success": True}
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    @staticmethod
    def _serialize_delegation(d, session):
        """Serializza una delega con info sessioni."""
        order = session.query(Order).filter(Order.id == d.order_id).first()
        op_princ = session.query(User).filter(User.id == d.operatore_principale).first()
        op_deleg = session.query(User).filter(User.id == d.operatore_delegato).first()

        # Info sessioni per deleghe in_progress
        sessione_attiva = False
        sessione_attiva_inizio = None
        tempo_cumulativo_secondi = 0
        sessioni_count = 0
        in_pausa = False

        if d.stato == 'in_progress':
            step = session.query(ProcessingStep).filter(
                ProcessingStep.order_id == d.order_id,
                ProcessingStep.fase == d.fase,
                ProcessingStep.timestamp_fine.is_(None)
            ).first()
            if step:
                phase_sessions = session.query(PhaseSession).filter(
                    PhaseSession.step_id == step.id
                ).order_by(PhaseSession.timestamp_inizio).all()
                sessioni_count = len(phase_sessions)
                closed = [s for s in phase_sessions if s.timestamp_fine]
                tempo_cumulativo_secondi = sum(
                    int((s.timestamp_fine - s.timestamp_inizio).total_seconds()) for s in closed
                )
                active_list = [s for s in phase_sessions if s.timestamp_fine is None]
                active = active_list[0] if active_list else None
                sessione_attiva = len(active_list) > 0
                sessione_attiva_inizio = active.timestamp_inizio.isoformat() + 'Z' if active else None
                in_pausa = (not sessione_attiva and sessioni_count > 0)

        return {
            'id': d.id,
            'order_id': d.order_id,
            'cliente': order.cliente if order else 'N/A',
            'numero_ordine': order.numero_ordine if order else None,
            'fase': d.fase,
            'operatore_principale': d.operatore_principale,
            'nome_principale': op_princ.name if op_princ else 'N/A',
            'operatore_delegato': d.operatore_delegato,
            'nome_delegato': op_deleg.name if op_deleg else 'N/A',
            'stato': d.stato,
            'forzata': d.forzata,
            'data_delega': d.data_delega.isoformat() + 'Z' if d.data_delega else None,
            'scadenza': d.scadenza.isoformat() if d.scadenza else None,
            'note': d.note,
            'tempo_inizio_delegato': d.tempo_inizio_delegato.isoformat() + 'Z' if d.tempo_inizio_delegato else None,
            'tempo_fine_delegato': d.tempo_fine_delegato.isoformat() + 'Z' if d.tempo_fine_delegato else None,
            'durata_effettiva': d.durata_effettiva,
            'note_delegato': d.note_delegato,
            'sessione_attiva': sessione_attiva,
            'sessione_attiva_inizio': sessione_attiva_inizio,
            'tempo_cumulativo_secondi': tempo_cumulativo_secondi,
            'sessioni_count': sessioni_count,
            'in_pausa': in_pausa
        }

    @staticmethod
    def get_delegations(order_id: str = None, op_principale: str = None,
                        op_delegato: str = None, stato: str = None) -> list:
        """Query flessibile deleghe con filtri opzionali."""
        session = get_session()
        try:
            query = session.query(PhaseDelegation)

            if order_id:
                query = query.filter(PhaseDelegation.order_id == order_id)
            if op_principale:
                query = query.filter(PhaseDelegation.operatore_principale == op_principale)
            if op_delegato:
                query = query.filter(PhaseDelegation.operatore_delegato == op_delegato)
            if stato:
                query = query.filter(PhaseDelegation.stato == stato)

            delegations = query.order_by(PhaseDelegation.data_delega.desc()).all()
            return [DelegationManager._serialize_delegation(d, session) for d in delegations]
        except Exception as e:
            logger.error(f"get_delegations: {e}")
            return []
        finally:
            session.close()

    @staticmethod
    def get_all_active_delegations() -> list:
        """Per dashboard capo: tutte le deleghe non completate/rifiutate."""
        session = get_session()
        try:
            delegations = session.query(PhaseDelegation).filter(
                PhaseDelegation.stato.notin_(['completed', 'rejected'])
            ).order_by(PhaseDelegation.data_delega.desc()).all()
            return [DelegationManager._serialize_delegation(d, session) for d in delegations]
        except Exception as e:
            logger.error(f"get_all_active_delegations: {e}")
            return []
        finally:
            session.close()


class SupportManager:
    """Gestione richieste di supporto — collaborazione su ordini interi"""

    @staticmethod
    def create_support_request(order_id: str, op_principale: str, op_supporto: str,
                               forzata: bool = False, note: str = "") -> dict:
        """Crea una richiesta di supporto per un ordine"""
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {'success': False, 'error': 'Ordine non trovato'}
            if order.status == 'COMPLETATO':
                return {'success': False, 'error': 'Ordine già completato'}

            # Verifica duplicati attivi
            existing = session.query(SupportRequest).filter(
                SupportRequest.order_id == order_id,
                SupportRequest.operatore_supporto == op_supporto,
                SupportRequest.stato.in_(['pending', 'accepted'])
            ).first()
            if existing:
                return {'success': False, 'error': 'Richiesta di supporto già attiva per questo operatore'}

            req_id = str(uuid.uuid4())
            sr = SupportRequest(
                id=req_id,
                order_id=order_id,
                operatore_principale=op_principale,
                operatore_supporto=op_supporto,
                stato='accepted' if forzata else 'pending',
                forzata=forzata,
                data_richiesta=datetime.utcnow(),
                data_risposta=datetime.utcnow() if forzata else None,
                note=note
            )
            session.add(sr)

            # Nomi per notifiche
            principale = session.query(User).filter(User.id == op_principale).first()
            supporto = session.query(User).filter(User.id == op_supporto).first()
            nome_p = principale.name if principale else op_principale
            nome_s = supporto.name if supporto else op_supporto
            cliente = order.cliente
            numero = order.numero_ordine or order.id[:8]

            if forzata:
                # Notifica al supporto: assegnato dal responsabile
                NotificationManager.create_notification(
                    user_id=op_supporto, order_id=order_id,
                    title='Supporto assegnato',
                    message=f'Sei stato assegnato in supporto a {nome_p} per ordine {cliente} #{numero} (assegnato dal responsabile)',
                    notification_type='order', notification_category='attiva'
                )
            else:
                # Notifica al supporto: richiesta di aiuto
                NotificationManager.create_notification(
                    user_id=op_supporto, order_id=order_id,
                    title='Richiesta di aiuto',
                    message=f'{nome_p} ti chiede aiuto per ordine {cliente} #{numero}',
                    notification_type='order', notification_category='attiva'
                )

            session.commit()

            # Se forzata (auto-accepted), avvia fase per il supporter
            if forzata and order.fase_corrente:
                try:
                    OrderManager.start_phase(order_id, order.fase_corrente, nome_s)
                except Exception as e:
                    logger.warning(f"auto-start phase for forced supporter: {e}")

            return {'success': True, 'support_request_id': req_id}
        except Exception as e:
            session.rollback()
            logger.error(f"create_support_request: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            session.close()

    @staticmethod
    def accept_support_request(request_id: str, operatore_id: str) -> dict:
        """Accetta una richiesta di supporto"""
        session = get_session()
        try:
            sr = session.query(SupportRequest).filter(SupportRequest.id == request_id).first()
            if not sr:
                return {'success': False, 'error': 'Richiesta non trovata'}
            if sr.operatore_supporto != operatore_id:
                return {'success': False, 'error': 'Non autorizzato'}
            if sr.stato != 'pending':
                return {'success': False, 'error': f'Richiesta non in stato pending (stato: {sr.stato})'}

            sr.stato = 'accepted'
            sr.data_risposta = datetime.utcnow()

            # Notifica al principale
            supporto = session.query(User).filter(User.id == sr.operatore_supporto).first()
            order = session.query(Order).filter(Order.id == sr.order_id).first()
            nome_s = supporto.name if supporto else sr.operatore_supporto
            cliente = order.cliente if order else ''
            numero = (order.numero_ordine or order.id[:8]) if order else ''

            NotificationManager.create_notification(
                user_id=sr.operatore_principale, order_id=sr.order_id,
                title='Supporto accettato',
                message=f'{nome_s} ha accettato di aiutarti per ordine {cliente} #{numero}',
                notification_type='order', notification_category='attiva'
            )

            session.commit()

            # Auto-avvia fase per l'operatore di supporto (timer personale indipendente)
            if order and order.fase_corrente:
                try:
                    OrderManager.start_phase(sr.order_id, order.fase_corrente, nome_s)
                except Exception as e:
                    logger.warning(f"auto-start phase for supporter failed: {e}")

            return {'success': True}
        except Exception as e:
            session.rollback()
            logger.error(f"accept_support_request: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            session.close()

    @staticmethod
    def reject_support_request(request_id: str, operatore_id: str) -> dict:
        """Rifiuta una richiesta di supporto"""
        session = get_session()
        try:
            sr = session.query(SupportRequest).filter(SupportRequest.id == request_id).first()
            if not sr:
                return {'success': False, 'error': 'Richiesta non trovata'}
            if sr.operatore_supporto != operatore_id:
                return {'success': False, 'error': 'Non autorizzato'}
            if sr.stato != 'pending':
                return {'success': False, 'error': f'Richiesta non in stato pending (stato: {sr.stato})'}

            sr.stato = 'rejected'
            sr.data_risposta = datetime.utcnow()

            # Notifica al principale
            supporto = session.query(User).filter(User.id == sr.operatore_supporto).first()
            order = session.query(Order).filter(Order.id == sr.order_id).first()
            nome_s = supporto.name if supporto else sr.operatore_supporto
            cliente = order.cliente if order else ''
            numero = (order.numero_ordine or order.id[:8]) if order else ''

            NotificationManager.create_notification(
                user_id=sr.operatore_principale, order_id=sr.order_id,
                title='Supporto rifiutato',
                message=f'{nome_s} ha rifiutato il supporto per ordine {cliente} #{numero}',
                notification_type='order', notification_category='attiva'
            )

            session.commit()
            return {'success': True}
        except Exception as e:
            session.rollback()
            logger.error(f"reject_support_request: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            session.close()

    @staticmethod
    def revoke_support_request(request_id: str) -> dict:
        """Revoca una richiesta di supporto (capo o operatore principale)"""
        session = get_session()
        try:
            sr = session.query(SupportRequest).filter(SupportRequest.id == request_id).first()
            if not sr:
                return {'success': False, 'error': 'Richiesta non trovata'}
            if sr.stato not in ['pending', 'accepted']:
                return {'success': False, 'error': 'Richiesta non revocabile'}

            sr.stato = 'revoked'
            sr.data_risposta = datetime.utcnow()

            # Notifica al supporto
            principale = session.query(User).filter(User.id == sr.operatore_principale).first()
            order = session.query(Order).filter(Order.id == sr.order_id).first()
            nome_p = principale.name if principale else sr.operatore_principale
            cliente = order.cliente if order else ''

            NotificationManager.create_notification(
                user_id=sr.operatore_supporto, order_id=sr.order_id,
                title='Supporto revocato',
                message=f'Il supporto per ordine {cliente} di {nome_p} è stato revocato',
                notification_type='order', notification_category='informativa'
            )

            session.commit()
            return {'success': True}
        except Exception as e:
            session.rollback()
            logger.error(f"revoke_support_request: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            session.close()

    @staticmethod
    def get_support_requests(order_id: str = None, op_principale: str = None,
                             op_supporto: str = None, stato: str = None,
                             active_only: bool = False) -> list:
        """Recupera richieste di supporto con filtri"""
        session = get_session()
        try:
            query = session.query(SupportRequest)
            if order_id:
                query = query.filter(SupportRequest.order_id == order_id)
            if op_principale:
                query = query.filter(SupportRequest.operatore_principale == op_principale)
            if op_supporto:
                query = query.filter(SupportRequest.operatore_supporto == op_supporto)
            if stato:
                query = query.filter(SupportRequest.stato == stato)
            if active_only:
                query = query.filter(SupportRequest.stato.in_(['pending', 'accepted']))

            requests = query.order_by(SupportRequest.data_richiesta.desc()).all()
            return [SupportManager._serialize_support_request(sr, session) for sr in requests]
        except Exception as e:
            logger.error(f"get_support_requests: {e}")
            return []
        finally:
            session.close()

    @staticmethod
    def get_supported_order_ids(operatore_id: str) -> list:
        """Restituisce gli order_id per cui l'operatore è in supporto attivo"""
        session = get_session()
        try:
            requests = session.query(SupportRequest.order_id).filter(
                SupportRequest.operatore_supporto == operatore_id,
                SupportRequest.stato == 'accepted'
            ).all()
            return [r[0] for r in requests]
        except Exception as e:
            logger.error(f"get_supported_order_ids: {e}")
            return []
        finally:
            session.close()

    @staticmethod
    def _serialize_support_request(sr, session) -> dict:
        """Serializza una richiesta di supporto"""
        order = session.query(Order).filter(Order.id == sr.order_id).first()
        principale = session.query(User).filter(User.id == sr.operatore_principale).first()
        supporto = session.query(User).filter(User.id == sr.operatore_supporto).first()
        return {
            'id': sr.id,
            'order_id': sr.order_id,
            'cliente': order.cliente if order else '',
            'numero_ordine': (order.numero_ordine or order.id[:8]) if order else '',
            'operatore_principale': sr.operatore_principale,
            'nome_principale': principale.name if principale else '',
            'operatore_supporto': sr.operatore_supporto,
            'nome_supporto': supporto.name if supporto else '',
            'stato': sr.stato,
            'forzata': sr.forzata,
            'data_richiesta': sr.data_richiesta.isoformat() + 'Z' if sr.data_richiesta else None,
            'data_risposta': sr.data_risposta.isoformat() + 'Z' if sr.data_risposta else None,
            'note': sr.note
        }

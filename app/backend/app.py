"""Flask Backend per Schedulatore Laser"""
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import sys
import uuid
import logging

logger = logging.getLogger(__name__)

# Importa moduli locali
from .models import initialize_database, Order, OrderFile, get_session, SupportRequest as SRModel
from .database import OrderManager, UserManager, AuditManager, ArchiveManager, NotificationManager, OperatorClientManager, AlertManager, KPIManager, DelegationManager, SupportManager

app = Flask(__name__, static_folder=None)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max upload
CORS(app, origins=[r"http://localhost:*", r"http://127\.0\.0\.1:*", r"http://192\.168\.\d+\.\d+:*"])

# Configurazioni
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads')
DRAWINGS_FOLDER = os.path.join(UPLOAD_FOLDER, 'drawings')
PDFS_FOLDER = os.path.join(UPLOAD_FOLDER, 'pdfs')
FRONTEND_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'frontend')

os.makedirs(DRAWINGS_FOLDER, exist_ok=True)
os.makedirs(PDFS_FOLDER, exist_ok=True)

# Error handler globale — no stack trace nelle risposte
@app.errorhandler(Exception)
def handle_unexpected_error(e):
    logging.error(f"Errore non gestito: {e}", exc_info=True)
    return jsonify({'error': 'Errore interno del server'}), 500

@app.errorhandler(413)
def handle_file_too_large(e):
    return jsonify({'error': 'File troppo grande (max 50MB)'}), 413

# Inizializza database
initialize_database()

# ============ UTILITÀ AUTORIZZAZIONE ============

def _require_capo(user_id: str) -> bool:
    """Verifica che user_id appartenga a un utente con is_capo=True."""
    if not user_id:
        return False
    user = UserManager.get_user(user_id)
    return bool(user and user.get('is_capo', False))

# ============ FRONTEND ROUTES ============

@app.route('/')
def index():
    """Serve login page"""
    return send_from_directory(FRONTEND_FOLDER, 'login.html')

@app.route('/<path:filename>')
def serve_frontend(filename):
    """Serve frontend files"""
    return send_from_directory(FRONTEND_FOLDER, filename)

# ============ API AUTH ============

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Autentica utente e registra nel log di audit"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'success': False, 'error': 'user_id obbligatorio'}), 400

        # Autentica e aggiorna last_login
        user = UserManager.authenticate(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'Utente non trovato'}), 404

        return jsonify({
            'success': True,
            'user_id': user['id'],
            'name': user['name'],
            'role': user['role'],
            'phase': user['phase'],
            'permissions': user['permissions'],
            'machines': user['machines'],
            'is_capo': user.get('is_capo', False)
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Registra logout nel log di audit"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')

        if user_id:
            user = UserManager.get_user(user_id)
            if user:
                AuditManager.log(
                    user_id=user_id,
                    user_name=user.get('name'),
                    action='LOGOUT',
                    ip_address=request.remote_addr
                )

        return jsonify({'success': True}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/users', methods=['GET'])
def get_users():
    """Recupera lista utenti (attivi, o tutti se include_inactive=true)"""
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        users = UserManager.get_all_users(include_inactive=include_inactive)
        return jsonify({
            'success': True,
            'users': users
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/users', methods=['POST'])
def create_user():
    """Crea un nuovo utente"""
    try:
        data = request.get_json()
        created_by = data.get('created_by')
        if not _require_capo(created_by):
            return jsonify({'success': False, 'error': 'Operazione riservata al Capo Officina'}), 403

        user_id = data.get('user_id', '').strip()
        name = data.get('name', '').strip()
        role = data.get('role', '').strip()
        phase = data.get('phase', 'LASER').strip()
        permissions = data.get('permissions', [])
        machines = data.get('machines', [])

        if not user_id or not name or not role:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        result = UserManager.create_user(
            user_id=user_id,
            name=name,
            role=role,
            phase=phase,
            permissions=permissions,
            machines=machines
        )

        if result is None:
            return jsonify({'success': False, 'error': 'User already exists'}), 400

        return jsonify({'success': True, 'user': result}), 201

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Disattiva un utente (soft delete)"""
    try:
        data = request.get_json() or {}
        deleted_by = data.get('deleted_by')
        if not _require_capo(deleted_by):
            return jsonify({'success': False, 'error': 'Operazione riservata al Capo Officina'}), 403

        success = UserManager.delete_user(user_id)
        if not success:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        return jsonify({'success': True, 'message': f'User {user_id} deleted'}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    """Modifica un utente esistente"""
    try:
        data = request.get_json()
        updated_by = data.get('updated_by')
        if not _require_capo(updated_by):
            return jsonify({'success': False, 'error': 'Operazione riservata al Capo Officina'}), 403

        result = UserManager.update_user(
            user_id=user_id,
            name=data.get('name'),
            role=data.get('role'),
            phase=data.get('phase'),
            is_active=data.get('is_active')
        )
        if result is None:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        return jsonify({'success': True, 'user': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ============ API ORDINI ============

@app.route('/api/orders', methods=['POST'])
def create_order():
    """Crea un nuovo ordine con routing dinamico"""
    try:
        data = request.get_json()

        numero_ordine = data.get('numero_ordine', '').strip()
        if not numero_ordine:
            return jsonify({'success': False, 'error': 'Numero ordine obbligatorio'}), 400

        cliente = (data.get('cliente') or '').strip()
        if not cliente:
            return jsonify({'success': False, 'error': 'Cliente obbligatorio'}), 400

        data_consegna = data.get('data_consegna')
        if not data_consegna:
            return jsonify({'success': False, 'error': 'Data consegna obbligatoria'}), 400
        # Validazione: data consegna non nel passato (tolleranza: ieri)
        try:
            dc = datetime.strptime(data_consegna, '%Y-%m-%d').date()
            ieri = (datetime.utcnow() - timedelta(days=1)).date()
            if dc < ieri:
                return jsonify({'success': False, 'error': f'Data consegna {data_consegna} è nel passato'}), 400
        except ValueError:
            pass  # formato non standard, lascia che il DB gestisca

        # Check duplicati: stesso cliente + numero ordine (non archiviati)
        existing = OrderManager.get_all_orders_dict(cliente=cliente)
        for ex in existing:
            if (ex.get('numero_ordine') or '').strip().lower() == numero_ordine.lower():
                return jsonify({'success': False, 'error': f'Ordine #{numero_ordine} per {cliente} esiste già'}), 409

        order = OrderManager.create_order(
            cliente=cliente,
            data_consegna=data_consegna,
            destinazione=data.get('destinazione', 'LASER'),
            numero_ordine=numero_ordine,
            note=data.get('note', '')
        )

        # Registra il file PDF nel DB
        session = get_session()
        try:
            pdf_filename = data.get('pdf_filename')
            if pdf_filename:
                pdf_filename = os.path.basename(pdf_filename)
                pdfs_folder = os.path.join(os.path.dirname(__file__), '..', 'uploads', 'pdfs')
                pdf_path = os.path.join(pdfs_folder, pdf_filename)
                if os.path.exists(pdf_path):
                    file_record = OrderFile(
                        id=str(uuid.uuid4()),
                        order_id=order.id,
                        filename=pdf_filename,
                        filepath=pdf_path,
                        file_type='PDF'
                    )
                    session.add(file_record)

            session.commit()
        finally:
            session.close()

        # Notifica solo al gestore del cliente (operatore assegnato)
        destinazione = data.get('destinazione', 'LASER')
        numero_display = order.numero_ordine or order.id[:8]
        op_id = OperatorClientManager.find_operator_for_client(order.cliente)
        if op_id:
            NotificationManager.create_notification(
                user_id=op_id,
                order_id=order.id,
                title='Nuovo ordine',
                message=f'Ordine #{numero_display} ({order.cliente}) inviato a {destinazione}',
                notification_type='order',
                notification_category='informativa'
            )

        return jsonify({
            'success': True,
            'order_id': order.id,
            'cliente': order.cliente,
            'data_consegna': order.data_consegna.isoformat(),
            'fase_corrente': order.fase_corrente,
            'operatore_assegnato': order.operatore_assegnato
        }), 201

    except Exception as e:
        logger.error(f"Create order error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    """Recupera dettagli ordine con stato articoli"""
    try:
        details = OrderManager.get_order_details(order_id)
        if 'error' in details:
            return jsonify(details), 404
        return jsonify(details), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/<order_id>/delivery-date', methods=['PUT'])
def update_delivery_date(order_id):
    """Aggiorna data di consegna di un ordine (drag & drop calendario laser)"""
    try:
        data = request.get_json()
        if not data or 'data_consegna' not in data:
            return jsonify({'success': False, 'error': 'data_consegna obbligatoria'}), 400
        new_date_str = data['data_consegna']
        try:
            new_date = datetime.strptime(new_date_str[:10], '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'error': 'Formato YYYY-MM-DD richiesto'}), 400
        result = OrderManager.update_delivery_date(order_id, new_date)
        if result.get('success'):
            return jsonify(result), 200
        return jsonify(result), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders/<order_id>', methods=['PUT'])
def update_order(order_id):
    """Aggiorna dati ordine: cliente, note, data_consegna, numero_ordine."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Body JSON richiesto'}), 400
        result = OrderManager.update_order(order_id, data)
        if result.get('success'):
            return jsonify(result), 200
        return jsonify(result), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders/<order_id>', methods=['DELETE'])
def delete_order(order_id):
    """Soft delete di un ordine: setta is_deleted=True, non cancella fisicamente i dati"""
    try:
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return jsonify({'success': False, 'error': 'Ordine non trovato'}), 404
            order.is_deleted = True
            session.commit()
            return jsonify({'success': True, 'message': f'Ordine {order_id} eliminato (recuperabile)'}), 200
        finally:
            session.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders/<order_id>/pdf', methods=['GET'])
def get_order_pdf(order_id):
    """Serve il PDF dell'ordine inline (per iframe viewer)"""
    try:
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return jsonify({'error': 'Ordine non trovato'}), 404

            # Cerca il file PDF tra i file allegati
            pdf_file = session.query(OrderFile).filter(
                OrderFile.order_id == order_id,
                OrderFile.file_type == 'PDF'
            ).first()

            if not pdf_file or not os.path.exists(pdf_file.filepath):
                return jsonify({'error': 'PDF non trovato'}), 404

            # Serve il PDF inline per iframe
            return send_file(
                pdf_file.filepath,
                mimetype='application/pdf',
                as_attachment=False,
                download_name=pdf_file.filename
            )

        finally:
            session.close()

    except Exception as e:
        logger.error(f"get_order_pdf: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/<order_id>/dxf/<filename>', methods=['GET'])
def get_dxf_file(order_id, filename):
    """Serve DXF file per download"""
    try:
        # Sanitize filename to prevent directory traversal
        filename = os.path.basename(filename)

        # Verify file exists in drawings folder
        dxf_path = os.path.join(DRAWINGS_FOLDER, filename)

        if not os.path.exists(dxf_path):
            return jsonify({'error': 'File non trovato'}), 404

        # Serve file for download with proper headers
        return send_file(
            dxf_path,
            mimetype='application/dxf',
            as_attachment=True,
            download_name=filename.replace('draft_', '')
        )

    except Exception as e:
        logger.error(f"Get DXF file error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders', methods=['GET'])
def get_orders():
    """Recupera lista ordini con filtri per il nuovo workflow"""
    try:
        cliente = request.args.get('cliente')
        status = request.args.get('status')
        fase_corrente = request.args.get('fase_corrente')
        operatore = request.args.get('operatore')
        orders_data = OrderManager.get_all_orders_dict(
            cliente=cliente, status=status,
            fase_corrente=fase_corrente, operatore=operatore
        )

        # Includi ordini in supporto per l'operatore
        if operatore:
            supported_ids = SupportManager.get_supported_order_ids(operatore)
            if supported_ids:
                existing_ids = {o['id'] for o in orders_data}
                new_ids = [sid for sid in supported_ids if sid not in existing_ids]
                if new_ids:
                    # Carica solo gli ordini supportati mancanti (non tutti)
                    for so in OrderManager.get_orders_by_ids(new_ids):
                        orders_data.append(so)

        return jsonify({'orders': orders_data}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ API FASI ============

@app.route('/api/orders/<order_id>/phase/<phase>/start', methods=['POST'])
def start_phase(order_id, phase):
    """Inizia una fase di lavorazione"""
    try:
        data = request.get_json() or {}
        operatore = data.get('operatore', '')
        operatore_id = data.get('operatore_id')

        # Se operatore_id è fornito ma operatore non lo è, recupera il nome dal database
        if operatore_id and not operatore:
            user = UserManager.get_user(operatore_id)
            if user:
                operatore = user.get('name', operatore_id)

        success = OrderManager.start_phase(order_id, phase, operatore)
        if success:
            # Registra azione nel audit log
            if operatore_id:
                operatore_user = UserManager.get_user(operatore_id)
                operatore_name = operatore_user.get('name') if operatore_user else operatore_id
                AuditManager.log(
                    user_id=operatore_id,
                    user_name=operatore_name,
                    action='START_PHASE',
                    entity_type='phase',
                    entity_id=order_id,
                    detail=f"Phase: {phase}",
                    ip_address=request.remote_addr
                )

            return jsonify({'success': True, 'phase': phase}), 200
        return jsonify({'success': False, 'error': 'Fase non trovata o già iniziata'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/orders/<order_id>/phase/<phase>/complete', methods=['POST'])
def complete_phase(order_id, phase):
    """Completa una fase con routing dinamico"""
    try:
        data = request.get_json() or {}
        note = data.get('note', '')
        fase_successiva = data.get('fase_successiva')
        completamento_parziale = data.get('completamento_parziale', False)
        operatore_id = data.get('operatore_id')

        # Whitelist fase_successiva
        _VALID_PHASES = {'LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'COMPLETATO'}
        if fase_successiva and fase_successiva not in _VALID_PHASES:
            return jsonify({'success': False, 'error': f"fase_successiva '{fase_successiva}' non valida"}), 400

        operatore_name = ''
        if operatore_id:
            user = UserManager.get_user(operatore_id)
            operatore_name = user.get('name', operatore_id) if user else operatore_id

        result = OrderManager.complete_phase(
            order_id, phase,
            fase_successiva=fase_successiva,
            completamento_parziale=completamento_parziale,
            note=note,
            operatore=operatore_name
        )

        if result.get('success'):
            if operatore_id:
                AuditManager.log(
                    user_id=operatore_id,
                    user_name=operatore_name,
                    action='COMPLETE_PHASE',
                    entity_type='phase',
                    entity_id=order_id,
                    detail=f"Phase: {phase} -> {fase_successiva}",
                    ip_address=request.remote_addr
                )

            # Se parziale (paused), ritorna direttamente senza notifiche
            if result.get('paused'):
                return jsonify(result), 200

            # Usa fase_successiva dal result (auto-routing nel DB la calcola se mancante)
            fase_successiva = result.get('fase_successiva', fase_successiva)
            details = OrderManager.get_order_details(order_id)
            cliente = details.get('cliente', '')
            numero_display = details.get('numero_ordine', order_id[:8])

            # Trova gestore del cliente
            op_id = details.get('operatore_assegnato')
            if not op_id:
                op_id = OperatorClientManager.find_operator_for_client(cliente)

            # Notifica ordine completato definitivamente
            if result.get('all_completed'):
                # Notifica impiegata + gestore cliente
                notif_targets = set(['elena-impiegata'])
                if op_id:
                    notif_targets.add(op_id)
                for uid in notif_targets:
                    NotificationManager.create_notification(
                        user_id=uid,
                        order_id=order_id,
                        title='Ordine completato',
                        message=f'Ordine #{numero_display} ({cliente}) - completato',
                        notification_type='completion',
                        notification_category='attiva'
                    )

            # Notifica attiva all'operatore assegnato quando fase completata
            if fase_successiva and fase_successiva not in ('COMPLETATO', 'LASER'):
                if op_id:
                    NotificationManager.create_notification(
                        user_id=op_id,
                        order_id=order_id,
                        title='Ordine pronto',
                        message=f'Ordine #{numero_display} ({cliente}): {phase} completata → {fase_successiva}',
                        notification_type='phase_ready',
                        notification_category='attiva'
                    )

            return jsonify({
                'success': True,
                'phase': phase,
                'fase_successiva': fase_successiva,
                'order_details': details,
                'operatori_tempi': result.get('operatori_tempi', [])
            }), 200

        return jsonify(result), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders/<order_id>/phase/<phase>/save-partial', methods=['POST'])
def save_partial(order_id, phase):
    """Salva parziale: chiude la sessione corrente, mantiene la fase aperta"""
    try:
        data = request.get_json() or {}
        note = data.get('note', '')
        operatore_id = data.get('operatore_id')

        operatore_name = ''
        if operatore_id:
            user = UserManager.get_user(operatore_id)
            operatore_name = user.get('name', operatore_id) if user else operatore_id

        result = OrderManager.save_partial(order_id, phase, note=note, operatore=operatore_name)

        if result.get('success'):
            if operatore_id:
                AuditManager.log(
                    user_id=operatore_id,
                    user_name=operatore_name,
                    action='SAVE_PARTIAL',
                    entity_type='phase',
                    entity_id=order_id,
                    detail=f"Phase: {phase}, Sessions: {result.get('sessioni_count')}",
                    ip_address=request.remote_addr
                )
            return jsonify(result), 200
        return jsonify(result), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders/<order_id>/complete-order', methods=['POST'])
def complete_order_early(order_id):
    """Completa un ordine anticipatamente dalla fase corrente"""
    try:
        data = request.get_json() or {}
        note = data.get('note', '')
        operatore_id = data.get('operatore_id')

        if not operatore_id:
            return jsonify({'success': False, 'error': 'operatore_id obbligatorio'}), 400

        user = UserManager.get_user(operatore_id)
        operatore_name = user.get('name', operatore_id) if user else operatore_id

        # Determina fase corrente
        order = OrderManager.get_order(order_id)
        if not order:
            return jsonify({'success': False, 'error': 'Ordine non trovato'}), 404
        current_phase = order.fase_corrente

        # Solo operatore principale o capo può chiudere l'ordine
        is_capo = user.get('is_capo', False) if user else False
        if not is_capo:
            sr_session = get_session()
            try:
                is_support = sr_session.query(SRModel).filter(
                    SRModel.order_id == order_id,
                    SRModel.operatore_supporto == operatore_id,
                    SRModel.stato == 'accepted'
                ).first()
                if is_support:
                    return jsonify({'success': False, 'error': "Solo l'operatore principale può chiudere l'ordine"}), 403
            finally:
                sr_session.close()

        result = OrderManager.complete_order(order_id, current_phase, note=note, operatore=operatore_name)

        if result.get('success'):
            AuditManager.log(
                user_id=operatore_id,
                user_name=operatore_name,
                action='COMPLETE_ORDER',
                entity_type='order',
                entity_id=order_id,
                detail=f"Ordine completato anticipatamente da fase {current_phase}",
                ip_address=request.remote_addr
            )

            # Notifiche completamento ordine — solo impiegata + gestore cliente
            details = OrderManager.get_order_details(order_id)
            cliente = details.get('cliente', '')
            numero_display = details.get('numero_ordine', order_id[:8])

            notif_targets = set(['elena-impiegata'])
            op_id = details.get('operatore_assegnato')
            if not op_id:
                op_id = OperatorClientManager.find_operator_for_client(cliente)
            if op_id:
                notif_targets.add(op_id)
            for uid in notif_targets:
                NotificationManager.create_notification(
                    user_id=uid,
                    order_id=order_id,
                    title='Ordine completato',
                    message=f'Ordine #{numero_display} ({cliente}) - completato',
                    notification_type='completion',
                    notification_category='attiva'
                )

            return jsonify(result), 200
        return jsonify(result), 400

    except Exception as e:
        logger.error(f"Phase operation error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/phase/<phase>/orders', methods=['GET'])
def get_orders_by_phase(phase):
    """Recupera ordini per fase corrente"""
    try:
        operatore_id = request.args.get('operatore')
        orders = OrderManager.get_orders_by_phase(phase, operatore_id)

        result = []
        existing_ids = set()
        for order in orders:
            details = OrderManager.get_order_details(order.id)
            result.append(details)
            existing_ids.add(order.id)

        # Includi ordini in supporto per l'operatore
        if operatore_id:
            supported_ids = SupportManager.get_supported_order_ids(operatore_id)
            for sid in supported_ids:
                if sid not in existing_ids:
                    details = OrderManager.get_order_details(sid)
                    if details and not details.get('error') and details.get('fase_corrente') == phase:
                        result.append(details)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ API NUOVE: WORKFLOW DINAMICO ============

@app.route('/api/orders/<order_id>/complete-laser', methods=['POST'])
def complete_laser(order_id):
    """Operatore laser: segna taglio completato"""
    try:
        data = request.get_json() or {}
        operatore_id = data.get('operatore_id')

        operatore_name = ''
        if operatore_id:
            user = UserManager.get_user(operatore_id)
            operatore_name = user.get('name', operatore_id) if user else operatore_id

        result = OrderManager.complete_laser(order_id, operatore_name)
        if result.get('success'):
            if operatore_id:
                AuditManager.log(
                    user_id=operatore_id,
                    user_name=operatore_name,
                    action='COMPLETE_LASER',
                    entity_type='phase',
                    entity_id=order_id,
                    detail='Taglio laser completato'
                )
            return jsonify(result), 200
        return jsonify(result), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders/<order_id>/send-to-laser', methods=['POST'])
def send_to_laser(order_id):
    """Operatore officina rimanda ordine al laser"""
    try:
        data = request.get_json() or {}
        operatore_id = data.get('operatore_id')

        result = OrderManager.send_to_laser(order_id, operatore_id or '')
        if result.get('success'):
            if operatore_id:
                user = UserManager.get_user(operatore_id)
                AuditManager.log(
                    user_id=operatore_id,
                    user_name=user.get('name') if user else operatore_id,
                    action='SEND_TO_LASER',
                    entity_type='order',
                    entity_id=order_id
                )
            return jsonify(result), 200
        return jsonify(result), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders/<order_id>/reassign', methods=['POST'])
def reassign_order(order_id):
    """Capo officina: riassegna ordine a un altro operatore"""
    try:
        data = request.get_json() or {}
        new_operator_id = data.get('new_operator_id')
        capo_id = data.get('capo_id')

        if not new_operator_id:
            return jsonify({'success': False, 'error': 'new_operator_id obbligatorio'}), 400
        if not _require_capo(capo_id):
            return jsonify({'success': False, 'error': 'Operazione riservata al Capo Officina'}), 403

        result = OrderManager.reassign_order(order_id, new_operator_id)
        if result.get('success'):
            AuditManager.log(
                user_id=data.get('capo_id', 'admin'),
                action='REASSIGN_ORDER',
                entity_type='order',
                entity_id=order_id,
                detail=f'Riassegnato a {new_operator_id}'
            )
        return jsonify(result), 200 if result.get('success') else 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders/<order_id>/correct-time', methods=['PUT'])
def correct_time(order_id):
    """Capo officina: corregge timestamp di una fase"""
    try:
        data = request.get_json() or {}
        step_id = data.get('step_id')
        new_start = data.get('timestamp_inizio')
        new_end = data.get('timestamp_fine')
        capo_id = data.get('capo_id')

        if not step_id:
            return jsonify({'success': False, 'error': 'step_id obbligatorio'}), 400
        if not _require_capo(capo_id):
            return jsonify({'success': False, 'error': 'Operazione riservata al Capo Officina'}), 403

        result = OrderManager.correct_time(step_id, new_start, new_end)
        if result.get('success'):
            AuditManager.log(
                user_id=data.get('capo_id', 'admin'),
                action='CORRECT_TIME',
                entity_type='phase',
                entity_id=order_id,
                detail=f'Step {step_id}: start={new_start}, end={new_end}'
            )
        return jsonify(result), 200 if result.get('success') else 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders/<order_id>/move-phase', methods=['POST'])
def move_phase(order_id):
    """Capo officina: sposta ordine a qualsiasi fase"""
    try:
        data = request.get_json() or {}
        new_phase = data.get('new_phase')
        capo_id = data.get('capo_id')

        VALID_PHASES = {'LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'COMPLETATO', 'PARZIALE'}
        if not new_phase:
            return jsonify({'success': False, 'error': 'new_phase obbligatorio'}), 400
        if new_phase not in VALID_PHASES:
            return jsonify({'success': False, 'error': f'Fase non valida: {new_phase}'}), 400
        if not _require_capo(capo_id):
            return jsonify({'success': False, 'error': 'Operazione riservata al Capo Officina'}), 403

        result = OrderManager.move_phase(order_id, new_phase)
        if result.get('success'):
            AuditManager.log(
                user_id=data.get('capo_id', 'admin'),
                action='MOVE_PHASE',
                entity_type='order',
                entity_id=order_id,
                detail=f'Spostato a {new_phase}'
            )
        return jsonify(result), 200 if result.get('success') else 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API OPERATOR-CLIENTS ============

@app.route('/api/operator-clients', methods=['GET'])
def get_operator_clients():
    """Lista assegnazioni operatore-cliente"""
    try:
        operator_id = request.args.get('operator_id')
        if operator_id:
            assignments = OperatorClientManager.get_by_operator(operator_id)
        else:
            assignments = OperatorClientManager.get_all()
        return jsonify({'success': True, 'assignments': assignments}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/operator-clients', methods=['POST'])
def create_operator_client():
    """Crea nuova assegnazione operatore-cliente"""
    try:
        data = request.get_json() or {}
        operator_id = data.get('operator_id')
        client_name = data.get('client_name')

        if not operator_id or not client_name:
            return jsonify({'success': False, 'error': 'operator_id e client_name obbligatori'}), 400

        result = OperatorClientManager.create(operator_id, client_name)
        return jsonify({'success': True, 'assignment': result}), 201

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/operator-clients/<assignment_id>', methods=['DELETE'])
def delete_operator_client(assignment_id):
    """Rimuovi assegnazione operatore-cliente"""
    try:
        success = OperatorClientManager.delete(assignment_id)
        if success:
            return jsonify({'success': True}), 200
        return jsonify({'success': False, 'error': 'Assegnazione non trovata'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ============ API ALERTS ============

@app.route('/api/alerts/check', methods=['GET'])
def check_alerts():
    """Controlla alert automatici (timer lunghi, ordini fermi, scadenze)"""
    try:
        alerts = AlertManager.check_alerts()
        return jsonify({'success': True, 'alerts': alerts, 'count': len(alerts)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API KPI DASHBOARD ============

@app.route('/api/kpi/dashboard', methods=['GET'])
def get_kpi_dashboard():
    """KPI operatori e fasi per dashboard Capo Officina"""
    try:
        result = KPIManager.get_dashboard_kpi()
        return jsonify(result), 200 if result.get('success') else 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API ADMIN ============

@app.route('/api/admin/kpi', methods=['GET'])
def get_admin_kpi():
    """Recupera KPI sistema per admin dashboard"""
    try:
        # Ordini attivi (non SPEDITO)
        all_orders = OrderManager.get_all_orders_dict()
        active_orders = [o for o in all_orders if o.get('status') not in ('COMPLETATO', 'PARZIALE')]
        ordini_attivi = len(active_orders)

        # KPI operai
        kpi_operai = AuditManager.get_kpi_operai()

        # Calcola login oggi
        from datetime import datetime as dt
        today = dt.now().date()
        audit_logs = AuditManager.get_recent(limit=1000)
        login_oggi = len([
            log for log in audit_logs
            if log['action'] == 'LOGIN' and dt.fromisoformat(log['timestamp']).date() == today
        ])

        # Calcola efficienza: ordini completati on-time vs totali
        completed_orders = [o for o in all_orders if o.get('status') in ('COMPLETATO', 'PARZIALE')]
        if completed_orders:
            on_time = sum(1 for o in completed_orders if o.get('data_consegna') and dt.fromisoformat(o['data_consegna']).date() >= today)
            efficienza = int((on_time / len(completed_orders)) * 100)
        else:
            efficienza = 0

        # Ritardi: ordini scaduti non completati
        ritardi = sum(1 for o in active_orders if o.get('data_consegna') and dt.fromisoformat(o['data_consegna']).date() < today)

        return jsonify({
            'success': True,
            'kpi_globali': {
                'ordini_attivi': ordini_attivi,
                'login_oggi': login_oggi,
                'efficienza': efficienza,
                'ritardi': ritardi
            },
            'kpi_operai': kpi_operai
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/audit-log', methods=['GET'])
def get_admin_audit_log():
    """Recupera log di audit per admin dashboard"""
    try:
        requester_id = request.args.get('requester_id')
        if not _require_capo(requester_id):
            return jsonify({'success': False, 'error': 'Operazione riservata al Capo Officina'}), 403

        limit = min(request.args.get('limit', 100, type=int), 500)
        user_id = request.args.get('user_id', None)

        audit_logs = AuditManager.get_recent(limit=limit, user_id=user_id)

        return jsonify({
            'success': True,
            'audit_logs': audit_logs,
            'count': len(audit_logs)
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ============ API ARCHIVE ============

@app.route('/api/archive/orders', methods=['GET'])
def get_archive_orders():
    """Recupera ordini completati con paginazione e filtri"""
    try:
        # Parametri paginazione
        page = max(1, request.args.get('page', 1, type=int))
        limit = min(request.args.get('limit', 10, type=int), 100)
        ALLOWED_SORT = {'data_consegna', 'cliente', 'numero_ordine', 'status'}
        sort_by = request.args.get('sort_by', 'data_consegna')
        if sort_by not in ALLOWED_SORT:
            sort_by = 'data_consegna'
        sort_dir = request.args.get('sort_dir', 'desc')

        # Parametri filtri
        filters = {}
        if request.args.get('cliente'):
            filters['cliente'] = request.args.get('cliente')
        if request.args.get('operatore'):
            filters['operatore'] = request.args.get('operatore')
        if request.args.get('date_from'):
            filters['date_from'] = request.args.get('date_from')
        if request.args.get('date_to'):
            filters['date_to'] = request.args.get('date_to')

        result = ArchiveManager.get_completed_orders(
            filters=filters if filters else None,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir
        )

        return jsonify({
            'success': True,
            'data': result
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/archive/orders/<order_id>/details', methods=['GET'])
def get_archive_order_details(order_id):
    """Recupera dettagli completi di un ordine completato"""
    try:
        order_details = ArchiveManager.get_order_details(order_id)
        if not order_details:
            return jsonify({'success': False, 'error': 'Ordine non trovato'}), 404

        return jsonify({
            'success': True,
            'data': order_details
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/archive/export/csv', methods=['GET'])
def export_archive_csv():
    """Esporta ordini completati come CSV"""
    try:
        import csv
        import io

        # Parametri filtri
        filters = {}
        if request.args.get('cliente'):
            filters['cliente'] = request.args.get('cliente')
        if request.args.get('date_from'):
            filters['date_from'] = request.args.get('date_from')
        if request.args.get('date_to'):
            filters['date_to'] = request.args.get('date_to')

        csv_data = ArchiveManager.export_csv_data(
            filters=filters if filters else None
        )

        if not csv_data:
            return jsonify({'success': False, 'error': 'Nessun dato da esportare'}), 400

        # Crea buffer CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=csv_data[0].keys())
        writer.writeheader()
        writer.writerows(csv_data)

        # Converti in bytes
        csv_bytes = output.getvalue().encode('utf-8-sig')

        return csv_bytes, 200, {
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename=archivio-ordini.csv'
        }

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/archive/export/excel', methods=['GET'])
def export_archive_excel():
    """Esporta ordini completati come Excel (una riga per fase)"""
    try:
        import io
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        filters = {}
        if request.args.get('cliente'):
            filters['cliente'] = request.args.get('cliente')
        if request.args.get('operatore'):
            filters['operatore'] = request.args.get('operatore')
        if request.args.get('date_from'):
            filters['date_from'] = request.args.get('date_from')
        if request.args.get('date_to'):
            filters['date_to'] = request.args.get('date_to')

        rows, summary_indices = ArchiveManager.export_excel_data(filters=filters if filters else None)

        if not rows:
            return jsonify({'success': False, 'error': 'Nessun dato da esportare'}), 400

        wb = Workbook()
        ws = wb.active
        ws.title = "Archivio Ordini"

        headers = list(rows[0].keys())
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="1A7A48", end_color="1A7A48", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style='thin', color='CCCCCC'),
            right=Side(style='thin', color='CCCCCC'),
            top=Side(style='thin', color='CCCCCC'),
            bottom=Side(style='thin', color='CCCCCC')
        )

        # Stili riga riepilogo
        summary_font = Font(bold=True, size=11)
        summary_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
        summary_border = Border(
            left=Side(style='thin', color='CCCCCC'),
            right=Side(style='thin', color='CCCCCC'),
            top=Side(style='medium', color='1A7A48'),
            bottom=Side(style='medium', color='1A7A48')
        )

        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border

        # Set di indici riepilogo per lookup veloce
        summary_set = set(summary_indices)

        for row_idx, row_data in enumerate(rows, 2):
            is_summary = (row_idx - 2) in summary_set
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=row_data.get(header, ''))
                if is_summary:
                    cell.font = summary_font
                    cell.fill = summary_fill
                    cell.border = summary_border
                    cell.alignment = Alignment(vertical="center")
                else:
                    cell.border = thin_border
                    cell.alignment = Alignment(vertical="center")

        col_widths = {
            'Cliente': 22, 'Numero Ordine': 16, 'Data Caricamento': 18,
            'Data Completamento': 18, 'Fase': 14,
            'Operatore': 22, 'Ruolo': 12, 'Inizio': 18, 'Fine': 18,
            'Tempo Lavorato': 18, 'Sessioni': 10,
        }
        for col_idx, header in enumerate(headers, 1):
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = col_widths.get(header, 15)

        ws.auto_filter.ref = f"A1:{ws.cell(row=1, column=len(headers)).column_letter}{len(rows)+1}"

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return output.getvalue(), 200, {
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'Content-Disposition': 'attachment; filename=archivio-ordini.xlsx'
        }

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/archive/filters', methods=['GET'])
def get_archive_filters():
    """Ritorna liste per i filtri dell'archivio (clienti e operatori)"""
    try:
        clients = ArchiveManager.get_archive_clients()
        operators = ArchiveManager.get_archive_operators()
        return jsonify({
            'success': True,
            'clienti': clients,
            'operatori': operators
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ============ API FILE ============

@app.route('/api/extract-pdf-data', methods=['POST'])
def extract_pdf_data():
    """Carica un PDF e restituisce il filename salvato (no parsing)"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nessun file caricato'}), 400

        file = request.files['file']

        if file.filename == '' or not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Solo file PDF sono supportati'}), 400

        # Salva il file (no parsing)
        safe_name = os.path.basename(file.filename)
        pdf_filename = f"{uuid.uuid4()}_{safe_name}"
        filepath = os.path.join(PDFS_FOLDER, pdf_filename)
        file.save(filepath)

        return jsonify({
            'success': True,
            'data': {'pdf_filename': pdf_filename}
        }), 200

    except Exception as e:
        logging.error(f"[ERROR] extract_pdf_data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/upload-drawing', methods=['POST'])
def upload_drawing():
    """Carica un disegno DXF o immagine"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nessun file'}), 400
        
        file = request.files['file']
        order_id = request.form.get('order_id', 'unknown')

        from werkzeug.utils import secure_filename
        safe_name = secure_filename(file.filename)
        if not safe_name:
            return jsonify({'error': 'Nome file non valido'}), 400
        ALLOWED_EXTENSIONS = {'.dxf', '.dwg', '.png', '.jpg', '.jpeg', '.pdf', '.step', '.stp'}
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({'error': f'Tipo file non supportato: {ext}'}), 400
        filename = f"{order_id}_{safe_name}"
        filepath = os.path.join(DRAWINGS_FOLDER, filename)
        file.save(filepath)

        return jsonify({
            'success': True,
            'filename': filename
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ============ HEALTH CHECK ============

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'online', 'timestamp': datetime.utcnow().isoformat()}), 200

# ============ BACKUP & EXPORT ============

# Avvia backup scheduler all'import del modulo
try:
    _backup_sys_path = os.path.join(os.path.dirname(__file__), '..')
    if _backup_sys_path not in sys.path:
        sys.path.insert(0, _backup_sys_path)
    from backup_db import backup as _do_backup, integrity_check as _integrity_check
    from backup_db import load_config as _backup_load_config, save_config as _backup_save_config
    from backup_db import list_backups as _backup_list, start_scheduler as _start_backup_scheduler
    _start_backup_scheduler()
except Exception as _e:
    logging.warning(f'[BACKUP] Impossibile avviare scheduler: {_e}')

@app.route('/api/admin/backup', methods=['POST'])
def manual_backup():
    """Esegue un backup manuale del database (solo admin/capo)"""
    try:
        ok = _integrity_check()
        path = _do_backup(motivo='manuale')
        if path:
            return jsonify({'success': True, 'backup_path': os.path.basename(path), 'integrity_ok': ok}), 200
        return jsonify({'success': False, 'error': 'Backup fallito'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/backup/settings', methods=['GET', 'PUT'])
def backup_settings():
    """Leggi o aggiorna impostazioni backup"""
    try:
        if request.method == 'GET':
            config = _backup_load_config()
            return jsonify({'success': True, 'settings': config}), 200
        else:
            data = request.get_json() or {}
            config = _backup_load_config()
            if 'backup_enabled' in data:
                config['backup_enabled'] = bool(data['backup_enabled'])
            if 'interval_hours' in data:
                config['interval_hours'] = max(1, min(168, int(data['interval_hours'])))
            if 'max_backups' in data:
                config['max_backups'] = max(5, min(100, int(data['max_backups'])))
            if 'backup_path' in data:
                config['backup_path'] = str(data['backup_path']).strip()
            if 'remote_path' in data:
                config['remote_path'] = str(data['remote_path']).strip()
            _backup_save_config(config)
            return jsonify({'success': True, 'settings': config}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/backup/list', methods=['GET'])
def backup_list():
    """Lista dei backup esistenti"""
    try:
        backups = _backup_list()
        return jsonify({'success': True, 'backups': backups, 'count': len(backups)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/audit', methods=['GET'])
def get_audit_log():
    """Recupera log attività recenti"""
    try:
        limit = min(request.args.get('limit', 100, type=int), 500)
        user_id = request.args.get('user_id')
        logs = AuditManager.get_recent(limit=limit, user_id=user_id)
        return jsonify({'success': True, 'logs': logs}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/export-json', methods=['GET'])
def export_json():
    """Esporta tutti gli ordini attivi in formato JSON (download)"""
    try:
        import json, io
        orders = OrderManager.get_all_orders_dict()
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        payload = json.dumps(orders, ensure_ascii=False, indent=2, default=str).encode('utf-8')
        buf = io.BytesIO(payload)
        buf.seek(0)
        return send_file(
            buf,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'ordini_{ts}.json'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ NOTIFICATION SYSTEM (WhatsApp-like) ============

@app.route('/api/notifications', methods=['GET', 'POST'])
def handle_notifications():
    """GET: Recupera notifiche | POST: Crea notifica"""
    if request.method == 'GET':
        try:
            user_id = request.args.get('user_id')
            limit = request.args.get('limit', 50, type=int)

            if not user_id:
                return jsonify({'success': False, 'error': 'user_id obbligatorio'}), 400

            notifications = NotificationManager.get_notifications(user_id, limit=limit)
            unread_count = NotificationManager.get_unread_count(user_id)

            return jsonify({
                'success': True,
                'data': {
                    'notifications': notifications,
                    'unread_count': unread_count,
                    'total': len(notifications)
                }
            }), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    elif request.method == 'POST':
        try:
            data = request.get_json() or {}
            sender_id = data.get('sender_id')
            if not sender_id or not UserManager.get_user(sender_id):
                return jsonify({'success': False, 'error': 'sender_id obbligatorio e deve essere un utente valido'}), 403

            user_id = data.get('user_id')
            order_id = data.get('order_id')
            title = data.get('title', 'Notifica')
            message = data.get('message', '')
            notification_type = data.get('notification_type', 'order')
            notification_category = data.get('notification_category', 'informativa')

            if not user_id or not title:
                return jsonify({'success': False, 'error': 'user_id e title obbligatori'}), 400

            notification = NotificationManager.create_notification(
                user_id=user_id,
                order_id=order_id,
                title=title,
                message=message,
                notification_type=notification_type,
                notification_category=notification_category
            )

            if notification:
                return jsonify({
                    'success': True,
                    'data': notification
                }), 201
            else:
                return jsonify({'success': False, 'error': 'Failed to create notification'}), 400
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/notifications/<notification_id>/read', methods=['PUT'])
def mark_notification_read(notification_id):
    """Segna una notifica come letta"""
    try:
        success = NotificationManager.mark_as_read(notification_id)
        return jsonify({'success': success}), 200 if success else 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/notifications/<notification_id>', methods=['DELETE'])
def delete_notification(notification_id):
    """Cancella una singola notifica (soft delete)"""
    try:
        success = NotificationManager.delete_notification(notification_id)

        if success:
            return jsonify({'success': True, 'message': 'Notifica cancellata'}), 200
        else:
            return jsonify({'success': False, 'error': 'Notifica non trovata'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/notifications/clear-all', methods=['DELETE'])
def clear_all_notifications():
    """Cancella tutte le notifiche dell'utente"""
    try:
        user_id = request.args.get('user_id')

        if not user_id:
            return jsonify({'success': False, 'error': 'user_id obbligatorio'}), 400

        success = NotificationManager.delete_all_notifications(user_id)

        if success:
            return jsonify({'success': True, 'message': 'Tutte le notifiche cancellate'}), 200
        else:
            return jsonify({'success': False, 'error': 'Errore durante la cancellazione'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ============ DELEGHE FASE ============

@app.route('/api/delegations', methods=['POST'])
def create_delegation():
    """Crea una nuova delega di fase"""
    try:
        data = request.json
        required = ['order_id', 'fase', 'operatore_principale', 'operatore_delegato', 'delegata_da']
        for field in required:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} obbligatorio'}), 400

        result = DelegationManager.create_delegation(
            order_id=data['order_id'],
            fase=data['fase'],
            op_principale=data['operatore_principale'],
            op_delegato=data['operatore_delegato'],
            delegata_da=data['delegata_da'],
            forzata=data.get('forzata', False),
            note=data.get('note', '')
        )
        status = 201 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/delegations/<delegation_id>/accept', methods=['POST'])
def accept_delegation(delegation_id):
    """Accetta una delega"""
    try:
        data = request.json
        operatore_id = data.get('operatore_id')
        if not operatore_id:
            return jsonify({'success': False, 'error': 'operatore_id obbligatorio'}), 400
        result = DelegationManager.accept_delegation(delegation_id, operatore_id)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/delegations/<delegation_id>/reject', methods=['POST'])
def reject_delegation(delegation_id):
    """Rifiuta una delega"""
    try:
        data = request.json
        operatore_id = data.get('operatore_id')
        if not operatore_id:
            return jsonify({'success': False, 'error': 'operatore_id obbligatorio'}), 400
        result = DelegationManager.reject_delegation(delegation_id, operatore_id)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/delegations/<delegation_id>/start', methods=['POST'])
def start_delegated_phase(delegation_id):
    """Inizia la fase delegata"""
    try:
        data = request.json
        operatore_id = data.get('operatore_id')
        if not operatore_id:
            return jsonify({'success': False, 'error': 'operatore_id obbligatorio'}), 400
        result = DelegationManager.start_delegated_phase(delegation_id, operatore_id)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/delegations/<delegation_id>/complete', methods=['POST'])
def complete_delegated_phase(delegation_id):
    """Completa la fase delegata"""
    try:
        data = request.json
        operatore_id = data.get('operatore_id')
        if not operatore_id:
            return jsonify({'success': False, 'error': 'operatore_id obbligatorio'}), 400
        result = DelegationManager.complete_delegated_phase(
            delegation_id, operatore_id, note=data.get('note', '')
        )
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/delegations/<delegation_id>/save-partial', methods=['POST'])
def save_partial_delegated(delegation_id):
    """Salva parziale su fase delegata"""
    try:
        data = request.json
        operatore_id = data.get('operatore_id')
        if not operatore_id:
            return jsonify({'success': False, 'error': 'operatore_id obbligatorio'}), 400
        result = DelegationManager.save_partial_delegated_phase(
            delegation_id, operatore_id, note=data.get('note', '')
        )
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/delegations/<delegation_id>/resume', methods=['POST'])
def resume_delegated_phase_endpoint(delegation_id):
    """Riprende una fase delegata in pausa"""
    try:
        data = request.json
        operatore_id = data.get('operatore_id')
        if not operatore_id:
            return jsonify({'success': False, 'error': 'operatore_id obbligatorio'}), 400
        result = DelegationManager.resume_delegated_phase(delegation_id, operatore_id)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/delegations/<delegation_id>/revoke', methods=['POST'])
def revoke_delegation(delegation_id):
    """Revoca una delega (solo capo o op_principale)"""
    try:
        data = request.json
        revocata_da = data.get('revocata_da')
        if not revocata_da:
            return jsonify({'success': False, 'error': 'revocata_da obbligatorio'}), 400
        result = DelegationManager.revoke_delegation(delegation_id, revocata_da)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/delegations', methods=['GET'])
def get_delegations():
    """Recupera deleghe con filtri opzionali"""
    try:
        order_id = request.args.get('order_id')
        op_principale = request.args.get('op_principale')
        op_delegato = request.args.get('op_delegato')
        stato = request.args.get('stato')

        # Se richieste tutte le attive (per capo)
        if request.args.get('active_only') == 'true':
            delegations = DelegationManager.get_all_active_delegations()
        else:
            delegations = DelegationManager.get_delegations(
                order_id=order_id,
                op_principale=op_principale,
                op_delegato=op_delegato,
                stato=stato
            )
        return jsonify({'success': True, 'delegations': delegations}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ============ API SUPPORTO ============

@app.route('/api/support-requests', methods=['POST'])
def create_support_request():
    """Crea una richiesta di supporto per un ordine"""
    try:
        data = request.get_json() or {}
        order_id = data.get('order_id')
        op_principale = data.get('operatore_principale')
        op_supporto = data.get('operatore_supporto')
        forzata = data.get('forzata', False)
        note = data.get('note', '')

        if not order_id or not op_principale or not op_supporto:
            return jsonify({'success': False, 'error': 'order_id, operatore_principale e operatore_supporto obbligatori'}), 400

        result = SupportManager.create_support_request(
            order_id=order_id, op_principale=op_principale,
            op_supporto=op_supporto, forzata=forzata, note=note
        )

        if result.get('success'):
            # Audit log
            principale = UserManager.get_user(op_principale)
            supporto = UserManager.get_user(op_supporto)
            nome_p = principale.get('name') if principale else op_principale
            nome_s = supporto.get('name') if supporto else op_supporto
            AuditManager.log(
                user_id=op_principale,
                user_name=nome_p,
                action='CREATE_SUPPORT',
                entity_type='order',
                entity_id=order_id,
                detail=f"Richiesta supporto a {nome_s}" + (" (forzata)" if forzata else ""),
                ip_address=request.remote_addr
            )

        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/support-requests/<request_id>/accept', methods=['POST'])
def accept_support_request(request_id):
    """Accetta una richiesta di supporto"""
    try:
        data = request.get_json() or {}
        operatore_id = data.get('operatore_id')
        if not operatore_id:
            return jsonify({'success': False, 'error': 'operatore_id obbligatorio'}), 400

        result = SupportManager.accept_support_request(request_id, operatore_id)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/support-requests/<request_id>/reject', methods=['POST'])
def reject_support_request(request_id):
    """Rifiuta una richiesta di supporto"""
    try:
        data = request.get_json() or {}
        operatore_id = data.get('operatore_id')
        if not operatore_id:
            return jsonify({'success': False, 'error': 'operatore_id obbligatorio'}), 400

        result = SupportManager.reject_support_request(request_id, operatore_id)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/support-requests/<request_id>/revoke', methods=['POST'])
def revoke_support_request(request_id):
    """Revoca una richiesta di supporto"""
    try:
        result = SupportManager.revoke_support_request(request_id)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/support-requests', methods=['GET'])
def get_support_requests():
    """Recupera richieste di supporto con filtri"""
    try:
        order_id = request.args.get('order_id')
        op_principale = request.args.get('op_principale')
        op_supporto = request.args.get('op_supporto')
        stato = request.args.get('stato')
        active_only = request.args.get('active_only') == 'true'

        requests_data = SupportManager.get_support_requests(
            order_id=order_id, op_principale=op_principale,
            op_supporto=op_supporto, stato=stato, active_only=active_only
        )
        return jsonify({'success': True, 'data': requests_data}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

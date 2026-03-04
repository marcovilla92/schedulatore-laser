"""Flask Backend per Schedulatore Laser"""
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import sys
import uuid
from pathlib import Path

# Importa moduli locali
from .models import initialize_database, Order, OrderFile, get_session
from .database import OrderManager, UserManager, AuditManager, ArchiveManager, NotificationManager, OperatorClientManager, AlertManager, KPIManager

app = Flask(__name__, static_folder=None)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max upload
CORS(app)

# Configurazioni
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads')
DRAWINGS_FOLDER = os.path.join(UPLOAD_FOLDER, 'drawings')
PDFS_FOLDER = os.path.join(UPLOAD_FOLDER, 'pdfs')
FRONTEND_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'frontend')

os.makedirs(DRAWINGS_FOLDER, exist_ok=True)
os.makedirs(PDFS_FOLDER, exist_ok=True)

# Inizializza database
initialize_database()

# ============ UTILITÀ ESTRAZIONE PDF MINIMALE ============

def extract_minimal_from_pdf(filepath: str) -> dict:
    """
    Estrae SOLO cliente e data consegna da un PDF usando regex semplici.
    Questo sostituisce i 7 parser precedenti (2000+ righe di codice).

    Returns:
        {
            "cliente": str | None,
            "data_consegna": str (formato YYYY-MM-DD) | None,
            "pdf_filename": str,
            "estrattore": "minimal"
        }
    """
    import PyPDF2
    import re

    try:
        text = ""
        try:
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += (page.extract_text() or "") + "\n"
        except Exception as _pdf_err:
            print(f"[WARN] Errore PyPDF2: {_pdf_err}, tentando fallback...")
            text = ""

        # Estrae CLIENTE con pattern flessibile
        cliente = None
        patterns_cliente = [
            r'(?:cliente|spett\.?le|destinatario)[:\s]+([A-Z][^\n]{3,80})',
            r'^([A-Z][A-Z\s\.\,&-]{3,80}?)(?:\n|s\.r\.l|spa|srl)',
        ]
        for pattern in patterns_cliente:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                cliente = match.group(1).strip()
                break

        # Estrae DATA CONSEGNA
        data_consegna = None
        patterns_data = [
            r'(?:consegna|delivery|scadenza|data\s+consegna)[^\d]*(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})',
            r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})',
        ]

        for pattern in patterns_data:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if len(match.groups()) >= 3:
                        day, month, year = match.groups()
                        year = int(year)
                        if year < 100:
                            year += 2000
                        from datetime import datetime
                        dt = datetime(year, int(month), int(day))
                        data_consegna = dt.strftime("%Y-%m-%d")
                        break
                except (ValueError, IndexError):
                    continue

        pdf_filename = os.path.basename(filepath)

        return {
            "cliente": cliente,
            "data_consegna": data_consegna,
            "pdf_filename": pdf_filename,
            "estrattore": "minimal"
        }

    except Exception as e:
        print(f"[ERROR] extract_minimal_from_pdf: {e}")
        return {
            "cliente": None,
            "data_consegna": None,
            "pdf_filename": os.path.basename(filepath),
            "estrattore": "minimal",
            "error": str(e)
        }

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
    """Recupera lista utenti attivi"""
    try:
        users = UserManager.get_all_users()
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
        success = UserManager.delete_user(user_id)
        if not success:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        return jsonify({'success': True, 'message': f'User {user_id} deleted'}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ============ API ORDINI ============

@app.route('/api/orders', methods=['POST'])
def create_order():
    """Crea un nuovo ordine con routing dinamico"""
    try:
        data = request.get_json()

        order = OrderManager.create_order(
            cliente=data.get('cliente'),
            data_consegna=data.get('data_consegna'),
            destinazione=data.get('destinazione', 'LASER'),
            numero_ordine=data.get('numero_ordine'),
            prezzo_quotato=data.get('prezzo_quotato'),
            note=data.get('note', '')
        )

        # Registra i file (PDF e DXF) nel DB
        session = get_session()
        try:
            pdf_filename = data.get('pdf_filename')
            if pdf_filename:
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

            dxf_filenames = data.get('dxf_filenames', [])
            drawings_folder = os.path.join(os.path.dirname(__file__), '..', 'uploads', 'drawings')
            for dxf_filename in dxf_filenames:
                dxf_path = os.path.join(drawings_folder, dxf_filename)
                if os.path.exists(dxf_path):
                    file_record = OrderFile(
                        id=str(uuid.uuid4()),
                        order_id=order.id,
                        filename=dxf_filename,
                        filepath=dxf_path,
                        file_type='DXF'
                    )
                    session.add(file_record)

            session.commit()
        finally:
            session.close()

        # Notifica capo officina + impiegata
        NotificationManager.create_notification(
            user_id='marco-capo',
            order_id=order.id,
            title='Nuovo ordine',
            message=f'Ordine {order.cliente} inviato a {data.get("destinazione", "LASER")}',
            notification_type='order'
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
        print(f"[ERROR] Create order error: {e}")
        import traceback
        traceback.print_exc()
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
        print(f"[ERROR] get_order_pdf: {e}")
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
        print(f"[ERROR] Get DXF file error: {e}")
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
        fase_successiva = data.get('fase_successiva')  # PIEGA, SALDATURA, PULIZIA, LASER, COMPLETATO
        completamento_parziale = data.get('completamento_parziale', False)
        operatore_id = data.get('operatore_id')

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

            # Notifica se ordine completato o parziale
            if result.get('all_completed') or completamento_parziale:
                status_text = "completato" if result.get('all_completed') else "parziale"
                details = OrderManager.get_order_details(order_id)
                NotificationManager.create_notification(
                    user_id='giulia-impiegata',
                    order_id=order_id,
                    title=f'Ordine {status_text}',
                    message=f'Ordine {details.get("cliente", "")} - {status_text}',
                    notification_type='completion'
                )
                NotificationManager.create_notification(
                    user_id='marco-capo',
                    order_id=order_id,
                    title=f'Ordine {status_text}',
                    message=f'Ordine {details.get("cliente", "")} - {status_text}',
                    notification_type='completion'
                )

            details = OrderManager.get_order_details(order_id)
            return jsonify({
                'success': True,
                'phase': phase,
                'fase_successiva': fase_successiva,
                'order_details': details
            }), 200

        return jsonify(result), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/phase/<phase>/orders', methods=['GET'])
def get_orders_by_phase(phase):
    """Recupera ordini per fase corrente"""
    try:
        operatore_id = request.args.get('operatore')
        orders = OrderManager.get_orders_by_phase(phase, operatore_id)

        result = []
        for order in orders:
            details = OrderManager.get_order_details(order.id)
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

        if not new_operator_id:
            return jsonify({'success': False, 'error': 'new_operator_id obbligatorio'}), 400

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

        if not step_id:
            return jsonify({'success': False, 'error': 'step_id obbligatorio'}), 400

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

        if not new_phase:
            return jsonify({'success': False, 'error': 'new_phase obbligatorio'}), 400

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
        limit = request.args.get('limit', 100, type=int)
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
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        sort_by = request.args.get('sort_by', 'data_consegna')
        sort_dir = request.args.get('sort_dir', 'desc')

        # Parametri filtri
        filters = {}
        if request.args.get('cliente'):
            filters['cliente'] = request.args.get('cliente')
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

# ============ API FILE ============

@app.route('/api/extract-pdf-data', methods=['POST'])
def extract_pdf_data():
    """Estrae SOLO cliente e data consegna dal PDF caricato (parsing minimale)"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nessun file caricato'}), 400

        file = request.files['file']

        if file.filename == '' or not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Solo file PDF sono supportati'}), 400

        # Salva il file
        pdf_filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(PDFS_FOLDER, pdf_filename)
        file.save(filepath)

        # Estrai SOLO cliente + data consegna (parsing minimale)
        pdf_data = extract_minimal_from_pdf(filepath)

        return jsonify({
            'success': True,
            'data': pdf_data
        }), 200

    except Exception as e:
        print(f"[ERROR] extract_pdf_data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/upload-drawing', methods=['POST'])
def upload_drawing():
    """Carica un disegno DXF o immagine"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nessun file'}), 400
        
        file = request.files['file']
        order_id = request.form.get('order_id', 'unknown')
        
        filename = f"{order_id}_{file.filename}"
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
            user_id = data.get('user_id')
            order_id = data.get('order_id')
            title = data.get('title', 'Notifica')
            message = data.get('message', '')
            notification_type = data.get('notification_type', 'order')

            if not user_id or not title:
                return jsonify({'success': False, 'error': 'user_id e title obbligatori'}), 400

            notification = NotificationManager.create_notification(
                user_id=user_id,
                order_id=order_id,
                title=title,
                message=message,
                notification_type=notification_type
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

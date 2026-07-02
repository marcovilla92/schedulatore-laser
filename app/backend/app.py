"""Flask Backend per Schedulatore Laser"""
from flask import Flask, request, jsonify, send_file, send_from_directory, redirect
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import sys
import uuid
import logging

logger = logging.getLogger(__name__)

# Importa moduli locali
from .models import initialize_database, Order, OrderFile, get_session
from .database import OrderManager, UserManager, AuditManager, ArchiveManager, FatturazioneManager, NotificationManager, AlertManager, KPIManager, BarcodeManager, PreventivoManager
from .pdf_cartellino import genera_cartellino_pdf
from .events import OrderEventBus
from .preventivi import (
    xlsx_importer as _xlsx_importer,
    dxf_scanner as _dxf_scanner,
    laser_cost_estimator as _laser_estimator,
    step_assieme as _step_assieme,
    step_tubolari as _step_tubolari,
    step_piastre as _step_piastre,
    pdf_exporter as _pdf_exporter,
)
import json as _json_mod
# Carica DB profili tubolari una volta (file copiato dal Preventivatore desktop)
_PROFILI_TUBOLARI_DB = {}
try:
    _profili_path = os.path.join(os.path.dirname(__file__), 'preventivi', 'profili_tubolari.json')
    if os.path.exists(_profili_path):
        with open(_profili_path, 'r', encoding='utf-8') as _f:
            _PROFILI_TUBOLARI_DB = _json_mod.load(_f)
except Exception as _e:
    logger.warning('profili_tubolari.json non caricato: %s', _e)


def _find_oda_converter():
    """Cerca ODA File Converter installato sul sistema. Ritorna path .exe o None.
    Strategia: env var ODA_FC_PATH > glob su Program Files (versione qualsiasi).
    """
    import glob
    custom = os.environ.get('ODA_FC_PATH')
    if custom and os.path.exists(custom):
        return custom
    candidates = []
    for base in (r'C:\Program Files\ODA', r'C:\Program Files (x86)\ODA'):
        if os.path.isdir(base):
            candidates += glob.glob(os.path.join(base, 'ODAFileConverter*', 'ODAFileConverter.exe'))
    return candidates[-1] if candidates else None


def _convert_dwg_to_dxf(dwg_path):
    """Converte un .dwg in .dxf usando ODA File Converter (subprocess).

    Ritorna path del .dxf convertito, oppure dict {'error': ...} se conversione
    impossibile (ODA non installato, timeout, file corrotto).
    """
    import subprocess
    import shutil
    import tempfile
    import glob

    oda = _find_oda_converter()
    if not oda:
        return {'error': 'ODA_NOT_INSTALLED'}

    tmp_in = tempfile.mkdtemp(prefix='dwg_in_')
    tmp_out = tempfile.mkdtemp(prefix='dwg_out_')
    try:
        # ODA processa intere cartelle, non file singoli
        in_path = os.path.join(tmp_in, os.path.basename(dwg_path))
        shutil.copy2(dwg_path, in_path)
        # CLI: <input_dir> <output_dir> <out_ver> <out_format> <recurse> <audit>
        cmd = [oda, tmp_in, tmp_out, 'ACAD2018', 'DXF', '0', '1']
        proc = subprocess.run(cmd, capture_output=True, timeout=90)
        if proc.returncode != 0:
            return {'error': 'CONVERTER_FAILED', 'detail': proc.stderr.decode('utf-8', errors='ignore')[:200]}
        out_files = glob.glob(os.path.join(tmp_out, '*.dxf'))
        if not out_files:
            return {'error': 'NO_OUTPUT', 'detail': 'ODA non ha prodotto DXF'}
        # Sposta il DXF in un path che non scompare al cleanup di tmp_out
        out_path = os.path.join(UPLOAD_FOLDER, 'tmp_conv_' + uuid.uuid4().hex + '.dxf')
        shutil.copy2(out_files[0], out_path)
        return out_path
    except subprocess.TimeoutExpired:
        return {'error': 'TIMEOUT'}
    except Exception as e:
        return {'error': 'EXCEPTION', 'detail': str(e)}
    finally:
        shutil.rmtree(tmp_in, ignore_errors=True)
        shutil.rmtree(tmp_out, ignore_errors=True)

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


def _require_role(user_id: str, roles: list) -> bool:
    """Verifica che user_id abbia uno dei ruoli specificati.

    `roles` accetta: ruoli espliciti ('Commerciale', 'Admin', 'Impiegata',
    'Capo Officina', 'Operaio Laser', 'Operaio Officina', 'Amministratore')
    o l'alias virtuale 'CAPO' che include is_capo=True OR role='Amministratore'.

    Usato dagli endpoint preventivi per autorizzare Commerciale, Admin, Capi.
    """
    if not user_id:
        return False
    user = UserManager.get_user(user_id)
    if not user or not user.get('is_active', True):
        return False
    user_role = user.get('role', '')
    for r in roles:
        if r == 'CAPO' and (user.get('is_capo') or user_role == 'Amministratore'):
            return True
        if r == user_role:
            return True
    return False

# ============ FRONTEND ROUTES ============

@app.route('/')
def index():
    """Serve login page"""
    return send_from_directory(FRONTEND_FOLDER, 'login.html')

@app.route('/download-cert')
def download_cert():
    """Scarica il certificato SSL per installazione su tablet Android."""
    cert_dir = os.path.join(os.path.dirname(__file__), '..', 'certs')
    cert_path = os.path.join(cert_dir, 'cert.pem')
    if os.path.exists(cert_path):
        return send_file(cert_path, as_attachment=True, download_name='ferrotrack-cert.crt',
                        mimetype='application/x-x509-ca-cert')
    return jsonify({'error': 'Certificato non trovato'}), 404

# Pagine legacy rimosse — redirect verso le nuove
_LEGACY_REDIRECTS = {
    'officina.html': '/capo-officina.html',
    'laser-v2.html': '/capo-officina.html',
    'approva-ordine.html': '/capo-officina.html',
    'dettaglio-ordine.html': '/capo-officina.html',
}


@app.route('/<path:filename>')
def serve_frontend(filename):
    """Serve frontend files. Redirect su pagine legacy demolite."""
    if filename in _LEGACY_REDIRECTS:
        return redirect(_LEGACY_REDIRECTS[filename], code=302)
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
            'is_capo': user.get('is_capo', False),
            'assigned_clients': user.get('assigned_clients', [])
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

        # Notifica a tutti i capi officina ("Nuovo ordine")
        numero_display = order.numero_ordine or order.id[:8]
        try:
            for u in UserManager.get_all_users() or []:
                if u.get('is_capo') and u.get('is_active', True):
                    NotificationManager.create_notification(
                        user_id=u['id'],
                        order_id=order.id,
                        title='Nuovo ordine',
                        message=f'Ordine #{numero_display} ({order.cliente})',
                        notification_type='order',
                        notification_category='informativa'
                    )
        except Exception as exc:
            logger.warning('notifica nuovo ordine ai capi fallita: %s', exc)

        return jsonify({
            'success': True,
            'order_id': order.id,
            'cliente': order.cliente,
            'data_consegna': order.data_consegna.isoformat(),
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


@app.route('/api/orders/<order_id>/mark-laser-done', methods=['POST'])
def mark_laser_done(order_id):
    """Marca il taglio laser come completato — chiama il LASER (Mirko).
    Da questo momento gli operai officina possono scansionare il cartellino.
    """
    try:
        data = request.get_json(silent=True) or {}
        user_id = (data.get('user_id') or '').strip()
        if not user_id:
            return jsonify({'error': 'user_id obbligatorio'}), 400
        user = UserManager.get_user(user_id)
        if not user:
            return jsonify({'error': 'utente non trovato'}), 403
        # Solo ruolo Laser (o capo) può marcare il taglio completato
        is_laser = (user.get('role') == 'Operaio Laser') or user.get('is_capo')
        if not is_laser:
            return jsonify({'error': 'Solo operatore Laser o capo può marcare il taglio'}), 403
        result = OrderManager.mark_laser_done(order_id, user_id=user_id)
        return jsonify(result), (200 if result.get('success') else 400)
    except Exception as e:
        logger.exception('mark_laser_done endpoint failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/orders/<order_id>/mark-laser-undone', methods=['POST'])
def mark_laser_undone(order_id):
    """Rollback marcatura taglio completato (errore, va re-tagliato)."""
    try:
        data = request.get_json(silent=True) or {}
        user_id = (data.get('user_id') or '').strip()
        if not user_id:
            return jsonify({'error': 'user_id obbligatorio'}), 400
        user = UserManager.get_user(user_id)
        if not user:
            return jsonify({'error': 'utente non trovato'}), 403
        is_laser = (user.get('role') == 'Operaio Laser') or user.get('is_capo')
        if not is_laser:
            return jsonify({'error': 'Solo operatore Laser o capo può annullare il taglio'}), 403
        result = OrderManager.mark_laser_undone(order_id, user_id=user_id)
        return jsonify(result), (200 if result.get('success') else 400)
    except Exception as e:
        logger.exception('mark_laser_undone endpoint failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/orders/<order_id>/close', methods=['POST'])
def close_order(order_id):
    """Marca un ordine come 'lavoro finito' → status=DA_FATTURARE.

    Permesso: capi officina E impiegata (Elena fa da backup quando i capi
    si dimenticano o accumulano).
    """
    try:
        data = request.get_json(silent=True) or {}
        user_id = (data.get('user_id') or '').strip()
        if not user_id:
            return jsonify({'error': 'user_id obbligatorio'}), 400
        user = UserManager.get_user(user_id)
        if not user:
            return jsonify({'error': 'utente non trovato'}), 403
        is_allowed = user.get('is_capo') or (user.get('role') in ('Impiegata', 'Capo Officina', 'Amministratore'))
        if not is_allowed:
            return jsonify({'error': 'Permesso negato'}), 403
        result = OrderManager.close_order(order_id, user_id=user_id)
        return jsonify(result), (200 if result.get('success') else 400)
    except Exception as e:
        logger.exception('close_order endpoint failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/orders/sospetti-finiti', methods=['GET'])
def api_ordini_sospetti_finiti():
    """Ordini che probabilmente sono finiti ma nessuno li ha chiusi.

    Usato da Elena (sezione dedicata) e dal Pannello Capo (badge rosso).
    Soglie configurabili via /api/admin/config.
    """
    try:
        items = BarcodeManager.get_ordini_sospetti_finiti()
        return jsonify({
            'success': True,
            'count': len(items),
            'orders': items,
            'config': BarcodeManager.load_config(),
        }), 200
    except Exception as e:
        logger.exception('sospetti-finiti endpoint failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/config', methods=['GET'])
def api_admin_config_get():
    """Config app (soglie sospetto, ecc.). Lettura aperta."""
    try:
        return jsonify({'success': True, 'config': BarcodeManager.load_config()}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/config', methods=['PUT'])
def api_admin_config_update():
    """Modifica config app (solo capi/admin)."""
    try:
        data = request.get_json(silent=True) or {}
        user_id = (data.get('admin_id') or '').strip()
        if not _require_capo(user_id):
            return jsonify({'error': 'Permesso negato'}), 403
        updates = {k: v for k, v in data.items() if k != 'admin_id'}
        new_cfg = BarcodeManager.save_config(updates)
        if 'error' in new_cfg:
            return jsonify({'success': False, 'error': new_cfg['error']}), 500
        try:
            AuditManager.log(
                user_id=user_id, action='UPDATE_CONFIG',
                entity_type='config', entity_id='app_config',
                detail=str(updates),
            )
        except Exception:
            pass
        return jsonify({'success': True, 'config': new_cfg}), 200
    except Exception as e:
        logger.exception('config update failed')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders/<order_id>/replace-pdf', methods=['POST'])
def replace_order_pdf(order_id):
    """Sostituisce il PDF di un ordine esistente"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'Nessun file inviato'}), 400
        file = request.files['file']
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            return jsonify({'success': False, 'error': 'Il file deve essere un PDF'}), 400

        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return jsonify({'success': False, 'error': 'Ordine non trovato'}), 404

            # Salva il nuovo file
            pdf_filename = f"{order_id}_{os.path.basename(file.filename)}"
            pdf_path = os.path.join(PDFS_FOLDER, pdf_filename)
            file.save(pdf_path)

            # Aggiorna o crea il record file
            existing_pdf = session.query(OrderFile).filter(
                OrderFile.order_id == order_id,
                OrderFile.file_type == 'PDF'
            ).first()
            if existing_pdf:
                existing_pdf.filename = pdf_filename
                existing_pdf.filepath = pdf_path
            else:
                new_file = OrderFile(
                    id=str(uuid.uuid4()),
                    order_id=order_id,
                    filename=pdf_filename,
                    filepath=pdf_path,
                    file_type='PDF'
                )
                session.add(new_file)

            session.commit()
            return jsonify({'success': True, 'filename': pdf_filename}), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"replace_order_pdf: {e}")
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

# ============ API MARK ORDER SEEN ============

@app.route('/api/orders/<order_id>/mark-seen', methods=['POST'])
def mark_order_seen(order_id):
    """Marca un ordine come visto dall'operatore"""
    try:
        result = OrderManager.mark_order_seen(order_id)
        return jsonify(result), 200 if result.get('success') else 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
        from datetime import datetime as dt, timedelta

        all_orders = OrderManager.get_all_orders_dict()
        active_orders = [o for o in all_orders if o.get('status') not in ('COMPLETATO', 'PARZIALE', 'SPEDITO')]
        ordini_attivi = len(active_orders)

        # KPI operai (calcoli reali, nessun mock)
        kpi_operai = AuditManager.get_kpi_operai()

        # Login oggi
        today = dt.now().date()
        audit_logs = AuditManager.get_recent(limit=1000)
        login_oggi = len([
            log for log in audit_logs
            if log['action'] == 'LOGIN' and dt.fromisoformat(log['timestamp']).date() == today
        ])

        # Efficienza: per ordini COMPLETATI, verifica se ultimo step <= data_consegna
        # Usa il KPI dashboard che ha gia' il calcolo corretto
        kpi_dashboard = KPIManager.get_dashboard_kpi()
        efficienza = kpi_dashboard.get('riepilogo', {}).get('efficienza_puntualita', 0) if kpi_dashboard.get('success') else 0

        # Ritardi: ordini scaduti non completati
        ritardi = sum(1 for o in active_orders if o.get('data_consegna') and dt.fromisoformat(o['data_consegna']).date() < today)

        # Completati oggi (dal KPI dashboard)
        completati_oggi = kpi_dashboard.get('riepilogo', {}).get('completati_oggi', 0) if kpi_dashboard.get('success') else 0

        # Operai online
        operai_online = sum(1 for op in kpi_operai if op.get('saturazione', 0) > 0 or
            (op.get('ultimo_accesso') and op['ultimo_accesso'] != 'Mai' and
             dt.fromisoformat(op['ultimo_accesso']).date() == today))

        return jsonify({
            'success': True,
            'kpi_globali': {
                'ordini_attivi': ordini_attivi,
                'login_oggi': login_oggi,
                'efficienza': efficienza,
                'ritardi': ritardi,
                'completati_oggi': completati_oggi,
                'operai_online': operai_online,
                'totale_operai': len(kpi_operai)
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

# ============ API FATTURAZIONE (Chiusura Amministrativa) ============

@app.route('/api/ordini-da-fatturare', methods=['GET'])
def get_ordini_da_fatturare():
    """Recupera ordini in attesa di chiusura amministrativa"""
    try:
        page = max(1, request.args.get('page', 1, type=int))
        limit = min(request.args.get('limit', 20, type=int), 100)
        sort_by = request.args.get('sort_by', 'data_consegna')
        sort_dir = request.args.get('sort_dir', 'asc')

        filters = {}
        if request.args.get('cliente'):
            filters['cliente'] = request.args.get('cliente')
        if request.args.get('numero_ordine'):
            filters['numero_ordine'] = request.args.get('numero_ordine')
        if request.args.get('date_from'):
            filters['date_from'] = request.args.get('date_from')
        if request.args.get('date_to'):
            filters['date_to'] = request.args.get('date_to')

        result = FatturazioneManager.get_ordini_da_fatturare(
            filters=filters if filters else None,
            page=page, limit=limit,
            sort_by=sort_by, sort_dir=sort_dir
        )

        return jsonify({'success': True, 'data': result}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/ordini-da-fatturare/count', methods=['GET'])
def get_ordini_da_fatturare_count():
    """Conteggio ordini da fatturare (per badge)"""
    try:
        count = FatturazioneManager.get_count()
        return jsonify({'success': True, 'count': count}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/orders/<order_id>/salva-bozza-fattura', methods=['PUT'])
def salva_bozza_fattura(order_id):
    """Salva dati DDT/fattura come bozza senza chiudere l'ordine"""
    try:
        data = request.get_json() or {}
        result = FatturazioneManager.salva_bozza(order_id, data)
        if not result['success']:
            return jsonify(result), 400
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/orders/<order_id>/chiudi-amministrativo', methods=['POST'])
def chiudi_ordine_amministrativo(order_id):
    """Chiude ordine amministrativamente — status → CHIUSO"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', '')
        result = FatturazioneManager.chiudi_ordine(order_id, data, user_id)
        if not result['success']:
            return jsonify(result), 400

        # Log audit
        AuditManager.log(
            user_id=user_id,
            action='CHIUSURA_AMMINISTRATIVA',
            entity_type='order',
            entity_id=order_id,
            detail=f"DDT: {data.get('numero_ddt', '-')}, Fattura: {data.get('numero_fattura', '-')}",
            ip_address=request.remote_addr
        )

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/orders/<order_id>/riapri', methods=['POST'])
def riapri_ordine(order_id):
    """Riapre ordine CHIUSO riportandolo a DA_FATTURARE"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', '')
        result = FatturazioneManager.riapri_ordine(order_id)
        if not result['success']:
            return jsonify(result), 400

        AuditManager.log(
            user_id=user_id,
            action='RIAPERTURA_ORDINE',
            entity_type='order',
            entity_id=order_id,
            detail='Ordine riaperto da CHIUSO a DA_FATTURARE',
            ip_address=request.remote_addr
        )

        return jsonify(result), 200
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

# ============================================================================
#  BARCODE / OFFICINA SCAN — endpoint per pistole WiFi e UI dedicate
# ============================================================================

@app.route('/api/scan', methods=['POST'])
def api_scan():
    """Endpoint chiamato dalle pistole WiFi a ogni scansione.

    Body: { "pistola_id": "<id hw configurato>", "codice": "<numero ordine>" }
    Risposta 200 = beep ok sulla pistola; 4xx = beep errore.
    """
    try:
        data = request.get_json(silent=True) or {}
        pistola_id = data.get('pistola_id') or ''
        codice = data.get('codice') or ''
        result = BarcodeManager.process_scan(pistola_id, codice)
        status = result.pop('status_code', 200 if result.get('ok') else 500)
        return jsonify(result), status
    except Exception as e:
        logger.exception('api_scan failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/orders/<order_id>/cartellino', methods=['GET'])
def api_cartellino(order_id):
    """Ritorna il PDF A6 col cartellino barcode dell'ordine."""
    try:
        session = get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if not order:
                return jsonify({'error': 'Ordine non trovato'}), 404
            codice = order.numero_ordine or order.id[:8]
            cliente = order.cliente or ''
            data_consegna = order.data_consegna
            note = ''
            if order.lotto_numero and order.lotto_numero > 0:
                note = f'Lotto {order.lotto_numero}'
                if order.lotto_nome:
                    note += f' — {order.lotto_nome}'
        finally:
            session.close()

        pdf_bytes = genera_cartellino_pdf(
            codice=codice,
            cliente=cliente,
            data_consegna=data_consegna,
            note=note,
        )
        import io as _io
        return send_file(
            _io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f'cartellino_{codice}.pdf',
        )
    except Exception as e:
        logger.exception('api_cartellino failed for %s', order_id)
        return jsonify({'error': str(e)}), 500


@app.route('/api/orders/<order_id>/tempo-officina', methods=['GET'])
def api_tempo_officina(order_id):
    """Ritorna il dettaglio delle sessioni officina per un ordine."""
    try:
        data = BarcodeManager.get_tempo_officina(order_id)
        return jsonify(data), 200
    except Exception as e:
        logger.exception('api_tempo_officina failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/officina/live-status', methods=['GET'])
def api_officina_live_status():
    """Feed live per la pagina 'Stato officina' dell'impiegata."""
    try:
        return jsonify(BarcodeManager.get_live_status()), 200
    except Exception as e:
        logger.exception('api_officina_live_status failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/capo/kpi-operai', methods=['GET'])
def api_capo_kpi_operai():
    """KPI ore per operaio (oggi/settimana/mese) — pagina capo officina."""
    try:
        return jsonify(BarcodeManager.get_kpi_operai()), 200
    except Exception as e:
        logger.exception('api_capo_kpi_operai failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/capo/calendario-ordini', methods=['GET'])
def api_capo_calendario():
    """Ordini per data consegna nel mese (param ?mese=YYYY-MM)."""
    try:
        mese = (request.args.get('mese') or '').strip()
        if not mese:
            now = datetime.utcnow()
            year, month = now.year, now.month
        else:
            try:
                year, month = mese.split('-')
                year = int(year); month = int(month)
                if not (1 <= month <= 12):
                    raise ValueError
            except Exception:
                return jsonify({'error': 'Formato mese non valido (usa YYYY-MM)'}), 400
        return jsonify({
            'mese': f'{year:04d}-{month:02d}',
            'giorni': BarcodeManager.get_calendario_ordini(year, month),
        }), 200
    except Exception as e:
        logger.exception('api_capo_calendario failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/close-residual', methods=['POST'])
def api_admin_close_residual():
    """Chiude tutte le scan ancora aperte (fine turno).

    Richiede capo/admin: passa user_id nel body per audit.
    """
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id') or ''
        if not _require_capo(user_id):
            return jsonify({'error': 'Permesso negato'}), 403
        motivo = data.get('motivo') or 'fine_turno'
        n = BarcodeManager.close_residual_scans(motivo=motivo)
        AuditManager.log(
            user_id=user_id,
            action='CLOSE_RESIDUAL_SCANS',
            entity_type='officina_scans',
            entity_id='*',
            detail=f'Chiuse {n} scan, motivo={motivo}',
        )
        return jsonify({'ok': True, 'chiuse': n}), 200
    except Exception as e:
        logger.exception('api_admin_close_residual failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/pistole', methods=['GET'])
def api_admin_pistole_list():
    """Lista pistole registrate."""
    try:
        return jsonify(BarcodeManager.list_pistole(include_inactive=True)), 200
    except Exception as e:
        logger.exception('api_admin_pistole_list failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/pistole', methods=['POST'])
def api_admin_pistole_create():
    """Registra una nuova pistola."""
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('admin_id') or ''
        if not _require_capo(user_id):
            return jsonify({'error': 'Permesso negato'}), 403
        result = BarcodeManager.create_pistola(
            pistola_id=data.get('pistola_id') or '',
            operatore_id=data.get('operatore_id') or '',
            note=data.get('note') or '',
        )
        if result.get('error'):
            return jsonify(result), 400
        AuditManager.log(
            user_id=user_id,
            action='CREATE_PISTOLA',
            entity_type='pistole',
            entity_id=result.get('id'),
            detail=f'pistola_id={data.get("pistola_id")} → {data.get("operatore_id")}',
        )
        return jsonify(result), 201
    except Exception as e:
        logger.exception('api_admin_pistole_create failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/pistole/<pistola_uuid>', methods=['PUT'])
def api_admin_pistole_update(pistola_uuid):
    """Aggiorna pistola (operatore, attiva, note)."""
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('admin_id') or ''
        if not _require_capo(user_id):
            return jsonify({'error': 'Permesso negato'}), 403
        result = BarcodeManager.update_pistola(
            pistola_uuid=pistola_uuid,
            operatore_id=data.get('operatore_id'),
            attiva=data.get('attiva'),
            note=data.get('note'),
        )
        if result.get('error'):
            return jsonify(result), 400
        AuditManager.log(
            user_id=user_id,
            action='UPDATE_PISTOLA',
            entity_type='pistole',
            entity_id=pistola_uuid,
            detail=str(data),
        )
        return jsonify(result), 200
    except Exception as e:
        logger.exception('api_admin_pistole_update failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/pistole/<pistola_uuid>', methods=['DELETE'])
def api_admin_pistole_delete(pistola_uuid):
    """Elimina pistola."""
    try:
        admin_id = request.args.get('admin_id') or ''
        if not _require_capo(admin_id):
            return jsonify({'error': 'Permesso negato'}), 403
        result = BarcodeManager.delete_pistola(pistola_uuid)
        if result.get('error'):
            return jsonify(result), 400
        AuditManager.log(
            user_id=admin_id,
            action='DELETE_PISTOLA',
            entity_type='pistole',
            entity_id=pistola_uuid,
            detail='',
        )
        return jsonify(result), 200
    except Exception as e:
        logger.exception('api_admin_pistole_delete failed')
        return jsonify({'error': str(e)}), 500


# ============================================================================
#  PREVENTIVI — API REST (Fase 2 merge preventivatore)
# ============================================================================

# Ruoli autorizzati a write/read sui preventivi (decisione: aperto interni, no operai)
_PREV_WRITE_ROLES = ['Commerciale', 'Amministratore', 'CAPO']
_PREV_READ_ROLES = ['Commerciale', 'Amministratore', 'CAPO', 'Impiegata']


@app.route('/api/preventivi', methods=['GET'])
def api_preventivi_list():
    """Lista preventivi (filtri opzionali: cliente, status)."""
    try:
        cliente = request.args.get('cliente')
        status = request.args.get('status')
        limit = min(int(request.args.get('limit', 200)), 500)
        items = PreventivoManager.list(cliente=cliente, status=status, limit=limit)
        return jsonify({'success': True, 'count': len(items), 'preventivi': items}), 200
    except Exception as e:
        logger.exception('preventivi list failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi', methods=['POST'])
def api_preventivi_create():
    """Crea preventivo (BOZZA). Riservato a Commerciale + Admin."""
    try:
        data = request.get_json() or {}
        created_by = data.get('created_by') or ''
        if not _require_role(created_by, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        cliente = (data.get('cliente') or '').strip()
        if not cliente:
            return jsonify({'success': False, 'error': 'Cliente obbligatorio'}), 400
        dcp = data.get('data_consegna_proposta')
        dcp_dt = None
        if dcp:
            try:
                dcp_dt = datetime.strptime(dcp[:10], '%Y-%m-%d')
            except ValueError:
                return jsonify({'success': False, 'error': 'data_consegna_proposta: formato YYYY-MM-DD'}), 400
        p = PreventivoManager.create(
            cliente=cliente,
            created_by=created_by,
            quantita=data.get('quantita', 1),
            numero_ordine_cliente=data.get('numero_ordine_cliente'),
            margine_pct=data.get('margine_pct', 0.0),
            data_consegna_proposta=dcp_dt,
            note=data.get('note'),
        )
        try:
            AuditManager.log(user_id=created_by, action='CREATE_PREVENTIVO',
                             entity_type='preventivi', entity_id=p['id'],
                             detail='cliente=' + cliente)
        except Exception:
            pass
        return jsonify({'success': True, 'preventivo': p}), 201
    except Exception as e:
        logger.exception('preventivi create failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>', methods=['GET'])
def api_preventivi_get(preventivo_id):
    """Dettaglio preventivo + articoli/assiemi/tubolari/piastre."""
    try:
        p = PreventivoManager.get(preventivo_id, include_children=True)
        if not p:
            return jsonify({'success': False, 'error': 'Preventivo non trovato'}), 404
        return jsonify({'success': True, 'preventivo': p}), 200
    except Exception as e:
        logger.exception('preventivo get failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>', methods=['PUT'])
def api_preventivi_update(preventivo_id):
    """Modifica preventivo. Bloccato se status INVIATO/ACCETTATO (immutabili)."""
    try:
        data = request.get_json() or {}
        updated_by = data.pop('updated_by', '')
        if not _require_role(updated_by, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        # data_consegna_proposta come stringa → datetime
        if 'data_consegna_proposta' in data and data['data_consegna_proposta']:
            try:
                data['data_consegna_proposta'] = datetime.strptime(
                    data['data_consegna_proposta'][:10], '%Y-%m-%d')
            except (ValueError, TypeError):
                data['data_consegna_proposta'] = None
        result = PreventivoManager.update(preventivo_id, data)
        if result is None:
            return jsonify({'success': False, 'error': 'Preventivo non trovato'}), 404
        if isinstance(result, dict) and result.get('error'):
            return jsonify({'success': False, 'error': result['error']}), 409
        try:
            AuditManager.log(user_id=updated_by, action='UPDATE_PREVENTIVO',
                             entity_type='preventivi', entity_id=preventivo_id,
                             detail=str(list(data.keys())))
        except Exception:
            pass
        return jsonify({'success': True, 'preventivo': result}), 200
    except Exception as e:
        logger.exception('preventivo update failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>', methods=['DELETE'])
def api_preventivi_delete(preventivo_id):
    """Soft delete (is_deleted=True). Riservato a Commerciale + Admin."""
    try:
        deleted_by = request.args.get('deleted_by') or ''
        if not _require_role(deleted_by, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        ok = PreventivoManager.soft_delete(preventivo_id)
        if not ok:
            return jsonify({'success': False, 'error': 'Preventivo non trovato'}), 404
        try:
            AuditManager.log(user_id=deleted_by, action='DELETE_PREVENTIVO',
                             entity_type='preventivi', entity_id=preventivo_id, detail='')
        except Exception:
            pass
        _cleanup_preventivo_files(preventivo_id)
        return jsonify({'success': True}), 200
    except Exception as e:
        logger.exception('preventivo delete failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/import-xlsx', methods=['POST'])
def api_preventivi_import_xlsx(preventivo_id):
    """Upload XLSX Lantek → estrae articoli e li ritorna (NON li salva ancora).
    La UI mostra l'anteprima; il save effettivo avviene quando l'utente conferma.
    """
    try:
        admin_id = request.form.get('admin_id') or request.args.get('admin_id') or ''
        if not _require_role(admin_id, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'File XLSX obbligatorio'}), 400
        f = request.files['file']
        if not f.filename or not f.filename.lower().endswith('.xlsx'):
            return jsonify({'success': False, 'error': 'File deve essere .xlsx'}), 400
        # Salva temporaneo per processing
        tmp_path = os.path.join(UPLOAD_FOLDER, 'tmp_' + uuid.uuid4().hex + '_' + os.path.basename(f.filename))
        f.save(tmp_path)
        try:
            articoli = _xlsx_importer.importa_xlsx(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return jsonify({'success': True, 'articoli': articoli, 'count': len(articoli)}), 200
    except Exception as e:
        logger.exception('preventivi import xlsx failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/import-dxf', methods=['POST'])
def api_preventivi_import_dxf(preventivo_id):
    """Upload DXF → estrae lavorazioni (pieghe/saldature) + geometria (area/perimetro).
    Il file viene scartato dopo l'estrazione (decisione: no storage DXF).
    """
    try:
        admin_id = request.form.get('admin_id') or request.args.get('admin_id') or ''
        if not _require_role(admin_id, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'File disegno obbligatorio'}), 400
        f = request.files['file']
        fname_lower = (f.filename or '').lower()
        if not (fname_lower.endswith('.dxf') or fname_lower.endswith('.dwg')):
            return jsonify({'success': False, 'error': 'File deve essere .dxf o .dwg'}), 400
        # Salva DXF (o DXF convertito da DWG) in uploads/preventivi_tmp/<id>/
        # per consentire la preview interattiva. Sarà cancellato all'accettazione/rifiuto/delete.
        prev_dir = os.path.join(UPLOAD_FOLDER, 'preventivi_tmp', preventivo_id)
        os.makedirs(prev_dir, exist_ok=True)
        saved_filename = os.path.basename(f.filename)

        is_dwg = fname_lower.endswith('.dwg')
        if is_dwg:
            tmp_dwg = os.path.join(UPLOAD_FOLDER, 'tmp_' + uuid.uuid4().hex + '.dwg')
            f.save(tmp_dwg)
            conv = _convert_dwg_to_dxf(tmp_dwg)
            try: os.remove(tmp_dwg)
            except OSError: pass
            if isinstance(conv, dict) and conv.get('error'):
                err_code = conv['error']
                if err_code == 'ODA_NOT_INSTALLED':
                    return jsonify({
                        'success': False,
                        'error': 'ODA File Converter non installato. Scarica e installa da: '
                                 'https://www.opendesign.com/guestfiles/oda_file_converter '
                                 '(gratuito, ~50MB). Una volta installato il DWG viene '
                                 'convertito automaticamente in DXF. Alternativa: salva il '
                                 'DWG come DXF (AutoCAD 2018) dal tuo CAD e ricarica.',
                    }), 415
                return jsonify({'success': False, 'error': 'Conversione DWG fallita: ' + err_code + ' ' + str(conv.get('detail', ''))}), 500
            # Sposta il convertito (DXF) nella cartella preview persistente con nome originale
            saved_filename = os.path.splitext(saved_filename)[0] + '.dxf'
            tmp_path = os.path.join(prev_dir, saved_filename)
            try:
                import shutil
                shutil.move(conv, tmp_path)
            except Exception:
                tmp_path = conv  # fallback
        else:
            tmp_path = os.path.join(prev_dir, saved_filename)
            f.save(tmp_path)
        try:
            # Config minimo per dxf_scanner (colori standard Lantek)
            # Config rilevamento da app_config.json (sezione dxf_detection) — valori calibrati
            # sul config Preventivatore desktop (ratio_min=1.8, filtra_zona=True, ecc.)
            app_cfg = BarcodeManager.load_config()
            dxf_cfg = app_cfg.get('dxf_detection') or {
                'dxf_colori_piega': [2], 'dxf_colori_saldatura': [1],
                'dxf_lunghezza_minima': 15.0, 'dxf_tolleranza_centro': 1.0,
                'dxf_svasatura_ratio_min': 1.8, 'dxf_svasatura_ratio_max': 3.0,
                'dxf_semicerchio_angolo_min': 150.0, 'dxf_semicerchio_angolo_max': 320.0,
                'dxf_filtra_zona_sviluppata': True,
            }
            pieghe, sald_ml, fil, svas = _dxf_scanner.scansiona_dxf_dettagli(tmp_path, dxf_cfg)
            # v3 detector (Shapely) — fornisce anche confidence + candidati per UI manuale
            try:
                from .preventivi.dxf_polygon_detector_v3 import detect_pezzo_geometry_v3
                geo = detect_pezzo_geometry_v3(tmp_path, dxf_cfg)
                # Se v3 non riesce, fallback a v2 legacy
                if not geo or geo.get('area_dm2', 0) == 0:
                    geo = _dxf_scanner.estrai_geometria_taglio(tmp_path, dxf_cfg)
            except Exception as _v3err:
                logger.warning('detector v3 fallito, fallback v2: %s', _v3err)
                geo = _dxf_scanner.estrai_geometria_taglio(tmp_path, dxf_cfg)
            cartiglio = _dxf_scanner.estrai_materiale_da_cartiglio(tmp_path)
            # Stima spessore: peso da cartiglio + area detector + materiale.
            # Alta affidabilità quando l'area è del pezzo vero (post trova-pezzo)
            # e materiale è stato riconosciuto. Se auto-detect ha bassa confidenza
            # sull'area, lo spessore ritornato va marcato come incerto in UI.
            mat_for_calc = cartiglio.get('materiale') if cartiglio.get('confidence', 0) >= 0.5 else None
            spessore = _dxf_scanner.estrai_spessore_da_cartiglio(
                tmp_path,
                area_dm2=(geo or {}).get('area_dm2'),
                materiale=mat_for_calc,
            )
            # Se l'area del detector è inaffidabile, abbatto la confidenza
            # dello spessore (dipende dall'area).
            if geo and geo.get('needs_manual_select'):
                spessore = {**spessore, 'confidence': min(spessore.get('confidence', 0), 0.4)}
            # NOTA: tmp_path resta su disco (in uploads/preventivi_tmp/<preventivo_id>/<filename>.dxf)
            # per consentire la preview successiva. Cleanup quando preventivo viene
            # accettato/rifiutato/eliminato.
        except Exception as e:
            try: os.remove(tmp_path)
            except OSError: pass
            raise e
        return jsonify({
            'success': True,
            'filename': saved_filename,
            'lavorazioni': {
                'pieghe': pieghe, 'saldatura_ml': sald_ml,
                'filettatura_pz': fil, 'svasatura_pz': svas,
            },
            'geometria': geo,
            'cartiglio': cartiglio,  # {materiale, materiale_raw, confidence}
            'spessore': spessore,    # {spessore_mm, confidence, source, details}
        }), 200
    except Exception as e:
        logger.exception('preventivi import dxf failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/step-files', methods=['GET'])
def api_preventivi_step_files_list(preventivo_id):
    """Elenca i file STEP (.step/.stp) caricati per il preventivo (in preventivi_tmp/<id>/)."""
    try:
        prev_dir = os.path.join(UPLOAD_FOLDER, 'preventivi_tmp', preventivo_id)
        if not os.path.isdir(prev_dir):
            return jsonify({'success': True, 'files': []}), 200
        files = []
        for name in sorted(os.listdir(prev_dir)):
            if name.lower().endswith(('.step', '.stp')):
                fp = os.path.join(prev_dir, name)
                try:
                    size = os.path.getsize(fp)
                except OSError:
                    size = 0
                files.append({'filename': name, 'size': size})
        return jsonify({'success': True, 'files': files}), 200
    except Exception as e:
        logger.exception('step_files_list failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/step/<path:filename>', methods=['GET'])
def api_preventivi_step_file(preventivo_id, filename):
    """Serve il file STEP raw (per viewer 3D preview-step.html che lo scarica via fetch)."""
    try:
        safe_name = os.path.basename(filename)
        prev_dir = os.path.join(UPLOAD_FOLDER, 'preventivi_tmp', preventivo_id)
        step_path = os.path.join(prev_dir, safe_name)
        if not os.path.exists(step_path):
            return jsonify({'error': 'File STEP non trovato'}), 404
        if not safe_name.lower().endswith(('.step', '.stp')):
            return jsonify({'error': 'Estensione file non valida'}), 400
        return send_file(step_path, mimetype='application/octet-stream',
                         as_attachment=False, download_name=safe_name)
    except Exception as e:
        logger.exception('step_file failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/dxf/<path:filename>/svg', methods=['GET'])
def api_preventivi_dxf_svg(preventivo_id, filename):
    """Ritorna SVG ad alta fedeltà del DXF (caricato in import-dxf).

    Usato dalla preview interattiva preview-dxf.html (pan/zoom + lavorazioni).
    """
    try:
        # Sicurezza: filename normalizzato, niente path traversal
        safe_name = os.path.basename(filename)
        prev_dir = os.path.join(UPLOAD_FOLDER, 'preventivi_tmp', preventivo_id)
        dxf_path = os.path.join(prev_dir, safe_name)
        if not os.path.exists(dxf_path):
            return jsonify({'error': 'File DXF non trovato'}), 404
        from flask import Response
        svg_string = _dxf_scanner.dxf_to_svg_string(dxf_path)
        return Response(svg_string, mimetype='image/svg+xml; charset=utf-8')
    except Exception as e:
        logger.exception('dxf_svg failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/dxf/<path:filename>/candidates', methods=['GET'])
def api_preventivi_dxf_candidates(preventivo_id, filename):
    """Ritorna la lista dei poligoni candidati come pezzo (per UI selezione manuale).

    Il detector v3 (Shapely) calcola uno score per ogni poligono chiuso e determina
    il migliore + confidence. Se confidence bassa, il frontend mostra all'utente
    tutti i candidati sovrapposti al DXF con overlay cliccabili.

    Response:
        {
            success: bool,
            geometry: {area_dm2, perimetro_taglio_m, n_pierce, bbox_*, ...},
            candidates: [
                {idx, area_dm2, perimetro_m, bbox: [minx,miny,maxx,maxy],
                 n_circles, n_inner, score, is_selected, geometry: [[x,y], ...]},
                ...
            ],
            selected_candidate_idx: int,
            confidence: 0-1,
            confidence_label: 'alta'|'media'|'bassa'|'nessuna',
            needs_manual_select: bool
        }
    """
    try:
        safe_name = os.path.basename(filename)
        prev_dir = os.path.join(UPLOAD_FOLDER, 'preventivi_tmp', preventivo_id)
        dxf_path = os.path.join(prev_dir, safe_name)
        if not os.path.exists(dxf_path):
            return jsonify({'success': False, 'error': 'File DXF non trovato'}), 404
        from .preventivi.dxf_polygon_detector_v3 import detect_pezzo_geometry_v3
        app_cfg = BarcodeManager.load_config() or {}
        detection_cfg = app_cfg.get('dxf_detection', {})
        r = detect_pezzo_geometry_v3(dxf_path, detection_cfg)
        return jsonify({'success': True, **r}), 200
    except Exception as e:
        logger.exception('dxf_candidates failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/dxf/<path:filename>/spessore', methods=['POST'])
def api_preventivi_dxf_spessore(preventivo_id, filename):
    """Ricalcola lo spessore lamiera per un DXF dato area (dal detector/manuale)
    e materiale (che l'utente potrebbe aver cambiato dopo l'import).

    Body: {area_dm2: float, materiale: str}
    Response: {success, spessore: {spessore_mm, confidence, source, details}}
    """
    try:
        safe_name = os.path.basename(filename)
        prev_dir = os.path.join(UPLOAD_FOLDER, 'preventivi_tmp', preventivo_id)
        dxf_path = os.path.join(prev_dir, safe_name)
        if not os.path.exists(dxf_path):
            return jsonify({'success': False, 'error': 'File DXF non trovato'}), 404
        data = request.get_json(silent=True) or {}
        area = float(data.get('area_dm2') or 0)
        mat = (data.get('materiale') or '').strip()
        sp = _dxf_scanner.estrai_spessore_da_cartiglio(dxf_path,
                                                       area_dm2=area or None,
                                                       materiale=mat or None)
        return jsonify({'success': True, 'spessore': sp}), 200
    except Exception as e:
        logger.exception('dxf spessore failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/dxf/<path:filename>/select-point', methods=['POST'])
def api_preventivi_dxf_select_point(preventivo_id, filename):
    """Pattern 'Trova pezzo' Lantek: click su un contorno chiuso → sistema
    identifica quel poligono e i suoi contorni interni.

    Body: {x: float, y: float}   (coord DXF in mm)
    Response: {success, area_dm2, perimetro_taglio_m, n_pierce, ...}
    """
    try:
        data = request.get_json(silent=True) or {}
        try:
            x = float(data.get('x'))
            y = float(data.get('y'))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'x/y richiesti (float mm DXF)'}), 400
        safe_name = os.path.basename(filename)
        prev_dir = os.path.join(UPLOAD_FOLDER, 'preventivi_tmp', preventivo_id)
        dxf_path = os.path.join(prev_dir, safe_name)
        if not os.path.exists(dxf_path):
            return jsonify({'success': False, 'error': 'File DXF non trovato'}), 404
        from .preventivi.dxf_polygon_detector_v3 import compute_geometry_from_point
        app_cfg = BarcodeManager.load_config() or {}
        detection_cfg = app_cfg.get('dxf_detection', {})
        r = compute_geometry_from_point(dxf_path, x, y, detection_cfg)
        return jsonify({'success': True, **r}), 200
    except Exception as e:
        logger.exception('dxf_select_point failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/dxf/<path:filename>/select-region', methods=['POST'])
def api_preventivi_dxf_select_region(preventivo_id, filename):
    """Ricalcola geometria pezzo prendendo tutti i contorni chiusi nella
    region bbox (mm) indicata dall'utente col marquee drag sulla preview.

    Body: {minx, miny, maxx, maxy, articolo_id: str (opz)}
    Response: {success, area_dm2, perimetro_taglio_m, n_pierce, ...}
    """
    try:
        data = request.get_json(silent=True) or {}
        try:
            minx = float(data.get('minx'))
            miny = float(data.get('miny'))
            maxx = float(data.get('maxx'))
            maxy = float(data.get('maxy'))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'minx/miny/maxx/maxy richiesti (float)'}), 400
        safe_name = os.path.basename(filename)
        prev_dir = os.path.join(UPLOAD_FOLDER, 'preventivi_tmp', preventivo_id)
        dxf_path = os.path.join(prev_dir, safe_name)
        if not os.path.exists(dxf_path):
            return jsonify({'success': False, 'error': 'File DXF non trovato'}), 404
        from .preventivi.dxf_polygon_detector_v3 import compute_geometry_from_region
        app_cfg = BarcodeManager.load_config() or {}
        detection_cfg = app_cfg.get('dxf_detection', {})
        r = compute_geometry_from_region(dxf_path, (minx, miny, maxx, maxy), detection_cfg)
        return jsonify({'success': True, **r}), 200
    except Exception as e:
        logger.exception('dxf_select_region failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/dxf/<path:filename>/select-polygon', methods=['POST'])
def api_preventivi_dxf_select_polygon(preventivo_id, filename):
    """Ricalcola area/perimetro/n_pierce assumendo che l'utente ha scelto un
    poligono specifico come outer del pezzo (invece del top-scored automatico).

    Body:
        {"candidate_idx": int, "articolo_id": str (opz — se presente aggiorna DB)}

    Response:
        {success, geometry: {area_dm2, perimetro_taglio_m, n_pierce, ...}}
    """
    try:
        data = request.get_json(silent=True) or {}
        cand_idx = data.get('candidate_idx')
        articolo_id = data.get('articolo_id') or ''
        if cand_idx is None:
            return jsonify({'success': False, 'error': 'candidate_idx richiesto'}), 400
        try:
            cand_idx = int(cand_idx)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'candidate_idx non valido'}), 400

        safe_name = os.path.basename(filename)
        prev_dir = os.path.join(UPLOAD_FOLDER, 'preventivi_tmp', preventivo_id)
        dxf_path = os.path.join(prev_dir, safe_name)
        if not os.path.exists(dxf_path):
            return jsonify({'success': False, 'error': 'File DXF non trovato'}), 404

        from .preventivi.dxf_polygon_detector_v3 import compute_geometry_from_candidate
        app_cfg = BarcodeManager.load_config() or {}
        detection_cfg = app_cfg.get('dxf_detection', {})
        r = compute_geometry_from_candidate(dxf_path, cand_idx, detection_cfg)
        return jsonify({'success': True, **r}), 200
    except Exception as e:
        logger.exception('dxf_select_polygon failed')
        return jsonify({'success': False, 'error': str(e)}), 500


def _cleanup_preventivo_files(preventivo_id):
    """Rimuove la cartella uploads/preventivi_tmp/<preventivo_id>/ (DXF/STEP temporanei).
    Chiamato all'accettazione, rifiuto o delete del preventivo.
    """
    try:
        import shutil
        d = os.path.join(UPLOAD_FOLDER, 'preventivi_tmp', preventivo_id)
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
    except Exception as exc:
        logger.warning('cleanup preventivo files failed for %s: %s', preventivo_id, exc)


@app.route('/api/preventivi/<preventivo_id>/import-step', methods=['POST'])
def api_preventivi_import_step(preventivo_id):
    """Upload STEP (.stp/.step) → estrae assiemi 3D + tubolari + piastre.

    Esegue 3 analisi indipendenti:
      - step_assieme.analizza_step_assieme  → conteggio corpi + saldatura totale
      - step_tubolari.analizza_step_tubolari → lista profili tubolari (CHS/SHS/RHS)
      - step_piastre.analizza_step_piastre  → lista piastre (spessore + area)

    Il file viene scartato dopo (no storage). Costi base calcolati su materiale='acciaio'
    di default (commerciale può modificare poi).
    """
    try:
        admin_id = request.form.get('admin_id') or request.args.get('admin_id') or ''
        if not _require_role(admin_id, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'File STEP obbligatorio'}), 400
        f = request.files['file']
        if not f.filename or not f.filename.lower().endswith(('.step', '.stp')):
            return jsonify({'success': False, 'error': 'File deve essere .step o .stp'}), 400

        # Salva STEP in preventivi_tmp/<id>/ (persistente per preview 3D; cleanup su accept/reject/delete)
        prev_dir = os.path.join(UPLOAD_FOLDER, 'preventivi_tmp', preventivo_id)
        os.makedirs(prev_dir, exist_ok=True)
        safe_name = os.path.basename(f.filename)
        step_path = os.path.join(prev_dir, safe_name)
        f.save(step_path)
        try:
            assieme_data = _step_assieme.analizza_step_assieme(step_path) or {}
            tubolari_data = _step_tubolari.analizza_step_tubolari(step_path, _PROFILI_TUBOLARI_DB) or {}
            piastre_data = _step_piastre.analizza_step_piastre(step_path) or {}
        except Exception:
            # Se l'analisi fallisce non lasciare il file orfano
            try: os.remove(step_path)
            except OSError: pass
            raise

        # Coefficienti da config del Preventivatore desktop (oggi inline, in futuro spostiamoli in app_config)
        config_tubolari_piastre = {
            'costo_materiale_acciaio_kg': 1.50,
            'costo_materiale_inox_kg': 4.50,
            'costo_materiale_alluminio_kg': 3.50,
            'costo_orario_taglio_tubo': 40.0,
            'costo_taglio_dritto': 1.0,
            'costo_taglio_obliquo': 2.5,
            'costo_taglio_sagomato': 5.0,
        }

        # Costi tubolari + piastre
        tub_costi = {}
        pia_costi = {}
        try:
            tub_costi = _step_tubolari.calcola_costo_tubolare(tubolari_data, config_tubolari_piastre, 'acciaio')
        except Exception as e:
            logger.warning('calcola_costo_tubolare failed: %s', e)
        try:
            pia_costi = _step_piastre.calcola_costo_piastre(piastre_data, config_tubolari_piastre, 'acciaio')
        except Exception as e:
            logger.warning('calcola_costo_piastre failed: %s', e)

        # Normalizza tubolari per la UI/DB
        tubolari_list = []
        for t in (tubolari_data.get('tubi') or []):
            tubolari_list.append({
                'profilo': t.get('profilo') or '',
                'tipo': t.get('tipo'),
                'materiale': 'acciaio',
                'lunghezza_m': t.get('lunghezza_m') or 0,
                'peso_kg': t.get('peso_kg') or 0,
                'costo_materiale': (t.get('peso_kg') or 0) * config_tubolari_piastre['costo_materiale_acciaio_kg'],
                'costo_taglio_totale': 0,  # aggregato in tub_costi.totale, qui zero per articolo singolo
                'n_tagli_dritti': 1 if t.get('taglio_1') == 'dritto' else 0,
                'n_tagli_obliqui': 1 if t.get('taglio_1') == 'obliquo' else 0,
            })

        # Normalizza piastre per la UI/DB
        piastre_list = []
        dettaglio_pia = pia_costi.get('dettaglio_piastre') or []
        for i, p in enumerate(piastre_data.get('piastre') or []):
            costo_p = dettaglio_pia[i].get('costo', 0) if i < len(dettaglio_pia) else 0
            piastre_list.append({
                'spessore_mm': p.get('spessore_mm') or 0,
                'area_dm2': p.get('area_dm2') or 0,
                'peso_kg': p.get('peso_kg') or 0,
                'costo': costo_p,
                'materiale': 'acciaio',
            })

        # Aggrega un assieme "macro" dal file STEP (saldatura totale + componenti count)
        assiemi_list = []
        saldatura_mt_tot = (assieme_data.get('saldatura_mm') or 0) / 1000.0
        if tubolari_list or piastre_list or saldatura_mt_tot > 0:
            assiemi_list.append({
                'codice_assieme': os.path.splitext(f.filename)[0],
                'qty': 1,
                'ore_montaggio': 0,
                'ore_puntatura': 0,
                'costo': 0,
                'costo_puntatura': 0,
                'costo_saldatura_assieme': saldatura_mt_tot * 18.0,  # default 18 EUR/ml saldatura
                'saldatura_mt': saldatura_mt_tot,
                'peso_kg': (tubolari_data.get('peso_totale_kg') or 0) + (piastre_data.get('peso_totale_kg') or 0),
                'componenti_qty': {},
            })

        return jsonify({
            'success': True,
            'assiemi': assiemi_list,
            'tubolari': tubolari_list,
            'piastre': piastre_list,
            'summary': {
                'n_tubolari': len(tubolari_list),
                'n_piastre': len(piastre_list),
                'peso_totale_kg': round(((tubolari_data.get('peso_totale_kg') or 0) + (piastre_data.get('peso_totale_kg') or 0)), 2),
                'saldatura_mt_tot': round(saldatura_mt_tot, 2),
                'costo_totale_tubolari': tub_costi.get('totale', 0),
                'costo_totale_piastre': pia_costi.get('totale', 0),
            },
        }), 200
    except Exception as e:
        logger.exception('preventivi import step failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/articoli', methods=['PUT'])
def api_preventivi_articoli_replace(preventivo_id):
    """Sostituisce l'intera lista degli articoli del preventivo (bulk replace).

    Usato dal frontend come autosave dopo import DXF / cambi editor. Il
    backend fa delete + insert atomici via PreventivoManager.replace_articoli.
    Bloccato se preventivo INVIATO / ACCETTATO.
    """
    try:
        data = request.get_json(silent=True) or {}
        admin_id = data.get('admin_id') or ''
        if not _require_role(admin_id, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        articoli = data.get('articoli', [])
        if not isinstance(articoli, list):
            return jsonify({'success': False, 'error': 'articoli deve essere una lista'}), 400
        result = PreventivoManager.replace_articoli(preventivo_id, articoli)
        if isinstance(result, dict) and 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 409
        try:
            AuditManager.log(user_id=admin_id, action='REPLACE_ARTICOLI',
                             entity_type='preventivi', entity_id=preventivo_id,
                             detail=f'n_articoli={result.get("count", 0)}')
        except Exception:
            pass
        return jsonify({'success': True, 'count': result.get('count', 0)}), 200
    except Exception as e:
        logger.exception('replace articoli failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/articoli/<articolo_id>/stima-base', methods=['POST'])
def api_preventivi_stima_base(preventivo_id, articolo_id):
    """Calcola stima costo base laser per un articolo (richiede spessore+materiale).

    Body opzionale: { articolo: {area_dm2, perimetro_taglio_m, n_forature,
                                  spessore_mm, materiale} }
    Se body non fornito, legge dal DB l'articolo per id.
    """
    try:
        data = request.get_json(silent=True) or {}
        admin_id = data.get('admin_id') or request.args.get('admin_id') or ''
        if not _require_role(admin_id, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        articolo = data.get('articolo')
        if not articolo:
            # Leggi articolo dal DB
            p = PreventivoManager.get(preventivo_id, include_children=True)
            if not p:
                return jsonify({'success': False, 'error': 'Preventivo non trovato'}), 404
            articolo = next((a for a in p['articoli'] if a['id'] == articolo_id), None)
            if not articolo:
                return jsonify({'success': False, 'error': 'Articolo non trovato'}), 404
        cfg = BarcodeManager.load_config()
        stima = _laser_estimator.stima_base(articolo, cfg)
        return jsonify({'success': True, 'stima': stima}), 200
    except Exception as e:
        logger.exception('preventivi stima-base failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/config', methods=['GET'])
def api_preventivi_config_get():
    """Coefficienti globali usati dallo stimatore + cost calculator.

    Ritorna laser_config (costi orari, €/kg, densità) + preventivi_config
    (costi lavorazioni post-taglio, sconti, margini default). Usato dalla tab
    Impostazioni per il form editabile.

    Accessibile a Commerciale + Amministratore + Capo.
    """
    try:
        cfg = BarcodeManager.load_config()
        return jsonify({
            'success': True,
            'laser_config': cfg.get('laser_config') or _laser_estimator.DEFAULT_LASER_CONFIG,
            'preventivi_config': cfg.get('preventivi_config') or {},
        }), 200
    except Exception as e:
        logger.exception('preventivi/config GET failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/config', methods=['PUT'])
def api_preventivi_config_put():
    """Aggiorna coefficienti globali. Salva quello che riceve senza validazione
    stretta sui valori (l'admin è responsabile). Loggato in audit.

    Body: {admin_id, laser_config?, preventivi_config?}. I singoli sub-oggetti
    sono opzionali: se assenti si mantiene quello attuale.
    """
    try:
        data = request.get_json(silent=True) or {}
        admin_id = data.get('admin_id') or ''
        if not _require_role(admin_id, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        updates = {}
        if isinstance(data.get('laser_config'), dict):
            updates['laser_config'] = data['laser_config']
        if isinstance(data.get('preventivi_config'), dict):
            updates['preventivi_config'] = data['preventivi_config']
        if not updates:
            return jsonify({'success': False, 'error': 'Nessuna sezione da aggiornare'}), 400
        saved = BarcodeManager.save_config(updates)
        if 'error' in saved:
            return jsonify({'success': False, 'error': saved['error']}), 500
        try:
            AuditManager.log(user_id=admin_id, action='UPDATE_PREVENTIVI_CONFIG',
                             entity_type='config', entity_id='preventivi',
                             detail=str(list(updates.keys())))
        except Exception:
            pass
        return jsonify({
            'success': True,
            'laser_config': saved.get('laser_config'),
            'preventivi_config': saved.get('preventivi_config'),
        }), 200
    except Exception as e:
        logger.exception('preventivi/config PUT failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/calcola', methods=['POST'])
def api_preventivi_calcola(preventivo_id):
    """Ricalcola totali del preventivo (chiama cost_calculator)."""
    try:
        data = request.get_json(silent=True) or {}
        admin_id = data.get('admin_id') or ''
        if not _require_role(admin_id, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        # Implementazione completa rimandata a Fase 3 (richiede integrazione editor articoli)
        # Per ora ritorna i totali correnti dal DB (placeholder funzionale)
        p = PreventivoManager.get(preventivo_id, include_children=False)
        if not p:
            return jsonify({'success': False, 'error': 'Preventivo non trovato'}), 404
        return jsonify({
            'success': True,
            'preventivo': p,
            '_note': 'Ricalcolo completo via cost_calculator implementato in Fase 3',
        }), 200
    except Exception as e:
        logger.exception('preventivi calcola failed')
        return jsonify({'success': False, 'error': str(e)}), 500


def _preventivo_to_pdf_dati(p: dict) -> dict:
    """Mappa il dict serializzato PreventivoManager al formato atteso da PDFPreventivo.genera_pdf().

    Differenze principali gestite:
    - Assiemi/tubolari/piastre: DB restituisce liste, PDF vuole dict per codice_assieme
    - Somma costi_piegatura/saldatura/filettatura/svasatura da articoli
    - Data ISO → dd/mm/yyyy italiano
    - Campi opzionali (azienda, logo_path) presi da app_config se disponibili
    """
    # Somma costi post-taglio da articoli (moltiplicati per quantità)
    articoli = p.get('articoli') or []
    tot_piega = sum(float(a.get('costo_piega') or 0) * int(a.get('quantita') or 1) for a in articoli)
    tot_sald = sum(float(a.get('costo_saldatura') or 0) * int(a.get('quantita') or 1) for a in articoli)
    tot_filett = sum(float(a.get('costo_filettatura') or 0) * int(a.get('quantita') or 1) for a in articoli)
    tot_svasat = sum(float(a.get('costo_svasatura') or 0) * int(a.get('quantita') or 1) for a in articoli)

    # Assiemi: lista → dict per codice_assieme (formato PDF)
    assiemi_list = p.get('assiemi') or []
    costi_montaggio = {}
    for a in assiemi_list:
        cod = a.get('codice_assieme') or a.get('id') or ''
        costi_montaggio[cod] = {
            'ore_montaggio': a.get('ore_montaggio') or 0,
            'ore_puntatura': a.get('ore_puntatura') or 0,
            'costo': a.get('costo') or 0,
            'costo_puntatura': a.get('costo_puntatura') or 0,
            'costo_saldatura_assieme': a.get('costo_saldatura_assieme') or 0,
            'saldatura_mt': a.get('saldatura_mt') or 0,
            'peso_kg': a.get('peso_kg') or 0,
            'qty': a.get('qty') or 1,
        }

    # Tubolari: raggruppa per codice_assieme in dict {codice: {'analisi': {'tubi': [...]}, 'costi': {...}}}
    tubolari_list = p.get('tubolari') or []
    tubolari_per_assieme = {}
    for t in tubolari_list:
        cod = t.get('codice_assieme') or 'GENERICO'
        node = tubolari_per_assieme.setdefault(cod, {'analisi': {'tubi': []}, 'costi': {'dettaglio_tubi': []}})
        # Deriva stringhe taglio da conteggio dritti/obliqui
        n_dr = int(t.get('n_tagli_dritti') or 0)
        n_ob = int(t.get('n_tagli_obliqui') or 0)
        # Assumiamo 2 estremi per tubo. Se ci sono obliqui, mostra "obliquo/dritto" o "obliquo/obliquo".
        if n_ob >= 2:
            taglio_1, taglio_2 = 'obliquo', 'obliquo'
        elif n_ob == 1:
            taglio_1, taglio_2 = 'obliquo', 'dritto'
        else:
            taglio_1, taglio_2 = 'dritto', 'dritto'
        node['analisi']['tubi'].append({
            'profilo': t.get('profilo') or '',
            'lunghezza_m': float(t.get('lunghezza_m') or 0),
            'taglio_1': taglio_1,
            'taglio_2': taglio_2,
            'peso_kg': float(t.get('peso_kg') or 0),
            'costo_materiale': float(t.get('costo_materiale') or 0),
            'costo_taglio': float(t.get('costo_taglio_totale') or 0),
            'materiale': t.get('materiale') or '',
        })

    # Piastre: raggruppa per codice_assieme nel formato dict che pdf_exporter si aspetta:
    # {codice: {'analisi': {'piastre': [{spessore_mm, area_dm2, peso_kg}, ...]},
    #           'costi':   {'dettaglio_piastre': [{'costo': N}, ...], 'totale': N}}}
    piastre_list = p.get('piastre') or []
    piastre_per_assieme = {}
    for pl in piastre_list:
        cod = pl.get('codice_assieme') or 'GENERICO'
        node = piastre_per_assieme.setdefault(cod, {
            'analisi': {'piastre': []},
            'costi': {'dettaglio_piastre': [], 'totale': 0.0},
        })
        node['analisi']['piastre'].append({
            'spessore_mm': pl.get('spessore_mm') or 0,
            'area_dm2': pl.get('area_dm2') or 0,
            'peso_kg': pl.get('peso_kg') or 0,
            'materiale': pl.get('materiale') or '',
        })
        costo = float(pl.get('costo') or 0)
        node['costi']['dettaglio_piastre'].append({'costo': costo})
        node['costi']['totale'] += costo

    # Data
    data_str = ''
    if p.get('data_creazione'):
        try:
            dt = datetime.fromisoformat(p['data_creazione'])
            data_str = dt.strftime('%d/%m/%Y')
        except Exception:
            data_str = p['data_creazione']
    else:
        data_str = datetime.now().strftime('%d/%m/%Y')

    # Ogni articolo per PDF vuole 'costo' = costo unitario totale
    articoli_pdf = []
    for a in articoli:
        costo_base = a.get('costo_base_override') if a.get('costo_base_override') is not None else (a.get('costo_base_stimato') or 0)
        costo_articolo = (float(costo_base or 0)
                          + float(a.get('costo_piega') or 0)
                          + float(a.get('costo_saldatura') or 0)
                          + float(a.get('costo_filettatura') or 0)
                          + float(a.get('costo_svasatura') or 0)
                          + float(a.get('costo_apporto') or 0)
                          + float(a.get('costo_pulizia') or 0))
        articoli_pdf.append({
            'codice': a.get('codice') or '',
            'quantita': a.get('quantita') or 1,
            'materiale': a.get('materiale') or '',
            'spessore_mm': a.get('spessore_mm'),
            'area_dm2': a.get('area_dm2') or 0,
            'costo': costo_articolo,
            'costo_materiale': a.get('costo_materiale') or costo_base,
            'costo_piega': a.get('costo_piega') or 0,
            'costo_saldatura': a.get('costo_saldatura') or 0,
            'costo_filettatura': a.get('costo_filettatura') or 0,
            'costo_svasatura': a.get('costo_svasatura') or 0,
            'costo_apporto': a.get('costo_apporto') or 0,
            'costo_pulizia': a.get('costo_pulizia') or 0,
        })

    # Info azienda: da app_config sezione 'azienda' se presente
    app_cfg = BarcodeManager.load_config() or {}
    azienda_info = app_cfg.get('azienda') or {}

    return {
        'cliente': p.get('cliente') or '',
        'numero_ordine': p.get('numero_ordine_cliente') or f"PREV-{p.get('id', '')[:8]}",
        'data': data_str,
        'articoli': articoli_pdf,
        'quantita': p.get('quantita') or 1,
        'margine': p.get('margine_pct') or 0,
        'costi_montaggio': costi_montaggio,
        'tubolari_per_assieme': tubolari_per_assieme,
        'piastre_per_assieme': piastre_per_assieme,
        'totale_pezzo': p.get('totale_pezzo') or 0,
        'totale_lotto': p.get('totale_lotto') or 0,
        'costo_piegatura': tot_piega,
        'costo_saldatura': tot_sald,
        'costo_filettatura': tot_filett,
        'costo_svasatura': tot_svasat,
        'costo_montaggio_totale': p.get('costi_montaggio_totale') or 0,
        'costo_tubolari_totale': p.get('costi_tubolari_totale') or 0,
        'costo_piastre_totale': p.get('costi_piastre_totale') or 0,
        'note': p.get('note') or '',
        'azienda': azienda_info,
    }


@app.route('/api/preventivi/<preventivo_id>/pdf', methods=['GET'])
def api_preventivi_pdf(preventivo_id):
    """Genera e serve il PDF del preventivo (officina-ready) — distinta taglio inclusa."""
    try:
        p = PreventivoManager.get(preventivo_id, include_children=True)
        if not p:
            return jsonify({'success': False, 'error': 'Preventivo non trovato'}), 404

        dati_pdf = _preventivo_to_pdf_dati(p)

        # Genera in cartella preventivi
        pdf_dir = os.path.join(UPLOAD_FOLDER, 'preventivi_pdf')
        os.makedirs(pdf_dir, exist_ok=True)
        filename = f"preventivo_{p.get('numero_ordine_cliente') or preventivo_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        # Sanitize filename
        filename = ''.join(c if c.isalnum() or c in '._-' else '_' for c in filename)
        pdf_path = os.path.join(pdf_dir, filename)

        app_cfg = BarcodeManager.load_config() or {}
        exporter = _pdf_exporter.PDFPreventivo(app_cfg)
        exporter.genera_pdf(pdf_path, dati_pdf)

        return send_file(pdf_path, mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        logger.exception('preventivi pdf failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/invia', methods=['POST'])
def api_preventivi_invia(preventivo_id):
    """Transizione BOZZA → INVIATO. (Snapshot versioning sarà aggiunto in Fase 3.)"""
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id') or ''
        if not _require_role(user_id, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        result = PreventivoManager.transition_status(preventivo_id, 'INVIATO', user_id=user_id)
        if result is None:
            return jsonify({'success': False, 'error': 'Preventivo non trovato'}), 404
        if isinstance(result, dict) and result.get('error'):
            return jsonify({'success': False, 'error': result['error']}), 409
        try:
            AuditManager.log(user_id=user_id, action='SEND_PREVENTIVO',
                             entity_type='preventivi', entity_id=preventivo_id, detail='BOZZA->INVIATO')
        except Exception:
            pass
        return jsonify({'success': True, 'preventivo': result}), 200
    except Exception as e:
        logger.exception('preventivi invia failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/accetta', methods=['POST'])
def api_preventivi_accetta(preventivo_id):
    """Transizione INVIATO → ACCETTATO + creazione atomica Order FerroTrack.

    Body opzionale:
      {
        "user_id": "...",
        "articoli": [...],                  // se passati, sostituiscono quelli su DB
        "totali": {"totale_pezzo", "totale_pezzo_con_margine", "totale_lotto"},
        "data_consegna": "YYYY-MM-DD",      // override della data_consegna_proposta
        "note_aggiuntive": "..."            // appese alle note ordine FerroTrack
      }

    Output: {success, order_id, numero_ordine, cartellino_url, preventivo}.
    """
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id') or ''
        if not _require_role(user_id, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        result = PreventivoManager.accetta_e_crea_ordine(
            preventivo_id,
            user_id=user_id,
            articoli=data.get('articoli'),
            assiemi=data.get('assiemi'),
            tubolari=data.get('tubolari'),
            piastre=data.get('piastre'),
            totali=data.get('totali'),
            note_aggiuntive=data.get('note_aggiuntive'),
            data_consegna_override=data.get('data_consegna'),
        )
        if not result or result.get('error'):
            err = result.get('error') if result else 'Errore sconosciuto'
            return jsonify({'success': False, 'error': err}), 409
        # Cleanup DXF/STEP temporanei caricati per il preventivo
        _cleanup_preventivo_files(preventivo_id)
        return jsonify(result), 200
    except Exception as e:
        logger.exception('preventivi accetta failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preventivi/<preventivo_id>/rifiuta', methods=['POST'])
def api_preventivi_rifiuta(preventivo_id):
    """Transizione INVIATO → RIFIUTATO."""
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id') or ''
        if not _require_role(user_id, _PREV_WRITE_ROLES):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        result = PreventivoManager.transition_status(preventivo_id, 'RIFIUTATO', user_id=user_id)
        if result is None:
            return jsonify({'success': False, 'error': 'Preventivo non trovato'}), 404
        if isinstance(result, dict) and result.get('error'):
            return jsonify({'success': False, 'error': result['error']}), 409
        try:
            AuditManager.log(user_id=user_id, action='REJECT_PREVENTIVO',
                             entity_type='preventivi', entity_id=preventivo_id, detail='INVIATO->RIFIUTATO')
        except Exception:
            pass
        _cleanup_preventivo_files(preventivo_id)
        return jsonify({'success': True, 'preventivo': result}), 200
    except Exception as e:
        logger.exception('preventivi rifiuta failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/laser-config', methods=['GET'])
def api_admin_laser_config_get():
    """Ritorna sezione laser_config dal app_config.json (coefficienti stimatore)."""
    try:
        cfg = BarcodeManager.load_config()
        return jsonify({
            'success': True,
            'laser_config': cfg.get('laser_config') or _laser_estimator.DEFAULT_LASER_CONFIG,
        }), 200
    except Exception as e:
        logger.exception('admin laser-config GET failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/laser-config', methods=['PUT'])
def api_admin_laser_config_put():
    """Aggiorna coefficienti stimatore laser (solo admin/capi)."""
    try:
        data = request.get_json(silent=True) or {}
        admin_id = data.get('admin_id') or ''
        if not _require_role(admin_id, ['Amministratore', 'CAPO']):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        new_config = data.get('laser_config')
        if not isinstance(new_config, dict):
            return jsonify({'success': False, 'error': 'laser_config deve essere un oggetto'}), 400
        saved = BarcodeManager.save_config({'laser_config': new_config})
        if 'error' in saved:
            return jsonify({'success': False, 'error': saved['error']}), 500
        try:
            AuditManager.log(user_id=admin_id, action='UPDATE_LASER_CONFIG',
                             entity_type='config', entity_id='laser_config',
                             detail=str(list(new_config.keys())))
        except Exception:
            pass
        return jsonify({'success': True, 'laser_config': saved.get('laser_config')}), 200
    except Exception as e:
        logger.exception('admin laser-config PUT failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/export-orders', methods=['GET'])
def api_admin_export_orders():
    """Export CSV ordini per gestionale esterno (cliente non ha Odoo ma userà altro gestionale).

    Query: ?format=csv|json (default: csv), ?from=YYYY-MM-DD, ?to=YYYY-MM-DD
    """
    try:
        admin_id = request.args.get('admin_id') or ''
        if not _require_role(admin_id, ['Amministratore', 'CAPO']):
            return jsonify({'success': False, 'error': 'Permesso negato'}), 403
        fmt = (request.args.get('format') or 'csv').lower()
        orders = OrderManager.get_all_orders_dict() or []
        # Filtri data
        date_from = request.args.get('from')
        date_to = request.args.get('to')
        if date_from:
            try:
                df = datetime.strptime(date_from, '%Y-%m-%d')
                orders = [o for o in orders if o.get('data_ricezione') and
                          datetime.fromisoformat(str(o['data_ricezione']).rstrip('Z')[:19]) >= df]
            except Exception:
                pass
        if date_to:
            try:
                dt = datetime.strptime(date_to, '%Y-%m-%d')
                orders = [o for o in orders if o.get('data_ricezione') and
                          datetime.fromisoformat(str(o['data_ricezione']).rstrip('Z')[:19]) <= dt]
            except Exception:
                pass

        if fmt == 'json':
            import json as _json
            import io
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            payload = _json.dumps(orders, ensure_ascii=False, indent=2, default=str).encode('utf-8')
            buf = io.BytesIO(payload); buf.seek(0)
            return send_file(buf, mimetype='application/json',
                             as_attachment=True, download_name='orders_' + ts + '.json')
        else:
            import csv as _csv
            import io
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            cols = ['id', 'numero_ordine', 'cliente', 'data_ricezione', 'data_consegna',
                    'status', 'origine', 'preventivo_id_origine',
                    'numero_ddt', 'data_ddt', 'numero_fattura', 'data_fattura', 'note']
            out = io.StringIO()
            w = _csv.DictWriter(out, fieldnames=cols, extrasaction='ignore')
            w.writeheader()
            for o in orders:
                w.writerow({c: o.get(c, '') for c in cols})
            data_bytes = out.getvalue().encode('utf-8-sig')  # BOM per Excel italiano
            buf = io.BytesIO(data_bytes); buf.seek(0)
            return send_file(buf, mimetype='text/csv; charset=utf-8',
                             as_attachment=True, download_name='orders_' + ts + '.csv')
    except Exception as e:
        logger.exception('admin export orders failed')
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

"""Flask Backend per Schedulatore Laser"""
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path

# Importa moduli locali
from .models import initialize_database
from .database import OrderManager, UserManager, AuditManager
from .pdf_parser import extract_pdf_content

# Estrattore universale (Docling + Gemini 2.0 Flash) — importato con guard
# perche universal_extractor.py importa google.genai a livello modulo.
# Se google-genai non e installato, Flask si avvia comunque usando i parser classici.
try:
    from .universal_extractor import extract_universal
    from .universal_extractor import ExtractionError as UniversalExtractionError
    _UNIVERSAL_EXTRACTOR_AVAILABLE = True
except ImportError as _ue_import_err:
    _UNIVERSAL_EXTRACTOR_AVAILABLE = False
    print(f"[INFO] Estrattore universale non disponibile (ImportError): {_ue_import_err}")

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

# ============ FRONTEND ROUTES ============

@app.route('/')
def index():
    """Serve login page"""
    return send_from_directory(FRONTEND_FOLDER, 'login.html')

@app.route('/ordini-estratti')
def ordini_dashboard():
    """Serve dashboard ordini estratti dai PDF"""
    return send_from_directory(FRONTEND_FOLDER, 'ordini_estratti.html')

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
            'machines': user['machines']
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

# ============ API ORDINI ============

@app.route('/api/orders', methods=['POST'])
def create_order():
    """Crea un nuovo ordine con articoli"""
    try:
        data = request.get_json()
        
        order = OrderManager.create_order(
            cliente=data.get('cliente'),
            data_consegna=data.get('data_consegna'),
            articles=data.get('articles', []),
            required_phases=data.get('required_phases', ['LASER', 'PIEGA', 'SALDATURA']),
            preventivo_minuti=data.get('preventivo_minuti', 0),
            note=data.get('note', '')
        )
        
        return jsonify({
            'success': True,
            'order_id': order.id,
            'cliente': order.cliente,
            'data_consegna': order.data_consegna.isoformat(),
            'articles': order.articles,
            'total_quantity': order.total_quantity
        }), 201
        
    except Exception as e:
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

@app.route('/api/orders/<order_id>/approve', methods=['POST'])
def approve_order(order_id):
    """Supervisore approva ordine e seleziona fasi"""
    try:
        data = request.get_json()
        required_phases = data.get('required_phases', [])
        operatore_id = data.get('operatore_id', 'unknown')

        if not required_phases or len(required_phases) == 0:
            return jsonify({'error': 'Seleziona almeno una fase'}), 400

        # Aggiorna ordine con fasi selezionate
        order = OrderManager.session.query(Order).filter(Order.id == order_id).first()
        if not order:
            return jsonify({'error': 'Ordine non trovato'}), 404

        order.required_phases = required_phases
        OrderManager.session.commit()

        # Crea processing_steps per ogni fase selezionata
        for phase in required_phases:
            OrderManager.create_processing_step(order_id, phase)

        # Audit log
        AuditManager.log(
            user_id=operatore_id,
            action='APPROVE_ORDER',
            entity_type='order',
            entity_id=order_id,
            detail=f'Ordine approvato con fasi: {", ".join(required_phases)}'
        )

        return jsonify({
            'success': True,
            'order_id': order_id,
            'numero_ordine': order.cliente,  # Fallback
            'required_phases': required_phases
        }), 200

    except Exception as e:
        print(f"[ERROR] Approve order error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders', methods=['GET'])
def get_orders():
    """Recupera lista ordini"""
    try:
        cliente = request.args.get('cliente')
        orders_data = OrderManager.get_all_orders_dict(cliente=cliente)
        return jsonify(orders_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/<order_id>/articles', methods=['PUT'])
def update_order_articles(order_id):
    """Aggiorna articoli di un ordine"""
    try:
        data = request.get_json()
        articles = data.get('articles', [])
        
        success = OrderManager.update_order_articles(order_id, articles)
        if success:
            return jsonify({'success': True}), 200
        return jsonify({'success': False, 'error': 'Ordine non trovato'}), 404
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/orders/confirm-phases', methods=['POST'])
def confirm_phases():
    """Crea ordine confermando fasi selezionate"""
    try:
        data = request.get_json() or {}

        cliente = data.get('cliente')
        data_consegna = data.get('data_consegna')
        articles = data.get('articles', [])
        selected_phases = data.get('selected_phases', [])
        operatore_id = data.get('operatore_id')

        if not cliente or not data_consegna or not articles or not selected_phases:
            return jsonify({
                'success': False,
                'error': 'Parametri obbligatori: cliente, data_consegna, articles, selected_phases'
            }), 400

        # Crea ordine con fasi selezionate
        order = OrderManager.create_order(
            cliente=cliente,
            data_consegna=data_consegna,
            articles=articles,
            required_phases=selected_phases,
            preventivo_minuti=0,
            note=''
        )

        # Registra azione nel audit log
        if operatore_id:
            operatore = UserManager.get_user(operatore_id)
            operatore_name = operatore.get('name') if operatore else operatore_id
            AuditManager.log(
                user_id=operatore_id,
                user_name=operatore_name,
                action='CREA_ORDINE',
                entity_type='order',
                entity_id=order.id,
                detail=f"Fasi: {', '.join(selected_phases)}",
                ip_address=request.remote_addr
            )

        return jsonify({
            'success': True,
            'order_id': order.id,
            'cliente': order.cliente,
            'data_consegna': order.data_consegna.isoformat(),
            'articles': order.articles,
            'required_phases': selected_phases,
            'total_quantity': order.total_quantity
        }), 201

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ============ API FASI ============

@app.route('/api/orders/<order_id>/phase/<phase>/start', methods=['POST'])
def start_phase(order_id, phase):
    """Inizia una fase di lavorazione"""
    try:
        data = request.get_json() or {}
        operatore = data.get('operatore', '')
        operatore_id = data.get('operatore_id')

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
    """Completa una fase e ritorna prossimi articoli"""
    try:
        data = request.get_json() or {}
        note = data.get('note', '')
        operatore_id = data.get('operatore_id')

        result = OrderManager.complete_phase(order_id, phase, note)
        if result.get('success'):
            # Registra azione nel audit log
            if operatore_id:
                operatore_user = UserManager.get_user(operatore_id)
                operatore_name = operatore_user.get('name') if operatore_user else operatore_id
                AuditManager.log(
                    user_id=operatore_id,
                    user_name=operatore_name,
                    action='COMPLETE_PHASE',
                    entity_type='phase',
                    entity_id=order_id,
                    detail=f"Phase: {phase}",
                    ip_address=request.remote_addr
                )

            # Recupera dettagli aggiornati
            details = OrderManager.get_order_details(order_id)
            return jsonify({
                'success': True,
                'phase': phase,
                'order_details': details
            }), 200

        return jsonify(result), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders/<order_id>/phase/<phase>/complete-partial', methods=['POST'])
def complete_phase_partial(order_id, phase):
    """Completa una fase solo per articoli specifici (completamento parziale)"""
    try:
        data = request.get_json() or {}
        article_indices = data.get('article_indices', [])  # Es: [0, 1, 3]
        note = data.get('note', '')
        operatore_id = data.get('operatore_id')

        if not article_indices:
            return jsonify({'success': False, 'error': 'Nessun articolo selezionato'}), 400

        if not all(isinstance(i, int) and i >= 0 for i in article_indices):
            return jsonify({'success': False, 'error': 'Indici articoli non validi'}), 400

        result = OrderManager.complete_phase_partial(order_id, phase, article_indices, note)
        if result.get('success'):
            # Registra azione nel audit log
            if operatore_id:
                operatore_user = UserManager.get_user(operatore_id)
                operatore_name = operatore_user.get('name') if operatore_user else operatore_id
                AuditManager.log(
                    user_id=operatore_id,
                    user_name=operatore_name,
                    action='COMPLETE_PHASE',
                    entity_type='phase',
                    entity_id=order_id,
                    detail=f"Phase: {phase}, Articles: {article_indices}",
                    ip_address=request.remote_addr
                )

            # Recupera dettagli aggiornati
            details = OrderManager.get_order_details(order_id)
            return jsonify({
                'success': True,
                'phase': phase,
                'articles_completed': result.get('articles_completed'),
                'phase_complete': result.get('phase_complete'),
                'order_details': details
            }), 200

        return jsonify(result), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/phase/<phase>/orders', methods=['GET'])
def get_orders_by_phase(phase):
    """Recupera ordini per una fase specificata"""
    try:
        orders = OrderManager.get_orders_by_phase(phase)
        
        result = []
        for order in orders:
            # Per ogni ordine, calcola quali articoli hanno questa fase come prossima
            details = OrderManager.get_order_details(order.id)
            articles_for_this_phase = [
                a for a in details['articles'] 
                if a['next_phase'] == phase
            ]
            
            if articles_for_this_phase:
                result.append({
                    'id': order.id,
                    'cliente': order.cliente,
                    'total_quantity': order.total_quantity,
                    'articles_next_phase': articles_for_this_phase,
                    'data_consegna': order.data_consegna.isoformat()
                })
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ API ADMIN ============

@app.route('/api/admin/kpi', methods=['GET'])
def get_admin_kpi():
    """Recupera KPI sistema per admin dashboard"""
    try:
        # Ordini attivi (non SPEDITO)
        all_orders = OrderManager.get_all_orders_dict()
        active_orders = [o for o in all_orders if o.get('status') != 'SPEDITO']
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
        completed_orders = [o for o in all_orders if o.get('status') == 'SPEDITO']
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

# ============ API FILE ============

@app.route('/api/extract-pdf-data', methods=['POST'])
def extract_pdf_data():
    """Estrae dati dal PDF caricato"""
    print("\n" + "="*70)
    print("[RECEIVE] /api/extract-pdf-data")
    print("="*70)

    try:
        print("[CHECK] Verifica file caricato...")
        if 'file' not in request.files:
            print("[ERROR] Nessun file caricato")
            return jsonify({'error': 'Nessun file caricato'}), 400

        file = request.files['file']
        print(f"   [OK] File ricevuto: {file.filename}")

        if file.filename == '':
            print("[ERROR] File non selezionato")
            return jsonify({'error': 'File non selezionato'}), 400

        if not file.filename.lower().endswith('.pdf'):
            print(f"[ERROR] File non è PDF: {file.filename}")
            return jsonify({'error': 'Solo file PDF sono supportati'}), 400

        print(f"   [OK] File è un PDF valido")

        # Salva temporaneamente e processa
        filepath = os.path.join(PDFS_FOLDER, file.filename)
        print(f"   [SAVE] {filepath}")
        file.save(filepath)
        print(f"   [OK] File salvato")
        
        # Estrae contenuto
        print(f"   -> Inizio estrazione PDF...")
        sys.stdout.flush()

        if _UNIVERSAL_EXTRACTOR_AVAILABLE:
            try:
                print(f"   -> Estrattore universale (Docling + Gemini)...")
                sys.stdout.flush()
                pdf_data = extract_universal(filepath)
                print(f"   OK Universale: {len(pdf_data.get('articoli', []))} articoli, estrattore={pdf_data.get('estrattore')}")
                sys.stdout.flush()
            except UniversalExtractionError as _ue_exc:
                print(f"   [FALLBACK] Universale non disponibile: {_ue_exc}")
                print(f"   -> Parser classici in uso...")
                sys.stdout.flush()
                pdf_data = extract_pdf_content(filepath)
                pdf_data["estrattore"] = "legacy"
        else:
            pdf_data = extract_pdf_content(filepath)
            pdf_data["estrattore"] = "legacy"

        print(f"\n   Estrazione completata!")
        print(f"   [CLIENT] {pdf_data.get('cliente', 'N/A')}")
        print(f"   [ITEMS] {len(pdf_data.get('articoli', []))} articoli")
        print("="*70 + "\n")
        sys.stdout.flush()
        
        return jsonify({
            'success': True,
            'data': pdf_data
        }), 200
        
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        print("="*70 + "\n")
        sys.stdout.flush()
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

# ============ PDF PROCESSING ============

@app.route('/api/process-pdfs', methods=['POST'])
def process_pdfs():
    """Processa tutti i PDFs dalla cartella ORDINI ed estrae dati"""
    try:
        ordini_folder = request.json.get('folder_path', '')
        if not ordini_folder:
            return jsonify({'error': 'Parametro folder_path obbligatorio'}), 400
        
        if not os.path.exists(ordini_folder):
            return jsonify({'error': f'Cartella non trovata: {ordini_folder}'}), 400
        
        # Raccogli tutti i PDF
        pdf_files = [f for f in os.listdir(ordini_folder) if f.lower().endswith('.pdf')]
        
        results = []
        errors = []
        
        for pdf_file in pdf_files:
            try:
                pdf_path = os.path.join(ordini_folder, pdf_file)
                
                # Estrai dati dal PDF
                pdf_data = extract_pdf_content(pdf_path)
                
                # Crea ordine nel database se i dati essenziali ci sono
                if pdf_data.get('numero_ordine') and pdf_data.get('articoli'):
                    order = OrderManager.create_order(
                        cliente=pdf_data.get('cliente', 'Sconosciuto'),
                        data_consegna=(pdf_data.get('data_consegna') or datetime.now().isoformat()),
                        articles=pdf_data.get('articoli', []),
                        note=f"Estratto da: {pdf_file}"
                    )
                    
                    results.append({
                        'pdf_file': pdf_file,
                        'order_id': order.id,
                        'cliente': order.cliente,
                        'numero_ordine': pdf_data.get('numero_ordine'),
                        'articoli_count': len(pdf_data.get('articoli', [])),
                        'status': 'success'
                    })
                else:
                    errors.append({
                        'pdf_file': pdf_file,
                        'error': 'Dati insufficienti per creare ordine'
                    })
                    
            except Exception as e:
                errors.append({
                    'pdf_file': pdf_file,
                    'error': str(e)[:100]
                })
        
        return jsonify({
            'success': True,
            'processed': len(results),
            'errors': len(errors),
            'results': results,
            'error_details': errors
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/extracted-orders', methods=['GET'])
def get_extracted_orders():
    """Recupera ordini estratti dai PDFs"""
    try:
        orders = OrderManager.get_all_orders_dict()
        
        return jsonify({
            'success': True,
            'count': len(orders),
            'orders': orders
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

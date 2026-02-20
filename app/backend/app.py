"""Flask Backend per Schedulatore Laser"""
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path

# Importa moduli locali
from .models import initialize_database
from .database import OrderManager
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
    """Serve welcome page"""
    return send_from_directory(FRONTEND_FOLDER, 'welcome.html')

@app.route('/ordini-estratti')
def ordini_dashboard():
    """Serve dashboard ordini estratti dai PDF"""
    return send_from_directory(FRONTEND_FOLDER, 'ordini_estratti.html')

@app.route('/<path:filename>')
def serve_frontend(filename):
    """Serve frontend files"""
    return send_from_directory(FRONTEND_FOLDER, filename)

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

# ============ API FASI ============

@app.route('/api/orders/<order_id>/phase/<phase>/start', methods=['POST'])
def start_phase(order_id, phase):
    """Inizia una fase di lavorazione"""
    try:
        data = request.get_json() or {}
        operatore = data.get('operatore', '')
        
        success = OrderManager.start_phase(order_id, phase, operatore)
        if success:
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
        
        result = OrderManager.complete_phase(order_id, phase, note)
        if result.get('success'):
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
        
        if not article_indices:
            return jsonify({'success': False, 'error': 'Nessun articolo selezionato'}), 400

        if not all(isinstance(i, int) and i >= 0 for i in article_indices):
            return jsonify({'success': False, 'error': 'Indici articoli non validi'}), 400
        
        result = OrderManager.complete_phase_partial(order_id, phase, article_indices, note)
        if result.get('success'):
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

# ============ API FILE ============

@app.route('/api/extract-pdf-data', methods=['POST'])
def extract_pdf_data():
    """Estrae dati dal PDF caricato"""
    print("\n" + "="*70)
    print("🔔 RICHIESTA RICEVUTA: /api/extract-pdf-data")
    print("="*70)
    
    try:
        print("📋 Verifica file caricato...")
        if 'file' not in request.files:
            print("❌ Errore: Nessun file caricato")
            return jsonify({'error': 'Nessun file caricato'}), 400
        
        file = request.files['file']
        print(f"   ✅ File ricevuto: {file.filename}")
        
        if file.filename == '':
            print("❌ Errore: File non selezionato")
            return jsonify({'error': 'File non selezionato'}), 400
        
        if not file.filename.lower().endswith('.pdf'):
            print(f"❌ Errore: File non è PDF: {file.filename}")
            return jsonify({'error': 'Solo file PDF sono supportati'}), 400
        
        print(f"   ✅ File è un PDF valido")
        
        # Salva temporaneamente e processa
        filepath = os.path.join(PDFS_FOLDER, file.filename)
        print(f"   → Salvataggio in: {filepath}")
        file.save(filepath)
        print(f"   ✅ File salvato")
        
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
        print(f"   → Cliente: {pdf_data.get('cliente', 'N/A')}")
        print(f"   → Articoli: {len(pdf_data.get('articoli', []))}")
        print("="*70 + "\n")
        sys.stdout.flush()
        
        return jsonify({
            'success': True,
            'data': pdf_data
        }), 200
        
    except Exception as e:
        print(f"\n❌ ERRORE: {str(e)}")
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

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
from .migrate_articles import ensure_articles_table, migrate_existing_orders

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

# Migrazione v1.1: assicura tabella articles e migra dati esistenti
ensure_articles_table()
migrate_existing_orders()

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

        # Normalizza articles: aggiungi required_phases di default se assenti
        articles = data.get('articles', [])
        for article in articles:
            if 'required_phases' not in article:
                article['required_phases'] = ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'SPEDIZIONE']

        order = OrderManager.create_order(
            cliente=data.get('cliente'),
            data_consegna=data.get('data_consegna'),
            articles=articles,
            required_phases=data.get('required_phases', ['LASER', 'PIEGA', 'SALDATURA']),
            preventivo_minuti=data.get('preventivo_minuti', 0),
            note=data.get('note', '')
        )

        # Recupera i record Article creati per includere gli UUID nella risposta
        from .models import Article, get_session
        session = get_session()
        try:
            article_records = session.query(Article).filter(
                Article.order_id == order.id
            ).order_by(Article.id).all()

            article_records_list = [
                {
                    'id': art.id,
                    'name': art.name,
                    'code': art.code,
                    'qty': art.qty,
                    'required_phases': art.required_phases
                }
                for art in article_records
            ]
        finally:
            session.close()

        return jsonify({
            'success': True,
            'order_id': order.id,
            'cliente': order.cliente,
            'data_consegna': order.data_consegna.isoformat(),
            'articles': order.articles,
            'total_quantity': order.total_quantity,
            'article_records': article_records_list   # Nuovo v1.1+: UUID degli articoli creati
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

@app.route('/api/orders/<order_id>/articles', methods=['GET'])
def get_order_articles(order_id):
    """
    Recupera i record Article di un ordine con stato per-articolo.

    Ritorna la lista degli articoli con UUID, fasi richieste, fasi completate,
    prossima fase e stato completamento.
    Usato da Phase 2 (Assegnazione Fasi UI) e Phase 3 (Viste Reparto).
    """
    try:
        details = OrderManager.get_order_details(order_id)
        if 'error' in details:
            return jsonify(details), 404
        return jsonify(details.get('articles', [])), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/<order_id>/articles/<article_id>/phases', methods=['PUT'])
def update_article_phases(order_id, article_id):
    """
    Aggiorna le fasi richieste per un articolo specifico.

    Body: {"required_phases": ["LASER", "PIEGA"]}

    Permette di cambiare le fasi solo se nessuno step per quell'articolo
    e gia stato avviato (timestamp_inizio IS NULL).
    Ritorna: {success, article_id, required_phases}
    """
    try:
        data = request.get_json()
        required_phases = data.get('required_phases')

        if not required_phases or not isinstance(required_phases, list):
            return jsonify({'success': False, 'error': 'required_phases deve essere una lista non vuota'}), 400

        from .models import Article, ProcessingStep, get_session
        from sqlalchemy.orm.attributes import flag_modified
        import uuid as uuid_module

        # Fasi canoniche valide
        VALID_PHASES = ['LASER', 'PIEGA', 'SALDATURA', 'PULIZIA', 'SPEDIZIONE']
        PHASE_ORDER = VALID_PHASES[:]

        # Normalizza: mantieni ordine canonico e filtra fasi valide
        normalized_phases = [p for p in PHASE_ORDER if p in required_phases]
        if not normalized_phases:
            return jsonify({'success': False, 'error': 'Nessuna fase valida fornita'}), 400

        session = get_session()
        try:
            # Verifica che l'articolo esista e appartenga all'ordine
            article = session.query(Article).filter(
                Article.id == article_id,
                Article.order_id == order_id
            ).first()

            if not article:
                return jsonify({'success': False, 'error': 'Articolo non trovato'}), 404

            # Verifica che nessuno step per questo articolo sia gia avviato
            started_steps = session.query(ProcessingStep).filter(
                ProcessingStep.article_id == article_id,
                ProcessingStep.timestamp_inizio.isnot(None)
            ).count()

            if started_steps > 0:
                return jsonify({
                    'success': False,
                    'error': 'Impossibile modificare le fasi: almeno una fase e gia stata avviata'
                }), 409

            # Rimuovi tutti i ProcessingStep esistenti per questo articolo
            session.query(ProcessingStep).filter(
                ProcessingStep.article_id == article_id
            ).delete()

            # Aggiorna le required_phases dell'articolo
            article.required_phases = normalized_phases
            flag_modified(article, 'required_phases')

            # Ricrea i ProcessingStep con le nuove fasi
            for phase in normalized_phases:
                step = ProcessingStep(
                    id=str(uuid_module.uuid4()),
                    order_id=order_id,
                    article_id=article_id,
                    fase=phase
                )
                session.add(step)

            session.commit()
            print(f"[API] Fasi articolo aggiornate: ordine={order_id} articolo={article_id} fasi={normalized_phases}")

            return jsonify({
                'success': True,
                'article_id': article_id,
                'required_phases': normalized_phases
            }), 200

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ============ API FASI ============

@app.route('/api/orders/<order_id>/phase/<phase>/start', methods=['POST'])
def start_phase(order_id, phase):
    """Inizia una fase di lavorazione (per tutti gli articoli o per articolo specifico)"""
    try:
        data = request.get_json() or {}
        operatore = data.get('operatore', '')
        article_id = data.get('article_id')  # Opzionale: v1.1+ per-articolo targeting

        success = OrderManager.start_phase(order_id, phase, operatore, article_id=article_id)
        if success:
            return jsonify({'success': True, 'phase': phase}), 200
        return jsonify({'success': False, 'error': 'Fase non trovata o gia iniziata'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/orders/<order_id>/phase/<phase>/complete', methods=['POST'])
def complete_phase(order_id, phase):
    """Completa una fase e ritorna prossimi articoli"""
    try:
        data = request.get_json() or {}
        note = data.get('note', '')
        article_id = data.get('article_id')  # Opzionale: v1.1+ per-articolo targeting

        result = OrderManager.complete_phase(order_id, phase, note, article_id=article_id)
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
        article_ids = data.get('article_ids', [])     # v1.1+: lista UUID articoli
        article_indices = data.get('article_indices', [])  # Legacy: lista indici interi

        note = data.get('note', '')

        # Almeno uno dei due parametri deve essere fornito
        if not article_ids and not article_indices:
            return jsonify({'success': False, 'error': 'Nessun articolo selezionato'}), 400

        if article_ids:
            # Modalita v1.1+: usa UUID direttamente
            result = OrderManager.complete_phase_partial(
                order_id, phase,
                article_ids=article_ids,
                note=note
            )
        else:
            # Modalita legacy: usa indici interi
            if not all(isinstance(i, int) and i >= 0 for i in article_indices):
                return jsonify({'success': False, 'error': 'Indici articoli non validi'}), 400

            result = OrderManager.complete_phase_partial(
                order_id, phase,
                article_indices=article_indices,
                note=note
            )

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
    """
    Recupera ordini per una fase specificata, con stato per-articolo (v1.1+).

    Per ogni articolo che ha la fase in required_phases e non l'ha ancora completata,
    include phase_status: 'in_attesa' | 'in_lavorazione' | 'completato'.
    Ordine risposta: articoli in_lavorazione prima di in_attesa per ogni ordine.
    Ordine ordini: data_consegna ascendente (urgenti prima), poi ordini con in_lavorazione prima.
    """
    try:
        orders = OrderManager.get_orders_by_phase(phase)

        result = []
        for order in orders:
            details = OrderManager.get_order_details(order.id)

            # Filtra articoli che hanno questa fase in required_phases
            # e non l'hanno ancora completata
            articles_in_phase = []
            for article in details['articles']:
                if phase not in article.get('required_phases', []):
                    continue
                if phase in article.get('completed_phases', []):
                    continue  # Già completato per questa fase — escludi

                # Determina lo stato per-articolo
                if phase in article.get('started_phases', []):
                    phase_status = 'in_lavorazione'
                else:
                    phase_status = 'in_attesa'

                articles_in_phase.append({
                    'article_id': article.get('article_id'),
                    'idx': article.get('idx'),
                    'name': article.get('name', ''),
                    'code': article.get('code', ''),
                    'qty': article.get('qty', 0),
                    'phase_status': phase_status
                })

            if not articles_in_phase:
                continue  # Salta ordini senza articoli in questa fase

            # Ordina articoli: in_lavorazione prima, poi in_attesa
            phase_order = {'in_lavorazione': 0, 'in_attesa': 1, 'completato': 2}
            articles_in_phase.sort(key=lambda a: phase_order.get(a['phase_status'], 99))

            # Flag per ordinamento ordini: ha almeno un articolo in_lavorazione?
            has_active = any(a['phase_status'] == 'in_lavorazione' for a in articles_in_phase)

            result.append({
                'id': order.id,
                'cliente': order.cliente,
                'total_quantity': order.total_quantity,
                'articles_in_phase': articles_in_phase,
                'articles_next_phase': articles_in_phase,  # Alias backward compat
                'data_consegna': order.data_consegna.isoformat(),
                '_has_active': has_active  # Campo interno per ordinamento
            })

        # Ordina ordini: data_consegna ascendente, poi ordini con articoli attivi prima
        result.sort(key=lambda o: (
            o['data_consegna'],
            0 if o['_has_active'] else 1
        ))

        # Rimuovi campo interno prima di serializzare
        for o in result:
            o.pop('_has_active', None)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ API FILE ============

@app.route('/api/extract-pdf-data', methods=['POST'])
def extract_pdf_data():
    """Estrae dati dal PDF caricato"""
    print("\n" + "="*70)
    print("RICHIESTA RICEVUTA: /api/extract-pdf-data")
    print("="*70)

    try:
        print("Verifica file caricato...")
        if 'file' not in request.files:
            print("Errore: Nessun file caricato")
            return jsonify({'error': 'Nessun file caricato'}), 400

        file = request.files['file']
        print(f"   File ricevuto: {file.filename}")

        if file.filename == '':
            print("Errore: File non selezionato")
            return jsonify({'error': 'File non selezionato'}), 400

        if not file.filename.lower().endswith('.pdf'):
            print(f"Errore: File non e PDF: {file.filename}")
            return jsonify({'error': 'Solo file PDF sono supportati'}), 400

        print(f"   File e un PDF valido")

        # Salva temporaneamente e processa
        filepath = os.path.join(PDFS_FOLDER, file.filename)
        print(f"   -> Salvataggio in: {filepath}")
        file.save(filepath)
        print(f"   File salvato")

        # Estrae contenuto
        print(f"   -> Inizio estrazione PDF...")
        sys.stdout.flush()

        pdf_data = extract_pdf_content(filepath)

        print(f"\n   Estrazione completata!")
        print(f"   -> Cliente: {pdf_data.get('cliente', 'N/A')}")
        print(f"   -> Articoli: {len(pdf_data.get('articoli', []))}")
        print("="*70 + "\n")
        sys.stdout.flush()

        return jsonify({
            'success': True,
            'data': pdf_data
        }), 200

    except Exception as e:
        print(f"\nERRORE: {str(e)}")
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

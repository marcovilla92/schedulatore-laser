from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Float, Text, JSON, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum
import os
import uuid

DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'scheduler.db')
DATABASE_URL = f'sqlite:///{DATABASE_PATH.replace(chr(92), "/")}'

Base = declarative_base()

class FaseCorrente(str, enum.Enum):
    LASER = "LASER"
    PIEGA = "PIEGA"
    SALDATURA = "SALDATURA"
    PULIZIA = "PULIZIA"
    COMPLETATO = "COMPLETATO"
    PARZIALE = "PARZIALE"

class Order(Base):
    """Modello Ordine con articoli tracciati per fase"""
    __tablename__ = 'orders'
    id = Column(String, primary_key=True)
    cliente = Column(String, nullable=False)
    numero_ordine = Column(String, nullable=True)  # NUOVO: numero ordine estratto/inserito dal PDF
    data_ricezione = Column(DateTime, default=datetime.utcnow, nullable=False)
    data_consegna = Column(DateTime, nullable=False)
    status = Column(String, default="RICEVUTO")
    fase_corrente = Column(String, default="LASER")  # LASER, PIEGA, SALDATURA, PULIZIA, COMPLETATO, PARZIALE
    operatore_assegnato = Column(String, ForeignKey('users.id'), nullable=True)  # Auto-assegnato da operator_clients
    prezzo_quotato = Column(Float, nullable=True)  # Prezzo quotato per calcolo margine

    note = Column(Text)
    files = relationship('OrderFile', back_populates='order', cascade='all, delete-orphan')
    processing_steps = relationship('ProcessingStep', back_populates='order', cascade='all, delete-orphan')
    notifications = relationship('OrderNotification', back_populates='order', cascade='all, delete-orphan')

class OrderFile(Base):
    __tablename__ = 'order_files'
    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey('orders.id'), nullable=False)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    file_type = Column(String)  # PDF, DXF
    upload_date = Column(DateTime, default=datetime.utcnow)
    order = relationship('Order', back_populates='files')

class ProcessingStep(Base):
    """Fase di lavorazione di un ordine — traccia tempo per fase"""
    __tablename__ = 'processing_steps'
    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey('orders.id'), nullable=False)
    fase = Column(String, nullable=False)  # LASER, PIEGA, SALDATURA, PULIZIA
    timestamp_inizio = Column(DateTime, nullable=True)  # NULL per LASER (no time tracking)
    timestamp_fine = Column(DateTime, nullable=True)
    operatore = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    fase_successiva = Column(String, nullable=True)  # Dove l'operatore ha mandato l'ordine dopo
    completamento_parziale = Column(Boolean, default=False)  # True = ordine non del tutto finito
    order = relationship('Order', back_populates='processing_steps')
    sessions = relationship('PhaseSession', back_populates='step', cascade='all, delete-orphan')

class PhaseSession(Base):
    """Sessione di lavoro su una fase — ogni avvio-pausa/completamento è una sessione"""
    __tablename__ = 'phase_sessions'
    id = Column(String, primary_key=True)
    step_id = Column(String, ForeignKey('processing_steps.id'), nullable=False)
    order_id = Column(String, ForeignKey('orders.id'), nullable=False)
    fase = Column(String, nullable=False)
    operatore = Column(String, nullable=True)
    timestamp_inizio = Column(DateTime, nullable=False)
    timestamp_fine = Column(DateTime, nullable=True)
    tipo_chiusura = Column(String, nullable=True)  # 'parziale' | 'totale' | None (aperta)
    note = Column(Text, nullable=True)
    step = relationship('ProcessingStep', back_populates='sessions')

class OrderNotification(Base):
    """Notifiche di completamento ordine"""
    __tablename__ = 'order_notifications'
    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey('orders.id'), nullable=False)
    tempi_totali = Column(String)  # formato "2h 30min"
    viewed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    order = relationship('Order', back_populates='notifications')

class User(Base):
    """Utenti del sistema con ruoli e permessi"""
    __tablename__ = 'users'
    id = Column(String, primary_key=True)  # es: 'mirko-laser'
    name = Column(String, nullable=False)  # 'Mirko Sandionigi'
    role = Column(String, nullable=False)  # 'Operaio Laser', 'Amministratore', ecc
    initials = Column(String)  # 'LV'
    phase = Column(String)  # 'LASER', 'PIEGA', 'SALDATURA', 'ALL'
    permissions = Column(JSON, default=list)  # ['overview', 'lavorazione', 'supervisione', 'archive']
    machines = Column(JSON, default=list)  # ['CNC 01', 'Laser CO₂']
    is_capo = Column(Boolean, default=False)  # True = capo officina, controllo totale
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class OperatorClient(Base):
    """Assegnazioni fisse operatore-cliente"""
    __tablename__ = 'operator_clients'
    id = Column(String, primary_key=True)
    operator_id = Column(String, ForeignKey('users.id'), nullable=False)
    client_name = Column(String, nullable=False)  # Nome cliente (match esatto)
    operator = relationship('User')

class PhaseDelegation(Base):
    """Deleghe di fase: operatore principale delega una fase a un collega"""
    __tablename__ = 'phase_delegations'
    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey('orders.id'), nullable=False)
    fase = Column(String, nullable=False)  # PIEGA, SALDATURA, PULIZIA
    operatore_principale = Column(String, ForeignKey('users.id'), nullable=False)
    operatore_delegato = Column(String, ForeignKey('users.id'), nullable=False)
    stato = Column(String, default='pending')  # pending, accepted, in_progress, completed, rejected
    delegata_da = Column(String, ForeignKey('users.id'), nullable=True)  # Chi ha creato la delega
    forzata = Column(Boolean, default=False)  # True = capo ha forzato senza accettazione
    data_delega = Column(DateTime, default=datetime.utcnow)
    scadenza = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    tempo_inizio_delegato = Column(DateTime, nullable=True)
    tempo_fine_delegato = Column(DateTime, nullable=True)
    durata_effettiva = Column(Integer, nullable=True)  # secondi
    note_delegato = Column(Text, nullable=True)
    order = relationship('Order')

class SupportRequest(Base):
    """Richieste di supporto: operatore invita collega a collaborare sull'intero ordine"""
    __tablename__ = 'support_requests'
    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey('orders.id'), nullable=False)
    operatore_principale = Column(String, ForeignKey('users.id'), nullable=False)
    operatore_supporto = Column(String, ForeignKey('users.id'), nullable=False)
    stato = Column(String, default='pending')  # pending, accepted, rejected, revoked
    forzata = Column(Boolean, default=False)
    data_richiesta = Column(DateTime, default=datetime.utcnow)
    data_risposta = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    order = relationship('Order')

class AuditLog(Base):
    """Log di audit per tracciare azioni degli utenti"""
    __tablename__ = 'audit_log'
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String, ForeignKey('users.id'), nullable=True)  # FK a users.id
    user_name = Column(String)  # Denormalizzato per query veloci
    action = Column(String, nullable=False)  # 'LOGIN', 'LOGOUT', 'START_PHASE', 'COMPLETE_PHASE', 'CREA_ORDINE'
    entity_type = Column(String)  # 'order', 'phase', 'user'
    entity_id = Column(String)  # order_id correlato
    detail = Column(Text)  # JSON stringificato con dettagli aggiuntivi
    ip_address = Column(String, nullable=True)

class Notification(Base):
    """Notifiche UI persisted - sistema tipo WhatsApp per supervisore"""
    __tablename__ = 'notifications'
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)  # Supervisore/Admin che riceve
    order_id = Column(String, ForeignKey('orders.id'), nullable=True)  # Ordine correlato
    title = Column(String, nullable=False)  # "Nuovo ordine", "Ordine completato", ecc
    message = Column(String, nullable=False)  # Testo notifica
    notification_type = Column(String, default='order')  # 'order', 'completion', 'alert'
    notification_category = Column(String, default='informativa')  # 'informativa', 'attiva', 'delega', 'urgente'
    is_read = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)  # Soft delete

# Configurazione database
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session():
    return SessionLocal()

def seed_users():
    """Inserisce gli utenti di default se non esistono e rimuove quelli vecchi"""
    session = SessionLocal()
    try:
        # Utenti reali del sistema
        default_users = [
            {
                'id': 'elena-impiegata',
                'name': 'Elena Colombo',
                'role': 'Impiegata',
                'initials': 'EC',
                'phase': None,
                'permissions': ['overview', 'supervisione'],
                'machines': []
            },
            {
                'id': 'paolo-responsabile',
                'name': 'Paolo Scola',
                'role': 'Capo Officina',
                'initials': 'PS',
                'phase': 'ALL',
                'is_capo': True,
                'permissions': ['overview', 'supervisione', 'lavorazione', 'archive'],
                'machines': ['Tutte']
            },
            {
                'id': 'stefano-responsabile',
                'name': 'Stefano Villa',
                'role': 'Capo Officina',
                'initials': 'SV',
                'phase': 'ALL',
                'is_capo': True,
                'permissions': ['overview', 'supervisione', 'lavorazione', 'archive'],
                'machines': ['Tutte']
            },
            {
                'id': 'mirko-laser',
                'name': 'Mirko Sandionigi',
                'role': 'Operaio Laser',
                'initials': 'MS',
                'phase': 'LASER',
                'permissions': ['overview', 'lavorazione'],
                'machines': ['Laser CO₂']
            },
            {
                'id': 'enzo-officina',
                'name': 'Enzo Masciari',
                'role': 'Operaio Officina',
                'initials': 'EM',
                'phase': 'OFFICINA',
                'permissions': ['overview', 'lavorazione'],
                'machines': []
            }
        ]

        # Rimuovi vecchi utenti fittizi
        valid_ids = [u['id'] for u in default_users]
        old_users = session.query(User).filter(User.id.notin_(valid_ids)).all()
        for old in old_users:
            session.delete(old)

        # Inserisci/aggiorna utenti reali
        for user_data in default_users:
            existing = session.query(User).filter(User.id == user_data['id']).first()
            if existing:
                for k, v in user_data.items():
                    if k != 'id':
                        setattr(existing, k, v)
            else:
                user = User(**user_data)
                session.add(user)

        session.commit()
        print("[OK] Seed users completato — 5 utenti reali")
    except Exception as e:
        session.rollback()
        print(f"[WARN] Seed users error: {e}")
    finally:
        session.close()

def initialize_database():
    """Crea le tabelle se non esistono e popola i dati di default"""
    Base.metadata.create_all(bind=engine)

    # Migrazione: aggiunge colonne tempo a phase_delegations se mancanti
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if 'phase_delegations' in insp.get_table_names():
        existing = [c['name'] for c in insp.get_columns('phase_delegations')]
        new_cols = {
            'tempo_inizio_delegato': 'DATETIME',
            'tempo_fine_delegato': 'DATETIME',
            'durata_effettiva': 'INTEGER',
            'note_delegato': 'TEXT',
        }
        with engine.connect() as conn:
            for col, col_type in new_cols.items():
                if col not in existing:
                    conn.execute(text(f'ALTER TABLE phase_delegations ADD COLUMN {col} {col_type}'))
                    print(f'[MIGRATION] Aggiunta colonna {col} a phase_delegations')
            conn.commit()

    # Migrazione: popola phase_sessions per ProcessingSteps esistenti
    if 'phase_sessions' in insp.get_table_names():
        with engine.connect() as conn:
            count = conn.execute(text('SELECT COUNT(*) FROM phase_sessions')).scalar()
            if count == 0:
                existing_steps = conn.execute(text(
                    'SELECT id, order_id, fase, operatore, timestamp_inizio, timestamp_fine, completamento_parziale '
                    'FROM processing_steps WHERE timestamp_inizio IS NOT NULL'
                )).fetchall()
                for step in existing_steps:
                    session_id = str(uuid.uuid4())
                    tipo = 'parziale' if step[6] else ('totale' if step[5] else None)
                    conn.execute(text(
                        'INSERT INTO phase_sessions (id, step_id, order_id, fase, operatore, '
                        'timestamp_inizio, timestamp_fine, tipo_chiusura) '
                        'VALUES (:id, :step_id, :order_id, :fase, :op, :ts_in, :ts_fin, :tipo)'
                    ), {
                        'id': session_id, 'step_id': step[0], 'order_id': step[1],
                        'fase': step[2], 'op': step[3], 'ts_in': step[4],
                        'ts_fin': step[5], 'tipo': tipo
                    })
                conn.commit()
                if existing_steps:
                    print(f'[MIGRATION] Create {len(existing_steps)} phase_sessions retroattive')

    # Migrazione: aggiunge notification_category a notifications se mancante
    if 'notifications' in insp.get_table_names():
        existing_notif = [c['name'] for c in insp.get_columns('notifications')]
        if 'notification_category' not in existing_notif:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN notification_category VARCHAR DEFAULT 'informativa'"))
                conn.commit()
                print('[MIGRATION] Aggiunta colonna notification_category a notifications')

    seed_users()

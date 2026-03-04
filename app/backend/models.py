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
    id = Column(String, primary_key=True)  # es: 'luigi-laser'
    name = Column(String, nullable=False)  # 'Luigi Verdi'
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
    is_read = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)  # Soft delete

# Configurazione database
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session():
    return SessionLocal()

def seed_users():
    """Inserisce gli utenti di default se non esistono (idempotente)"""
    session = SessionLocal()
    try:
        # Lista degli utenti di default
        default_users = [
            {
                'id': 'luigi-laser',
                'name': 'Luigi Verdi',
                'role': 'Operaio Laser',
                'initials': 'LV',
                'phase': 'LASER',
                'permissions': ['overview', 'lavorazione'],
                'machines': ['CNC 01', 'Laser CO₂']
            },
            {
                'id': 'andrea-officina',
                'name': 'Andrea Bianchi',
                'role': 'Operaio Officina',
                'initials': 'AB',
                'phase': 'OFFICINA',
                'permissions': ['overview', 'lavorazione'],
                'machines': []
            },
            {
                'id': 'sara-officina',
                'name': 'Sara Neri',
                'role': 'Operaio Officina',
                'initials': 'SN',
                'phase': 'OFFICINA',
                'permissions': ['overview', 'lavorazione'],
                'machines': []
            },
            {
                'id': 'mario-officina',
                'name': 'Mario Russo',
                'role': 'Operaio Officina',
                'initials': 'MRu',
                'phase': 'OFFICINA',
                'permissions': ['overview', 'lavorazione'],
                'machines': []
            },
            {
                'id': 'paolo-officina',
                'name': 'Paolo Colombo',
                'role': 'Operaio Officina',
                'initials': 'PC',
                'phase': 'OFFICINA',
                'permissions': ['overview', 'lavorazione'],
                'machines': []
            },
            {
                'id': 'luca-officina',
                'name': 'Luca Ferrari',
                'role': 'Operaio Officina',
                'initials': 'LF',
                'phase': 'OFFICINA',
                'permissions': ['overview', 'lavorazione'],
                'machines': []
            },
            {
                'id': 'giulia-impiegata',
                'name': 'Giulia Gallo',
                'role': 'Impiegata',
                'initials': 'GG',
                'phase': None,
                'permissions': ['overview', 'supervisione'],
                'machines': []
            },
            {
                'id': 'marco-capo',
                'name': 'Marco Rossi',
                'role': 'Capo Officina',
                'initials': 'MR',
                'phase': 'ALL',
                'is_capo': True,
                'permissions': ['overview', 'supervisione', 'lavorazione', 'archive'],
                'machines': ['Tutte']
            },
            {
                'id': 'admin',
                'name': 'Amministratore',
                'role': 'Amministratore',
                'initials': 'AD',
                'phase': 'ALL',
                'is_capo': True,
                'permissions': ['overview', 'supervisione', 'lavorazione', 'archive'],
                'machines': ['Tutte']
            }
        ]

        # Inserisci utenti se non esistono (idempotente con merge)
        for user_data in default_users:
            existing = session.query(User).filter(User.id == user_data['id']).first()
            if not existing:
                user = User(**user_data)
                session.add(user)

        session.commit()
        print("[OK] Seed users completato")
    except Exception as e:
        session.rollback()
        print(f"[WARN] Seed users error: {e}")
    finally:
        session.close()

def initialize_database():
    """Crea le tabelle se non esistono e popola i dati di default"""
    Base.metadata.create_all(bind=engine)
    seed_users()

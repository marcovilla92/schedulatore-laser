from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, JSON, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum
import os
import uuid

DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'scheduler.db')
DATABASE_URL = f'sqlite:///{DATABASE_PATH.replace(chr(92), "/")}'

Base = declarative_base()

class OrderStatus(str, enum.Enum):
    RICEVUTO = "RICEVUTO"
    LASER_COMPLETATO = "LASER_COMPLETATO"
    PIEGA_COMPLETATA = "PIEGA_COMPLETATA"
    SALDATURA_COMPLETATA = "SALDATURA_COMPLETATA"
    PULIZIA_COMPLETATA = "PULIZIA_COMPLETATA"
    SPEDITO = "SPEDITO"

class ProcessingPhase(str, enum.Enum):
    LASER = "LASER"
    PIEGA = "PIEGA"
    SALDATURA = "SALDATURA"
    PULIZIA = "PULIZIA"
    SPEDIZIONE = "SPEDIZIONE"

class Order(Base):
    """Modello Ordine con articoli tracciati per fase"""
    __tablename__ = 'orders'
    id = Column(String, primary_key=True)
    cliente = Column(String, nullable=False)
    data_ricezione = Column(DateTime, default=datetime.utcnow, nullable=False)
    data_consegna = Column(DateTime, nullable=False)
    status = Column(String, default=OrderStatus.RICEVUTO.value)
    required_phases = Column(JSON, default=lambda: ['LASER', 'PIEGA', 'SALDATURA'])
    preventivo_minuti = Column(Integer, default=0)
    total_quantity = Column(Integer, default=0)
    
    # ✅ NUOVO: Articoli con fasi richieste
    # Formato: [{"name": "Staffa A", "code": "SA-001", "qty": 50, "required_phases": ["LASER", "PIEGA", "SALDATURA"]}, ...]
    articles = Column(JSON, default=list)
    
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
    """Fase di lavorazione di un ordine con tracking per articolo"""
    __tablename__ = 'processing_steps'
    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey('orders.id'), nullable=False)
    fase = Column(String, nullable=False)  # LASER, PIEGA, SALDATURA, ecc
    timestamp_inizio = Column(DateTime, nullable=True)
    timestamp_fine = Column(DateTime, nullable=True)
    operatore = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    # ✅ NUOVO: Traccia articoli completati per questa fase (lista di indici)
    completed_articles = Column(JSON, default=list)  # Es: [0, 1, 3] = articoli con indice 0, 1, 3 completati
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

# Configurazione database
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session():
    return SessionLocal()

def initialize_database():
    """Crea le tabelle se non esistono"""
    Base.metadata.create_all(bind=engine)

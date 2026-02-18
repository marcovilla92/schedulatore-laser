"""Backend initialization"""
from .app import app
from .models import initialize_database

__all__ = ['app', 'initialize_database']

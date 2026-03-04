#!/usr/bin/env python3
"""Test integrazione Docling"""

try:
    from docling.document_converter import DocumentConverter
    print("✅ Docling installato e funzionante!")
    
    # Verifica disponibilità
    converter = DocumentConverter()
    print("✅ DocumentConverter inizializzato correttamente")
    
except ImportError as e:
    print(f"❌ Errore importazione: {e}")
except Exception as e:
    print(f"⚠️ Errore: {e}")

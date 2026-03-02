#!/usr/bin/env python
"""Open mockup in default browser"""

import webbrowser
import os
from pathlib import Path

# Get the absolute path to the mockup file
mockup_file = Path(__file__).parent / "mockup_order_prioritization.html"
mockup_url = mockup_file.as_uri()

print(f"Opening mockup: {mockup_url}")
print()
print("📋 Descrizione del Mockup:")
print("=" * 70)
print("Il mockup mostra:")
print("  1. PRIMA (sinistra): Ordini in ordine arbitrario")
print("  2. DOPO (destra): Ordini ordinati per urgenza con badge colorati")
print("  3. Sistema 3-tier: Verde (≥7 giorni), Giallo (3-7), Rosso (<3 o scaduto)")
print("  4. Algoritmo EDD e vantaggi della prioritizzazione")
print("=" * 70)
print()

# Open in default browser
webbrowser.open(mockup_url)

print("✓ Mockup aperto nel browser predefinito")

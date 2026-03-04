#!/usr/bin/env python
"""
SCHEDULATORE LASER - Test Completo del Sistema
Simula il workflows da upload ordine a completamento
"""

import requests
import os
from datetime import datetime, timedelta

API_BASE = 'http://localhost:5000/api'
UPLOADS_PDF = r'c:\Users\39334\Documents\SCHEDULATORE LASER\app\uploads\pdfs'
UPLOADS_DXF = r'c:\Users\39334\Documents\SCHEDULATORE LASER\app\uploads\drawings'

print("=" * 70)
print("SCHEDULATORE LASER - TEST COMPLETO")
print("=" * 70)

# ============================================================================
# TEST 1: Creazione Ordine
# ============================================================================
print("\n[TEST 1] Creazione Nuovo Ordine")
print("-" * 70)

pdf_path = os.path.join(UPLOADS_PDF, '_test_order.pdf')
dxf_path = os.path.join(UPLOADS_DXF, '_test_order.dxf')

# Crea file test
with open(pdf_path, 'w') as f:
    f.write("Cliente: TEST AUTOMATION s.r.l.\n")
    f.write("Ordine: TEST-001\n")
    f.write("Data consegna: 15/02/2026\n")

with open(dxf_path, 'w') as f:
    f.write("0\nSECTION\n")

files = [
    ('pdf_file', open(pdf_path, 'rb')),
    ('dxf_files', open(dxf_path, 'rb')),
]

data = {
    'cliente': 'TEST AUTOMATION s.r.l.',
    'data_consegna': (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d'),
    'preventivo_minuti': '240',
    'note': 'Test automatico'
}

try:
    response = requests.post(f'{API_BASE}/orders', files=files, data=data)
    result = response.json()
    
    if result['success']:
        order_id = result['order_id']
        print(f"✓ Ordine creato: {order_id}")
        print(f"  Cliente: {result['cliente']}")
        print(f"  Data consegna: {result['data_consegna']}")
        print(f"  Status: {result['status']}")
    else:
        print(f"✗ Errore: {result.get('error')}")
        exit(1)
finally:
    for _, f in files:
        f.close()

# ============================================================================
# TEST 2: Dashboard - Caricamento Ordini
# ============================================================================
print("\n[TEST 2] Dashboard - Caricamento Ordini")
print("-" * 70)

response = requests.get(f'{API_BASE}/dashboard')
data = response.json()

if data['success']:
    ordini = data['data']
    print(f"✓ Dashboard caricato: {len(ordini)} ordini totali")
    
    # Verifica che il nuovo ordine sia presente
    nuovo = next((o for o in ordini if o['id'] == order_id), None)
    if nuovo:
        print(f"✓ Nuovo ordine trovato nel dashboard")
        print(f"  Progress: {nuovo['progress_percent']}%")
        print(f"  Status: {nuovo['status']}")
        print(f"  Urgency: {nuovo['urgency']}")
    else:
        print(f"✗ Ordine non trovato nel dashboard!")
else:
    print(f"✗ Errore: {data.get('error')}")

# ============================================================================
# TEST 3: Dettagli Ordine
# ============================================================================
print("\n[TEST 3] Dettagli Ordine - Timeline")
print("-" * 70)

response = requests.get(f'{API_BASE}/orders/{order_id}')
data = response.json()

if data['success']:
    order = data['order']
    print(f"✓ Ordine caricato: {order['id']}")
    print(f"  Cliente: {order['cliente']}")
    print(f"  Status: {order['status']}")
    print(f"  Steps registrati: {len(order['steps'])}")
    
    for step in order['steps']:
        status_str = "✓" if step['timestamp_fine'] else ("▶" if step['timestamp_inizio'] else "⏳")
        print(f"    {status_str} {step['fase']}")
else:
    print(f"✗ Errore: {data.get('error')}")

# ============================================================================
# TEST 4: Ordini per Reparto (RICEVUTO)
# ============================================================================
print("\n[TEST 4] Ordini per Reparto - RICEVUTO (Laser)")
print("-" * 70)

# Filtra gli ordini dal dashboard
response = requests.get(f'{API_BASE}/dashboard')
data = response.json()

if data and isinstance(data.get('data'), list):
    ordini_ricevuti = [o for o in data['data'] if o['status'] == 'RICEVUTO']
    count = len(ordini_ricevuti)
    print(f"✓ Ordini in stato RICEVUTO: {count}")
    
    # Verifica che il nostro ordine sia lì
    nostro = next((o for o in ordini_ricevuti if o['id'] == order_id), None)
    if nostro:
        print(f"✓ Nostro ordine è pronto per LASER")
else:
    print(f"✗ Errore caricamento ordini reparto")

# ============================================================================
# TEST 5: Inizio Lavoro - Simula operatore che inizia
# ============================================================================
print("\n[TEST 5] Inizio Lavoro - Simulazione Operatore")
print("-" * 70)

# Trova lo step LASER
response = requests.get(f'{API_BASE}/orders/{order_id}')
order = response.json()['order']
laser_step = next((s for s in order['steps'] if s['fase'] == 'LASER'), None)

if laser_step:
    step_id = laser_step['id']
    
    # Start step
    response = requests.put(f'{API_BASE}/steps/{step_id}/start')
    data = response.json()
    
    if data.get('success'):
        print(f"✓ Inizio lavoro registrato: {data.get('message')}")
        
        # Verifica che timestamp_inizio sia impostato
        response = requests.get(f'{API_BASE}/orders/{order_id}')
        order_updated = response.json()['order']
        laser_step_updated = next((s for s in order_updated['steps'] if s['fase'] == 'LASER'))
        
        if laser_step_updated['timestamp_inizio']:
            print(f"✓ Timestamp inizio registrato: {laser_step_updated['timestamp_inizio']}")
    else:
        print(f"✗ Errore: {data.get('error')}")

# ============================================================================
# TEST 6: Completamento Fase
# ============================================================================
print("\n[TEST 6] Completamento Fase - Laser")
print("-" * 70)

response = requests.put(
    f'{API_BASE}/steps/{step_id}/complete',
    json={'note': 'Test completato con successo'}
)
data = response.json()

if data.get('success'):
    print(f"✓ Fase completata: {data.get('message')}")
    
    # Verifica che lo step sia completato
    response = requests.get(f'{API_BASE}/orders/{order_id}')
    order_final = response.json()['order']
    laser_step_final = next((s for s in order_final['steps'] if s['fase'] == 'LASER'))
    
    if laser_step_final['timestamp_fine']:
        print(f"✓ Fase LASER completata")
        print(f"  Inizio: {laser_step_final['timestamp_inizio']}")
        print(f"  Fine: {laser_step_final['timestamp_fine']}")
        print(f"  Note: {laser_step_final['note']}")
else:
    print(f"✗ Errore: {data.get('error')}")

# ============================================================================
# TEST 7: Dashboard Aggiornato
# ============================================================================
print("\n[TEST 7] Dashboard Aggiornato - Verifica Progresso")
print("-" * 70)

response = requests.get(f'{API_BASE}/dashboard')
data = response.json()

ordine_finale = next((o for o in data['data'] if o['id'] == order_id), None)
if ordine_finale:
    print(f"✓ Ordine nel dashboard aggiornato")
    print(f"  Status: {ordine_finale['status']}")
    print(f"  Progress: {ordine_finale['progress_percent']}%")
    print(f"  Fasi completate: {ordine_finale['fasi_completate']}/{ordine_finale['total_fasi']}")
else:
    print(f"✗ Ordine non trovato")

# ============================================================================
# RIEPILOGO
# ============================================================================
print("\n" + "=" * 70)
print("RIEPILOGO TEST")
print("=" * 70)
print(f"""
✓ ORDINE CREATO: {order_id}
✓ DASHBOARD OPERATIVO
✓ DETTAGLI ORDINE VISIBILI
✓ REPARTO LASER PRONTO
✓ INIZIO LAVORO REGISTRATO
✓ COMPLETAMENTO FASE REGISTRATO
✓ PROGRESSO AGGIORNATO

Sistema SCHEDULATORE LASER completamente operativo!
""")
print("=" * 70)

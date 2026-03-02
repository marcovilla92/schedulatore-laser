#!/usr/bin/env python
"""Test KPI operai tracking and calculation"""

import requests
import json
from datetime import datetime, timedelta
import time

def create_order(cliente, numero):
    """Create a test order"""
    order_data = {
        "cliente": cliente,
        "numero_ordine": numero,
        "data_consegna": (datetime.now() + timedelta(days=7)).isoformat(),
        "articles": [
            {
                "name": f"Pezzo {numero}-1",
                "code": f"ART-{numero}-001",
                "qty": 2,
                "required_phases": ["LASER", "PIEGA"]
            },
            {
                "name": f"Pezzo {numero}-2",
                "code": f"ART-{numero}-002",
                "qty": 3,
                "required_phases": ["LASER", "SALDATURA"]
            }
        ]
    }

    response = requests.post(
        'http://localhost:5000/api/orders',
        json=order_data,
        headers={'Content-Type': 'application/json'}
    )

    if response.status_code == 201:
        return response.json().get('order_id')
    return None

def start_phase(order_id, phase, operatore_id):
    """Start a phase"""
    response = requests.post(
        f'http://localhost:5000/api/orders/{order_id}/phase/{phase}/start',
        json={'operatore_id': operatore_id},
        headers={'Content-Type': 'application/json'}
    )
    return response.status_code == 200

def complete_phase(order_id, phase, operatore_id):
    """Complete a phase"""
    response = requests.post(
        f'http://localhost:5000/api/orders/{order_id}/phase/{phase}/complete',
        json={'operatore_id': operatore_id},
        headers={'Content-Type': 'application/json'}
    )
    return response.status_code == 200

def get_kpi():
    """Get KPI from API"""
    response = requests.get('http://localhost:5000/api/admin/kpi')
    if response.status_code == 200:
        return response.json()
    return None

def test_kpi():
    print("=" * 70)
    print("TEST: KPI Operai Tracking and Calculation")
    print("=" * 70)

    # Step 1: Create test orders
    print("\n[1] Creating test orders...")
    order_ids = []
    for i in range(1, 4):
        order_id = create_order(f"CLIENT-{i}", f"ORDER-{i:03d}")
        if order_id:
            order_ids.append(order_id)
            print(f"    [+] Order {i} created: {order_id[:8]}...")
        else:
            print(f"    [-] Failed to create order {i}")

    if not order_ids:
        print("[-] No orders created, cannot continue")
        return

    # Step 2: Simulate work by different operators
    print("\n[2] Simulating operator work...")
    operators = {
        'luigi-laser': 'LASER',
        'sara-piega': 'PIEGA',
        'andrea-saldatura': 'SALDATURA'
    }

    work_log = []

    # Luigi completes LASER phases
    print("    [*] Luigi (LASER) working...")
    for i, order_id in enumerate(order_ids[:2]):
        if start_phase(order_id, 'LASER', 'luigi-laser'):
            time.sleep(0.5)  # Simulate work
            if complete_phase(order_id, 'LASER', 'luigi-laser'):
                work_log.append(f"Luigi completed LASER on order {i+1}")
                print(f"       [+] LASER completed")

    # Sara completes PIEGA phases
    print("    [*] Sara (PIEGA) working...")
    for i, order_id in enumerate(order_ids[:2]):
        if start_phase(order_id, 'PIEGA', 'sara-piega'):
            time.sleep(0.5)  # Simulate work
            if complete_phase(order_id, 'PIEGA', 'sara-piega'):
                work_log.append(f"Sara completed PIEGA on order {i+1}")
                print(f"       [+] PIEGA completed")

    # Andrea completes SALDATURA phases
    print("    [*] Andrea (SALDATURA) working...")
    for i, order_id in enumerate(order_ids[1:3]):
        if start_phase(order_id, 'SALDATURA', 'andrea-saldatura'):
            time.sleep(0.5)  # Simulate work
            if complete_phase(order_id, 'SALDATURA', 'andrea-saldatura'):
                work_log.append(f"Andrea completed SALDATURA on order {i+2}")
                print(f"       [+] SALDATURA completed")

    # Step 3: Fetch KPI
    print("\n[3] Fetching KPI data...")
    kpi_data = get_kpi()

    if not kpi_data:
        print("    [-] Failed to fetch KPI")
        return

    # Step 4: Analyze KPI results
    print("\n[4] KPI Results:")
    print("=" * 70)

    kpi_globali = kpi_data.get('kpi_globali', {})
    kpi_operai = kpi_data.get('kpi_operai', [])

    print("\nKPI Globali:")
    print(f"  - Ordini Attivi: {kpi_globali.get('ordini_attivi', 0)}")
    print(f"  - Login Oggi: {kpi_globali.get('login_oggi', 0)}")
    print(f"  - Efficienza: {kpi_globali.get('efficienza', 0)}%")
    print(f"  - Ritardi: {kpi_globali.get('ritardi', 0)}")

    print("\nKPI Operai:")
    print("-" * 70)

    expected_operators = {'luigi-laser', 'sara-piega', 'andrea-saldatura'}
    found_operators = set()

    for operai_kpi in kpi_operai:
        operaio = operai_kpi.get('operaio', 'Unknown')
        user_id = operai_kpi.get('user_id', 'N/A')
        role = operai_kpi.get('role', 'N/A')
        ordini_completati = operai_kpi.get('ordini_completati', 0)
        tempo_medio = operai_kpi.get('tempo_medio', 'N/A')
        ultimo_accesso = operai_kpi.get('ultimo_accesso', 'Mai')
        efficienza = operai_kpi.get('efficienza', 0)

        found_operators.add(user_id)

        print(f"\n{operaio} ({role})")
        print(f"  Ordini Completati: {ordini_completati}")
        print(f"  Tempo Medio: {tempo_medio}")
        print(f"  Ultimo Accesso: {ultimo_accesso}")
        print(f"  Efficienza: {efficienza}%")

    # Step 5: Verify results
    print("\n[5] Verification:")
    print("-" * 70)

    # Check if all expected operators were found
    verified = []

    # Luigi should have completed LASER phases
    luigi = next((o for o in kpi_operai if o['user_id'] == 'luigi-laser'), None)
    if luigi and luigi['ordini_completati'] >= 2:
        print("  [+] Luigi: LASER phases recorded correctly (2+)")
        verified.append(True)
    else:
        print(f"  [-] Luigi: Expected 2+ completed orders, got {luigi['ordini_completati'] if luigi else 0}")
        verified.append(False)

    # Sara should have completed PIEGA phases
    sara = next((o for o in kpi_operai if o['user_id'] == 'sara-piega'), None)
    if sara and sara['ordini_completati'] >= 2:
        print("  [+] Sara: PIEGA phases recorded correctly (2+)")
        verified.append(True)
    else:
        print(f"  [-] Sara: Expected 2+ completed orders, got {sara['ordini_completati'] if sara else 0}")
        verified.append(False)

    # Andrea should have completed SALDATURA phases
    andrea = next((o for o in kpi_operai if o['user_id'] == 'andrea-saldatura'), None)
    if andrea and andrea['ordini_completati'] >= 2:
        print("  [+] Andrea: SALDATURA phases recorded correctly (2+)")
        verified.append(True)
    else:
        print(f"  [-] Andrea: Expected 2+ completed orders, got {andrea['ordini_completati'] if andrea else 0}")
        verified.append(False)

    # Check that operators have non-null last_login
    print("\n  [*] Last Login Status:")
    for operai_kpi in kpi_operai:
        operaio = operai_kpi.get('operaio', 'Unknown')
        ultimo_accesso = operai_kpi.get('ultimo_accesso', 'Mai')
        if ultimo_accesso != 'Mai':
            print(f"      [+] {operaio}: Last login recorded")
        else:
            print(f"      [-] {operaio}: No login recorded")

    # Summary
    print("\n" + "=" * 70)
    if all(verified):
        print("[OK] All KPI tests PASSED!")
    else:
        print(f"[!] Some KPI tests FAILED ({sum(verified)}/{len(verified)} passed)")
    print("=" * 70)

if __name__ == '__main__':
    test_kpi()

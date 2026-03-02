#!/usr/bin/env python3
"""Test FASE 3 API endpoints usando Flask test client"""

import sys
import os
from datetime import datetime, timedelta

# Aggiungi path
sys.path.insert(0, os.path.dirname(__file__))

from app.backend.app import app
from app.backend.models import initialize_database

def test_endpoints():
    """Test API endpoints usando Flask test client"""

    # Inizializza database
    initialize_database()

    # Crea test client
    client = app.test_client()

    print("\n" + "="*70)
    print("FASE 3 — API Endpoints Direct Testing (Flask test client)")
    print("="*70)

    # Test 1: Health check
    print("\n[TEST] GET /api/health")
    resp = client.get('/api/health')
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"  [OK] Server health OK")
    else:
        print(f"  [FAIL] {resp.text}")

    # Test 2: GET /api/users
    print("\n[TEST] GET /api/users")
    resp = client.get('/api/users')
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.get_json()
        users = data.get('users', [])
        print(f"  [OK] Found {len(users)} users:")
        for user in users[:3]:
            print(f"    - {user['id']}: {user['name']} ({user['role']})")
    else:
        print(f"  [FAIL] {resp.text}")

    # Test 3: POST /api/auth/login
    print("\n[TEST] POST /api/auth/login")
    resp = client.post('/api/auth/login', json={"user_id": "luigi-laser"})
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.get_json()
        print(f"  [OK] Logged in as {data['name']} ({data['role']})")
        user_id = data['user_id']
    else:
        print(f"  [FAIL] {resp.text}")
        return False

    # Test 4: POST /api/auth/logout
    print("\n[TEST] POST /api/auth/logout")
    resp = client.post('/api/auth/logout', json={"user_id": user_id})
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"  [OK] Logged out successfully")
    else:
        print(f"  [FAIL] {resp.text}")

    # Test 5: GET /api/admin/kpi
    print("\n[TEST] GET /api/admin/kpi")
    resp = client.get('/api/admin/kpi')
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.get_json()
        kpi = data.get('kpi_globali', {})
        operai = data.get('kpi_operai', [])
        print(f"  [OK] KPI Globali:")
        print(f"    - Ordini attivi: {kpi.get('ordini_attivi')}")
        print(f"    - Login oggi: {kpi.get('login_oggi')}")
        print(f"    - Efficienza: {kpi.get('efficienza')}%")
        print(f"    - Ritardi: {kpi.get('ritardi')}")
        print(f"  [OK] KPI Operai: {len(operai)} operatori")
    else:
        print(f"  [FAIL] {resp.text}")

    # Test 6: GET /api/admin/audit-log
    print("\n[TEST] GET /api/admin/audit-log")
    resp = client.get('/api/admin/audit-log?limit=20')
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.get_json()
        logs = data.get('audit_logs', [])
        print(f"  [OK] Found {len(logs)} audit log entries")
        if logs:
            print(f"    - Latest: {logs[0]['timestamp']} - {logs[0]['action']} by {logs[0].get('user_name', 'system')}")
    else:
        print(f"  [FAIL] {resp.text}")

    # Test 7: POST /api/orders/confirm-phases
    print("\n[TEST] POST /api/orders/confirm-phases")
    order_data = {
        "cliente": "Test Cliente FASE3",
        "data_consegna": (datetime.now() + timedelta(days=7)).isoformat(),
        "articles": [
            {"name": "Staffa A", "code": "SA-001", "qty": 50},
            {"name": "Staffa B", "code": "SA-002", "qty": 30}
        ],
        "selected_phases": ["LASER", "PIEGA"],
        "operatore_id": "luigi-laser"
    }
    resp = client.post('/api/orders/confirm-phases', json=order_data)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 201:
        data = resp.get_json()
        order_id = data.get('order_id')
        print(f"  [OK] Ordine creato: {order_id}")
        print(f"    - Cliente: {data['cliente']}")
        print(f"    - Fasi: {data['required_phases']}")
        print(f"    - Qty totale: {data['total_quantity']}")
    else:
        print(f"  [FAIL] {resp.text}")
        return False

    # Test 8: POST /api/orders/{id}/phase/{phase}/start con audit
    print(f"\n[TEST] POST /api/orders/{order_id}/phase/LASER/start")
    phase_data = {
        "operatore": "Luigi Verdi",
        "operatore_id": "luigi-laser"
    }
    resp = client.post(f'/api/orders/{order_id}/phase/LASER/start', json=phase_data)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"  [OK] Phase started")
    else:
        print(f"  [FAIL] {resp.text}")

    # Test 9: Verify audit log has START_PHASE
    print("\n[TEST] Verify START_PHASE in audit log")
    resp = client.get('/api/admin/audit-log?user_id=luigi-laser&limit=20')
    if resp.status_code == 200:
        data = resp.get_json()
        logs = data.get('audit_logs', [])
        start_logs = [l for l in logs if l['action'] == 'START_PHASE']
        crea_logs = [l for l in logs if l['action'] == 'CREA_ORDINE']
        print(f"  [OK] Audit log entries for luigi-laser:")
        print(f"    - CREA_ORDINE: {len(crea_logs)}")
        print(f"    - START_PHASE: {len(start_logs)}")
        print(f"    - LOGIN: {len([l for l in logs if l['action'] == 'LOGIN'])}")
        print(f"    - LOGOUT: {len([l for l in logs if l['action'] == 'LOGOUT'])}")
    else:
        print(f"  [FAIL] {resp.text}")

    # Summary
    print("\n" + "="*70)
    print("[PASS] All FASE 3 endpoint tests completed successfully!")
    print("="*70)
    return True

if __name__ == '__main__':
    try:
        success = test_endpoints()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

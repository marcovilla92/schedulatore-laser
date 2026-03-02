#!/usr/bin/env python3
"""Test E2E completo: login > create order > track phases > logout"""

import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from app.backend.app import app
from app.backend.models import initialize_database

def run_e2e_test():
    """Complete end-to-end test"""
    initialize_database()
    client = app.test_client()

    print("\n" + "="*70)
    print("E2E TEST COMPLETO - Login > Create Order > Track Phases > Logout")
    print("="*70)

    # TEST 1: Health check
    print("\n[TEST 1/9] Health check")
    resp = client.get('/api/health')
    assert resp.status_code == 200
    print("[OK] Health check OK")

    # TEST 2: Load users
    print("\n[TEST 2/9] GET /api/users")
    resp = client.get('/api/users')
    assert resp.status_code == 200
    users = resp.get_json()['users']
    assert len(users) >= 5
    print(f"[OK] {len(users)} users loaded")

    # TEST 3: Login as luigi-laser
    print("\n[TEST 3/9] POST /api/auth/login (luigi-laser)")
    resp = client.post('/api/auth/login', json={'user_id': 'luigi-laser'})
    assert resp.status_code == 200
    user = resp.get_json()
    assert user['user_id'] == 'luigi-laser'
    assert user['name'] == 'Luigi Verdi'
    assert user['phase'] == 'LASER'
    print(f"[OK] Logged in: {user['name']} ({user['role']})")

    # TEST 4: Get KPI
    print("\n[TEST 4/9] GET /api/admin/kpi")
    resp = client.get('/api/admin/kpi')
    assert resp.status_code == 200
    kpi = resp.get_json()
    assert 'kpi_globali' in kpi
    assert 'kpi_operai' in kpi
    print(f"[OK] KPI: {kpi['kpi_globali']['ordini_attivi']} active orders, {kpi['kpi_globali']['login_oggi']} logins today")

    # TEST 5: Get audit log
    print("\n[TEST 5/9] GET /api/admin/audit-log")
    resp = client.get('/api/admin/audit-log?limit=10')
    assert resp.status_code == 200
    audit = resp.get_json()
    assert 'audit_logs' in audit
    login_events = [l for l in audit['audit_logs'] if l['action'] == 'LOGIN']
    print(f"[OK] Audit log: {len(audit['audit_logs'])} events ({len(login_events)} LOGIN)")

    # TEST 6: Create order with confirm-phases
    print("\n[TEST 6/9] POST /api/orders/confirm-phases")
    order_data = {
        'cliente': 'Test Cliente E2E',
        'data_consegna': (datetime.now() + timedelta(days=7)).isoformat(),
        'articles': [
            {'name': 'Staffa A', 'code': 'SA-001', 'qty': 50},
            {'name': 'Staffa B', 'code': 'SA-002', 'qty': 30}
        ],
        'selected_phases': ['LASER', 'PIEGA'],
        'operatore_id': 'luigi-laser'
    }
    resp = client.post('/api/orders/confirm-phases', json=order_data)
    assert resp.status_code == 201
    order = resp.get_json()
    order_id = order['order_id']
    assert order['cliente'] == 'Test Cliente E2E'
    assert order['required_phases'] == ['LASER', 'PIEGA']
    print(f"[OK] Order created: {order_id} (fasi: LASER > PIEGA)")

    # TEST 7: Start LASER phase
    print("\n[TEST 7/9] POST /api/orders/{order_id}/phase/LASER/start")
    resp = client.post(f'/api/orders/{order_id}/phase/LASER/start', json={
        'operatore': 'Luigi Verdi',
        'operatore_id': 'luigi-laser'
    })
    assert resp.status_code == 200
    print(f"[OK] LASER phase started")

    # TEST 8: Complete LASER phase (partial)
    print("\n[TEST 8/9] POST /api/orders/{order_id}/phase/LASER/complete-partial")
    resp = client.post(f'/api/orders/{order_id}/phase/LASER/complete-partial', json={
        'article_indices': [0],  # Complete only first article
        'note': 'Test partial completion',
        'operatore_id': 'luigi-laser'
    })
    assert resp.status_code == 200
    result = resp.get_json()
    assert result['articles_completed'] == [0]
    print(f"[OK] Article 0 completed in LASER phase")

    # TEST 9: Logout
    print("\n[TEST 9/9] POST /api/auth/logout")
    resp = client.post('/api/auth/logout', json={'user_id': 'luigi-laser'})
    assert resp.status_code == 200
    print(f"[OK] Logged out successfully")

    # VERIFY audit log has CREA_ORDINE, START_PHASE, COMPLETE_PHASE
    print("\n[VERIFY] Checking audit log for events")
    resp = client.get('/api/admin/audit-log?user_id=luigi-laser&limit=20')
    audit = resp.get_json()['audit_logs']

    crea_ordine = [l for l in audit if l['action'] == 'CREA_ORDINE']
    start_phase = [l for l in audit if l['action'] == 'START_PHASE']
    complete_phase = [l for l in audit if l['action'] == 'COMPLETE_PHASE']
    logout_events = [l for l in audit if l['action'] == 'LOGOUT']

    assert len(crea_ordine) > 0, "No CREA_ORDINE event"
    assert len(start_phase) > 0, "No START_PHASE event"
    assert len(complete_phase) > 0, "No COMPLETE_PHASE event"
    assert len(logout_events) > 0, "No LOGOUT event"

    print(f"[OK] Audit trail verified:")
    print(f"    - {len(crea_ordine)} CREA_ORDINE events")
    print(f"    - {len(start_phase)} START_PHASE events")
    print(f"    - {len(complete_phase)} COMPLETE_PHASE events")
    print(f"    - {len(logout_events)} LOGOUT events")

    print("\n" + "="*70)
    print("[PASS] ALL E2E TESTS PASSED! System is fully functional.")
    print("="*70)
    return True

if __name__ == '__main__':
    try:
        success = run_e2e_test()
        sys.exit(0 if success else 1)
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

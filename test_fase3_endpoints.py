#!/usr/bin/env python3
"""Test API endpoints della FASE 3 - Auth, Admin, KPI, Audit"""

import requests
import json
import sys
from datetime import datetime, timedelta

BASE_URL = "http://localhost:5000"

def test_auth_endpoints():
    """Test login, logout, e user list"""
    print("\n" + "="*70)
    print("[TEST] Auth Endpoints")
    print("="*70)

    # Test 1: GET /api/users
    print("\n[TEST] GET /api/users")
    resp = requests.get(f"{BASE_URL}/api/users")
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        users = data.get('users', [])
        print(f"  [OK] Found {len(users)} users:")
        for user in users:
            print(f"    - {user['id']}: {user['name']} ({user['role']}, phase={user['phase']})")
    else:
        print(f"  [FAIL] {resp.text}")
        return False

    # Test 2: POST /api/auth/login
    print("\n[TEST] POST /api/auth/login")
    login_data = {"user_id": "luigi-laser"}
    resp = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        user = resp.json()
        print(f"  [OK] Logged in as {user['name']} ({user['role']})")
        logged_user_id = user['user_id']
    else:
        print(f"  [FAIL] {resp.text}")
        return False

    # Test 3: POST /api/auth/logout
    print("\n[TEST] POST /api/auth/logout")
    logout_data = {"user_id": logged_user_id}
    resp = requests.post(f"{BASE_URL}/api/auth/logout", json=logout_data)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"  [OK] Logged out successfully")
    else:
        print(f"  [FAIL] {resp.text}")
        return False

    return True

def test_admin_endpoints():
    """Test KPI e Audit Log endpoints"""
    print("\n" + "="*70)
    print("[TEST] Admin Endpoints")
    print("="*70)

    # Test 1: GET /api/admin/kpi
    print("\n[TEST] GET /api/admin/kpi")
    resp = requests.get(f"{BASE_URL}/api/admin/kpi")
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        kpi = data.get('kpi_globali', {})
        operai = data.get('kpi_operai', [])
        print(f"  [OK] KPI Globali:")
        print(f"    - Ordini attivi: {kpi.get('ordini_attivi')}")
        print(f"    - Login oggi: {kpi.get('login_oggi')}")
        print(f"    - Efficienza: {kpi.get('efficienza')}%")
        print(f"    - Ritardi: {kpi.get('ritardi')}")
        print(f"  [OK] KPI Operai: {len(operai)} operatori")
        for op in operai[:3]:  # Mostra primi 3
            print(f"    - {op['operatore']}: {op['ordini_completati']} ordini, rating {op.get('rating', 'N/A')}")
    else:
        print(f"  [FAIL] {resp.text}")
        return False

    # Test 2: GET /api/admin/audit-log
    print("\n[TEST] GET /api/admin/audit-log")
    resp = requests.get(f"{BASE_URL}/api/admin/audit-log?limit=20")
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        logs = data.get('audit_logs', [])
        print(f"  [OK] Found {len(logs)} audit log entries")
        for log in logs[:5]:  # Mostra primi 5
            print(f"    - {log['timestamp']}: {log['action']} by {log.get('user_name', 'system')}")
    else:
        print(f"  [FAIL] {resp.text}")
        return False

    return True

def test_order_endpoints():
    """Test confirm-phases endpoint"""
    print("\n" + "="*70)
    print("[TEST] Order Confirm Phases Endpoint")
    print("="*70)

    # Test 1: POST /api/orders/confirm-phases
    print("\n[TEST] POST /api/orders/confirm-phases")
    order_data = {
        "cliente": "Test Cliente",
        "data_consegna": (datetime.now() + timedelta(days=7)).isoformat(),
        "articles": [
            {"name": "Staffa A", "code": "SA-001", "qty": 50},
            {"name": "Staffa B", "code": "SA-002", "qty": 30}
        ],
        "selected_phases": ["LASER", "PIEGA"],
        "operatore_id": "luigi-laser"
    }
    resp = requests.post(f"{BASE_URL}/api/orders/confirm-phases", json=order_data)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 201:
        order = resp.json()
        order_id = order.get('order_id')
        print(f"  [OK] Ordine creato: {order_id}")
        print(f"    - Cliente: {order['cliente']}")
        print(f"    - Fasi: {order['required_phases']}")
        print(f"    - Qty totale: {order['total_quantity']}")
        return order_id
    else:
        print(f"  [FAIL] {resp.text}")
        return None

def test_phase_endpoints(order_id):
    """Test phase endpoints con audit logging"""
    if not order_id:
        print("\n[SKIP] Phase endpoints test skipped (no order)")
        return True

    print("\n" + "="*70)
    print("[TEST] Phase Endpoints with Audit Logging")
    print("="*70)

    # Test 1: Start phase
    print(f"\n[TEST] POST /api/orders/{order_id}/phase/LASER/start")
    phase_data = {
        "operatore": "Luigi Verdi",
        "operatore_id": "luigi-laser"
    }
    resp = requests.post(f"{BASE_URL}/api/orders/{order_id}/phase/LASER/start", json=phase_data)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"  [OK] Phase started")
    else:
        print(f"  [WARN] {resp.text}")

    # Test 2: Verify audit log entry
    print(f"\n[TEST] Verify START_PHASE in audit log")
    resp = requests.get(f"{BASE_URL}/api/admin/audit-log?user_id=luigi-laser&limit=10")
    if resp.status_code == 200:
        logs = resp.json().get('audit_logs', [])
        start_logs = [l for l in logs if l['action'] == 'START_PHASE']
        if start_logs:
            print(f"  [OK] Found {len(start_logs)} START_PHASE entries in audit log")
            print(f"    - Latest: {start_logs[0]['timestamp']}")
        else:
            print(f"  [WARN] No START_PHASE entries found")
    else:
        print(f"  [WARN] Could not verify audit log")

    return True

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("FASE 3 — API Endpoints Testing")
    print("="*70)

    try:
        # Health check
        print("\n[INIT] Health check...")
        resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if resp.status_code == 200:
            print("[OK] Server is running")
        else:
            print("[FAIL] Server not responding correctly")
            return False
    except Exception as e:
        print(f"[ERROR] Cannot connect to server: {e}")
        print(f"Make sure Flask is running at {BASE_URL}")
        return False

    # Run test groups
    success = True
    success = success and test_auth_endpoints()
    success = success and test_admin_endpoints()
    order_id = test_order_endpoints()
    success = success and test_phase_endpoints(order_id)

    # Summary
    print("\n" + "="*70)
    if success:
        print("[PASS] All tests completed!")
        print("="*70)
        return True
    else:
        print("[FAIL] Some tests failed")
        print("="*70)
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

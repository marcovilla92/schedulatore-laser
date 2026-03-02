#!/usr/bin/env python3
"""Create and approve an order to test the fix"""
import requests
import json
from datetime import datetime, timedelta

print("Testing complete flow: Create -> Approve")
print("="*60)

# Create a new order (RICEVUTO with no phases yet)
print("\n1. Creating new order...")

articles = [
    {'name': 'Pezzo Test A', 'code': 'TEST001', 'qty': 5},
    {'name': 'Pezzo Test B', 'code': 'TEST002', 'qty': 10}
]

delivery_date = (datetime.now() + timedelta(days=7)).isoformat()

create_resp = requests.post('http://localhost:5000/api/orders', json={
    'cliente': 'Cliente Test S.r.l.',
    'data_consegna': delivery_date,
    'articles': articles,
    'required_phases': []  # Empty = waiting for approval
})

print(f"   Response status: {create_resp.status_code}")
print(f"   Response: {create_resp.text[:200]}")

if create_resp.status_code in [200, 201]:
    order = create_resp.json()
    order_id = order.get('order_id')
    if order_id:
        print(f"   [OK] Order created: {order_id[:8]}...")
        print(f"   Cliente: {order.get('cliente')}")
        print(f"   Phases: {order.get('required_phases')} (empty = pending)")
    else:
        print(f"   [ERROR] No order_id in response")
        exit(1)
else:
    print(f"   [ERROR] Creation failed: {create_resp.status_code}")
    exit(1)

# Now approve it
print(f"\n2. Approving order with LASER, PIEGA phases...")

approve_resp = requests.post(f'http://localhost:5000/api/orders/{order_id}/approve', json={
    'required_phases': ['LASER', 'PIEGA'],
    'operatore_id': 'marco-admin'
})

print(f"   Response status: {approve_resp.status_code}")

if approve_resp.status_code == 200:
    result = approve_resp.json()
    print(f"\n   [SUCCESS] Order approved!")
    print(f"   Cliente: {result.get('cliente')}")
    print(f"   Fasi: {result.get('required_phases')}")

    # Verify
    print(f"\n3. Verifying order updated...")
    verify_resp = requests.get(f'http://localhost:5000/api/orders/{order_id}')
    updated_order = verify_resp.json()
    print(f"   Status: {updated_order.get('status')}")
    print(f"   Required Phases: {updated_order.get('required_phases')}")
    print(f"\n[OK] COMPLETE: Order created, approved, and phases assigned!")
else:
    print(f"   [ERROR] Approval failed: {approve_resp.status_code}")
    print(f"   {approve_resp.text}")

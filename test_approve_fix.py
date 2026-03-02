#!/usr/bin/env python3
"""Test approve endpoint fix"""
import requests
import json

print("Testing approve endpoint fix...")
print("="*60)

# Get a pending order
resp = requests.get('http://localhost:5000/api/orders')
orders = resp.json()

pending = [o for o in orders if o.get('status') == 'RICEVUTO' and not o.get('required_phases')]

if not pending:
    print("[INFO] No pending orders to test")
    exit(1)

order = pending[0]
order_id = order.get('id')

print(f"Testing with order: {order_id[:8]}...")
print(f"  Cliente: {order.get('cliente')}")
print(f"  Articoli: {len(order.get('articles', []))}")

# Try to approve
print("\nApproving order with phases: LASER, PIEGA...")
resp = requests.post(f'http://localhost:5000/api/orders/{order_id}/approve', json={
    'required_phases': ['LASER', 'PIEGA'],
    'operatore_id': 'marco-admin'
})

print(f"\nResponse status: {resp.status_code}")
print(f"Response body: {resp.text[:200]}")

if resp.status_code == 200:
    result = resp.json()
    print("\n[SUCCESS] Order approved!")
    print(f"  Numero Ordine: {result.get('numero_ordine')}")
    print(f"  Fasi: {result.get('required_phases')}")

    # Verify it updated
    resp2 = requests.get(f'http://localhost:5000/api/orders/{order_id}')
    updated = resp2.json()
    print(f"\nVerification - Order phases now: {updated.get('required_phases')}")
else:
    print(f"\n[ERROR] Approval failed")
    if resp.status_code == 500:
        print("  This was the bug - /approve endpoint failed")

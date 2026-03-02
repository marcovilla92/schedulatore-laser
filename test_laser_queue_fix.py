#!/usr/bin/env python3
"""Test the laser queue fix"""
import requests
from datetime import datetime, timedelta

print("Testing LASER queue after fix...")
print("="*60)

# Create a new order
print("\n1. Creating order...")
articles = [
    {'name': 'Pezzo A', 'code': 'TEST-A', 'qty': 5},
    {'name': 'Pezzo B', 'code': 'TEST-B', 'qty': 10}
]

delivery_date = (datetime.now() + timedelta(days=7)).isoformat()

resp = requests.post('http://localhost:5000/api/orders', json={
    'cliente': 'Test Queue S.r.l.',
    'data_consegna': delivery_date,
    'articles': articles,
    'required_phases': []
})

if resp.status_code in [200, 201]:
    order = resp.json()
    order_id = order.get('order_id')
    print(f"   [OK] Order created: {order_id[:8]}...")
else:
    print(f"   [ERROR] {resp.status_code}")
    exit(1)

# Approve with LASER + PIEGA
print(f"\n2. Approving with LASER+PIEGA...")
resp = requests.post(f'http://localhost:5000/api/orders/{order_id}/approve', json={
    'required_phases': ['LASER', 'PIEGA'],
    'operatore_id': 'marco-admin'
})

if resp.status_code == 200:
    print(f"   [OK] Approved")
else:
    print(f"   [ERROR] {resp.status_code}: {resp.text}")
    exit(1)

# Check LASER queue
print(f"\n3. Checking LASER queue...")
resp = requests.get('http://localhost:5000/api/phase/LASER/orders')

if resp.status_code == 200:
    laser_orders = resp.json()
    print(f"   Orders in LASER queue: {len(laser_orders)}")

    # Look for our order
    found = False
    for o in laser_orders:
        if o['id'] == order_id:
            found = True
            print(f"   [SUCCESS] Order found in LASER queue!")
            print(f"     Cliente: {o['cliente']}")
            print(f"     Articles: {len(o['articles_next_phase'])}")
            for a in o['articles_next_phase']:
                print(f"       - {a['name']} ({a['code']}): next={a['next_phase']}")
            break

    if not found:
        print(f"   [FAILED] Order NOT found in LASER queue")
        print(f"   Available orders:")
        for o in laser_orders[:3]:
            print(f"     - {o['id'][:8]}... ({o['cliente']})")
else:
    print(f"   [ERROR] {resp.status_code}")

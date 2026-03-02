#!/usr/bin/env python3
"""Complete end-to-end test from scratch"""
import requests
from datetime import datetime, timedelta

print("COMPLETE E2E TEST")
print("="*70)

# Step 1: Create order
print("\n[STEP 1] Create order...")
articles = [
    {'name': 'Piastra acciaio', 'code': 'PIA-001', 'qty': 5},
    {'name': 'Angolare 50x50', 'code': 'ANG-050', 'qty': 10}
]

delivery = (datetime.now() + timedelta(days=7)).isoformat()

resp = requests.post('http://localhost:5000/api/orders', json={
    'cliente': 'MeccanicaSrl Test',
    'data_consegna': delivery,
    'articles': articles,
    'required_phases': []
})

if resp.status_code not in [200, 201]:
    print(f"  FAILED: {resp.status_code}")
    print(resp.text)
    exit(1)

order = resp.json()
order_id = order.get('order_id')
print(f"  [OK] Order created: {order_id[:8]}...")

# Step 2: Check order in DB (before approval)
print("\n[STEP 2] Check order before approval...")
resp = requests.get(f'http://localhost:5000/api/orders/{order_id}')
order_before = resp.json()
print(f"  Status: {order_before.get('status')}")
print(f"  Required phases: {order_before.get('required_phases')}")
print(f"  Articles[0].required_phases: {order_before['articles'][0].get('required_phases')}")

# Step 3: Approve order with LASER
print("\n[STEP 3] Approve order with LASER phase...")
resp = requests.post(f'http://localhost:5000/api/orders/{order_id}/approve', json={
    'required_phases': ['LASER'],
    'operatore_id': 'luigi-laser'
})

if resp.status_code != 200:
    print(f"  FAILED: {resp.status_code}")
    print(resp.text)
    exit(1)

print(f"  [OK] Approved")

# Step 4: Check order after approval
print("\n[STEP 4] Check order after approval...")
resp = requests.get(f'http://localhost:5000/api/orders/{order_id}')
order_after = resp.json()
print(f"  Status: {order_after.get('status')}")
print(f"  Required phases: {order_after.get('required_phases')}")
print(f"  Articles[0].required_phases: {order_after['articles'][0].get('required_phases')}")

# Step 5: Check LASER queue
print("\n[STEP 5] Check LASER queue...")
resp = requests.get('http://localhost:5000/api/phase/LASER/orders')

if resp.status_code != 200:
    print(f"  FAILED: {resp.status_code}")
    exit(1)

laser_queue = resp.json()
print(f"  Total orders in LASER queue: {len(laser_queue)}")

# Find our order
found = False
for o in laser_queue:
    if o['id'] == order_id:
        found = True
        print(f"  [OK] Order FOUND in queue!")
        print(f"    Articles ready for LASER:")
        for a in o['articles_next_phase']:
            print(f"      - {a['name']} ({a['code']}): qty={a['qty']}")
        break

if not found:
    print(f"  [FAIL] Order NOT in queue!")
    print(f"  Available orders in queue:")
    for o in laser_queue[:2]:
        print(f"    - {o['id'][:8]}... ({o['cliente']})")

# Step 6: Start LASER phase
if found:
    print("\n[STEP 6] Start LASER phase...")
    resp = requests.post(f'http://localhost:5000/api/orders/{order_id}/phase/LASER/start', json={
        'operatore_id': 'luigi-laser'
    })

    if resp.status_code in [200, 201]:
        print(f"  [OK] LASER phase started")
    else:
        print(f"  FAILED: {resp.status_code}")
        print(resp.text)

print("\n" + "="*70)
print("TEST SUMMARY:")
print(f"  Order ID: {order_id[:8]}...")
print(f"  Status: {'[OK] PASSED' if found else '[FAIL] FAILED'}")
if not found:
    print("\nDEBUG INFO:")
    print(f"  Check that articles have required_phases assigned")
    print(f"  Check that ProcessingSteps were created")

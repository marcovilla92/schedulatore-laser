#!/usr/bin/env python3
"""Debug why orders don't show in laser.html"""
import requests

print("Debugging laser.html empty orders...")
print("="*70)

# Get all orders
resp = requests.get('http://localhost:5000/api/orders')
all_orders = resp.json()
print(f"\n1. Total orders in DB: {len(all_orders)}")

# Get LASER queue
resp = requests.get('http://localhost:5000/api/phase/LASER/orders')
laser_queue = resp.json()
print(f"2. Orders in LASER queue (API): {len(laser_queue)}")

if laser_queue:
    print("\n3. LASER queue orders:")
    for o in laser_queue[:2]:
        print(f"   - {o['id'][:8]}... ({o['cliente']})")
        print(f"     Articles: {len(o.get('articles_next_phase', []))}")
        for a in o.get('articles_next_phase', [])[:1]:
            print(f"       - {a['name']}: next_phase={a.get('next_phase')}")

# Check if any order has timestamp_inizio
print("\n4. Checking processing steps...")
if all_orders:
    order = all_orders[-1]
    print(f"\n   Last order: {order['id'][:8]}...")
    print(f"   Cliente: {order['cliente']}")
    print(f"   Status: {order['status']}")

    steps = order.get('processing_steps', [])
    print(f"   Processing steps: {len(steps)}")

    for step in steps:
        print(f"\n     Phase: {step.get('fase')}")
        print(f"     timestamp_inizio: {step.get('timestamp_inizio')}")
        print(f"     timestamp_fine: {step.get('timestamp_fine')}")
        print(f"     operatore: {step.get('operatore')}")

print("\n" + "="*70)
print("ANALYSIS:")
if len(laser_queue) > 0:
    print("  Orders ARE in LASER queue (API)")
    print("  But laser.html shows nothing")
    print("  Problem: Frontend rendering issue")
else:
    print("  No orders in LASER queue")
    print("  Problem: Orders don't have timestamp_inizio set")
    print("  Solution: Need to call /api/orders/<id>/phase/LASER/start")

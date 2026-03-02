#!/usr/bin/env python3
"""Debug order status and processing steps"""
import requests

print("Debugging order status...")
print("="*60)

# Get all orders
resp = requests.get('http://localhost:5000/api/orders')
orders = resp.json()

print(f"\nTotal orders: {len(orders)}")

if orders:
    order = orders[0]
    order_id = order.get('id')

    print(f"\nLast order details:")
    print(f"  ID: {order_id[:8]}...")
    print(f"  Cliente: {order.get('cliente')}")
    print(f"  Status: {order.get('status')}")
    print(f"  Required Phases: {order.get('required_phases')}")
    print(f"  Articles: {len(order.get('articles', []))} articoli")

    print(f"\nProcessing Steps:")
    processing_steps = order.get('processing_steps', [])
    print(f"  Total: {len(processing_steps)}")
    for step in processing_steps:
        print(f"    - {step.get('fase')}: {step}")

    # Try to get laser queue
    print(f"\nChecking LASER queue...")
    resp_laser = requests.get('http://localhost:5000/api/phase/LASER/orders')
    if resp_laser.status_code == 200:
        laser_orders = resp_laser.json()
        print(f"  Orders in LASER queue: {len(laser_orders)}")
        for o in laser_orders[:2]:
            print(f"    - {o.get('id')[:8]}... ({o.get('cliente')})")
    else:
        print(f"  ERROR: {resp_laser.status_code}")
        print(f"  {resp_laser.text}")

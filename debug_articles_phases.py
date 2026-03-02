#!/usr/bin/env python3
"""Debug articles phases after approval"""
import requests

print("Debugging articles phases...")
print("="*60)

# Get last order
resp = requests.get('http://localhost:5000/api/orders')
orders = resp.json()

if orders:
    order = orders[-1]
    print(f"\nLast order:")
    print(f"  ID: {order['id'][:8]}...")
    print(f"  Cliente: {order['cliente']}")
    print(f"  Order required_phases: {order.get('required_phases')}")
    print(f"\n  Articles:")
    for i, art in enumerate(order.get('articles', [])):
        print(f"    [{i}] {art.get('name')} ({art.get('code')})")
        print(f"        required_phases: {art.get('required_phases')}")
        print(f"        qty: {art.get('qty')}")

    # Get details
    print(f"\n  Order details (from /api/orders/{order['id']}/details):")
    resp_details = requests.get(f"http://localhost:5000/api/orders/{order['id']}/details")
    if resp_details.status_code == 200:
        details = resp_details.json()
        print(f"  Articles in details:")
        for i, art in enumerate(details.get('articles', [])[:2]):
            print(f"    [{i}] {art.get('name')}")
            print(f"        required_phases: {art.get('required_phases')}")
            print(f"        next_phase: {art.get('next_phase')}")
    else:
        print(f"  ERROR: {resp_details.status_code}")

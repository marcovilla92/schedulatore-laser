#!/usr/bin/env python3
"""Check order status via API"""
import requests

print("Checking order status in database via API...")
print("="*60)

# Get all orders
resp = requests.get('http://localhost:5000/api/orders')
orders = resp.json()

# Filter for DECA orders
deca_orders = [o for o in orders if 'DECA' in o.get('cliente', '')]
print(f"Total DECA orders: {len(deca_orders)}")

# Check status
ricevuto_no_phases = [o for o in orders if o.get('status') == 'RICEVUTO' and not o.get('required_phases')]
print(f"Total RICEVUTO orders with NO phases: {len(ricevuto_no_phases)}")

print("\nSample DECA order status:")
if deca_orders:
    order = deca_orders[0]
    print(f"  Numero: {order.get('numero_ordine')}")
    print(f"  Status: {order.get('status')}")
    print(f"  Required Phases: {order.get('required_phases')}")

print("\nSample pending order (waiting for phase approval):")
if ricevuto_no_phases:
    order = ricevuto_no_phases[0]
    print(f"  Numero: {order.get('numero_ordine')}")
    print(f"  Cliente: {order.get('cliente')}")
    print(f"  Status: {order.get('status')}")
    print(f"  Required Phases: {order.get('required_phases')}")
    print(f"\n  This order SHOULD appear on approva-ordine.html")
else:
    print("  [INFO] No pending orders waiting for phase approval")
    print("  These would be new orders created via carica-ordine.html")

print("\nApprova-ordine page shows only RICEVUTO orders with NO required_phases")
print("This is correct - they are waiting for supervisor to select phases")

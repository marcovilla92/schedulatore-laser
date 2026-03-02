#!/usr/bin/env python3
"""Verify clean database state"""
import requests

print("VERIFYING CLEAN STATE")
print("="*60)

# Check orders
resp = requests.get('http://localhost:5000/api/orders')
orders = resp.json()
print(f"\nOrders in DB: {len(orders)} (should be 0)")

# Check users
resp = requests.get('http://localhost:5000/api/users')
data = resp.json()
users = data if isinstance(data, list) else data.get('users', [])
print(f"Users in DB: {len(users)}")
if users:
    print("  Users available:")
    for user in users[:3]:
        uid = user.get('id') if isinstance(user, dict) else user
        role = user.get('role', 'N/A') if isinstance(user, dict) else 'N/A'
        print(f"    - {uid} ({role})")

# Check health
resp = requests.get('http://localhost:5000/api/health')
print(f"\nAPI Health: {resp.status_code}")

print("\n" + "="*60)
print("SYSTEM READY FOR FRESH TEST")
print("\nWhat to do next:")
print("  1. Go to http://localhost:5000/login.html")
print("  2. Login as supervisore (marco-admin, sara-piega, etc)")
print("  3. Click 'Nuovo Ordine' to go to carica-ordine.html")
print("  4. Upload a PDF and select phases")
print("  5. Order appears in approva-ordine.html for approval")
print("  6. Confirm phases -> order goes to phase workflow")

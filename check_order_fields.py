#!/usr/bin/env python3
import requests
resp = requests.get('http://localhost:5000/api/orders')
orders = resp.json()
if orders:
    print("Sample order keys:")
    for key in orders[0].keys():
        print(f"  - {key}: {str(orders[0][key])[:50]}")

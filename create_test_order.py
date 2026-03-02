#!/usr/bin/env python
"""Create a test order for E2E testing"""

import requests
import json
from datetime import datetime, timedelta

def create_test_order():
    """Create a test order via API"""

    # Create order data
    order_data = {
        "cliente": "TEST CLIENTE",
        "numero_ordine": "TEST-001",
        "data_consegna": (datetime.now() + timedelta(days=7)).isoformat(),
        "articles": [
            {
                "name": "Pezzo 1",
                "code": "ART-001",
                "qty": 5,
                "required_phases": ["LASER", "PIEGA"]
            },
            {
                "name": "Pezzo 2",
                "code": "ART-002",
                "qty": 3,
                "required_phases": ["LASER", "SALDATURA"]
            }
        ]
    }

    try:
        response = requests.post(
            'http://localhost:5000/api/orders',
            json=order_data,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            result = response.json()
            print(f"[+] Test order created: {result.get('id')}")
            print(f"[+] Response: {json.dumps(result, indent=2)}")
            return result
        else:
            print(f"[-] Error: {response.status_code}")
            print(f"[-] Response: {response.text}")
            return None
    except Exception as e:
        print(f"[-] Exception: {e}")
        return None

if __name__ == '__main__':
    print("[*] Creating test order...")
    create_test_order()

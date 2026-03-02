#!/usr/bin/env python
"""Debug: Check what the auth/login endpoint returns for marco-admin"""

import requests
import json

BASE_URL = 'http://localhost:5000'

print("\n" + "="*70)
print("DEBUG: Testing auth/login response for marco-admin")
print("="*70)

# Test login endpoint
print("\n[1] Sending login request for marco-admin...")
try:
    resp = requests.post(
        f'{BASE_URL}/api/auth/login',
        json={'user_id': 'marco-admin'},
        timeout=5
    )
    print(f"    [+] Status: {resp.status_code}")

    data = resp.json()
    print(f"    [+] Response received")
    print(f"\n[2] Full response data:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    if 'permissions' in data:
        print(f"\n[3] Permissions check:")
        perms = data.get('permissions', [])
        print(f"    Permissions: {perms}")
        print(f"    Type: {type(perms)}")
        print(f"    Has 'archive': {'archive' in perms}")
        print(f"    Has 'supervisione': {'supervisione' in perms}")
    else:
        print("\n    [-] 'permissions' key NOT in response!")

except Exception as e:
    print(f"    [-] Error: {e}")

print("\n" + "="*70 + "\n")

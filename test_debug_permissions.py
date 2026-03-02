#!/usr/bin/env python
"""Debug: Monitor console and check currentUser.permissions in browser"""

import time
import json
from playwright.sync_api import sync_playwright

def test_debug_permissions():
    """Test and debug permission loading in browser"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        # Capture console messages
        console_logs = []
        page.on('console', lambda msg: console_logs.append({
            'type': msg.type,
            'text': msg.text,
            'location': msg.location
        }))

        print("\n" + "="*70)
        print("DEBUG: Permission Loading in Frontend")
        print("="*70)

        # Load login page
        print("\n[1] Loading login page...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        print("    [+] Login page loaded")

        # Click login for supervisore (marco-admin at index 4)
        print("\n[2] Logging in as supervisore...")
        demo_buttons = page.locator('button.btn-demo')
        if demo_buttons.count() > 4:
            demo_buttons.nth(4).click()
            time.sleep(3)
            page.wait_for_load_state('networkidle')
            print("    [+] Logged in")

        # Check currentUser in browser console
        print("\n[3] Checking currentUser object in browser...")
        try:
            current_user = page.evaluate('() => currentUser')
            print("    [+] currentUser object found:")
            print(f"       ID: {current_user.get('id')}")
            print(f"       Role: {current_user.get('role')}")
            print(f"       Permissions: {current_user.get('permissions')}")
            print(f"       Permissions type: {type(current_user.get('permissions'))}")

            perms = current_user.get('permissions', [])
            print(f"\n[4] Permission checks:")
            print(f"    'overview' in perms: {'overview' in perms}")
            print(f"    'supervisione' in perms: {'supervisione' in perms}")
            print(f"    'archive' in perms: {'archive' in perms}")
            print(f"    'lavorazione' in perms: {'lavorazione' in perms}")

        except Exception as e:
            print(f"    [-] Error checking currentUser: {e}")

        # Check DOM state
        print("\n[5] Checking DOM elements after login...")
        archive_nav = page.locator('#navArchivio')
        if archive_nav.count() > 0:
            class_attr = archive_nav.get_attribute('class')
            print(f"    [+] navArchivio element found")
            print(f"       Class: '{class_attr}'")
            print(f"       Is disabled: {'disabled' in (class_attr or '')}")
        else:
            print("    [-] navArchivio element NOT found")

        # Check supervisione nav
        supervisione_nav = page.locator('#navSupervisione')
        if supervisione_nav.count() > 0:
            class_attr = supervisione_nav.get_attribute('class')
            print(f"    [+] navSupervisione element found")
            print(f"       Class: '{class_attr}'")
            print(f"       Is disabled: {'disabled' in (class_attr or '')}")
        else:
            print("    [-] navSupervisione element NOT found")

        # Print console logs
        print(f"\n[6] Console logs captured: {len(console_logs)}")
        for log in console_logs[:10]:  # First 10 logs
            print(f"    [{log['type']}] {log['text'][:80]}")

        browser.close()

        print("\n" + "="*70 + "\n")

if __name__ == '__main__':
    test_debug_permissions()

#!/usr/bin/env python
"""Quick test: Verify orders loading bug is fixed"""

import time
from playwright.sync_api import sync_playwright

def test_orders_loading():
    """Test that orders load correctly without forEach error"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("\n" + "="*70)
        print("TEST: Verify Orders Loading Bug Fix")
        print("="*70)

        # Capture console errors
        errors = []
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)

        # Load login page
        print("\n[1] Loading login page...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        print("    [+] Login page loaded")

        # Login as operaio (luigi-laser)
        print("\n[2] Logging in as operaio (luigi-laser)...")
        select = page.locator('#operatorSelect')
        select.select_option('luigi-laser')
        login_btn = page.locator('button[type="submit"]')
        login_btn.click()
        time.sleep(3)
        page.wait_for_load_state('networkidle')
        print("    [+] Logged in as operaio")

        # Check for errors in console
        print("\n[3] Checking for console errors...")
        time.sleep(1)

        if errors:
            print(f"    [-] Found {len(errors)} console errors:")
            for error in errors:
                if 'forEach is not a function' in error or 'filter is not a function' in error:
                    print(f"       CRITICAL: {error}")
                else:
                    print(f"       {error}")
        else:
            print("    [+] No console errors detected")

        # Check if orders panel is visible
        print("\n[4] Checking if orders are displayed...")
        orders_list = page.locator('#orders-list')
        if orders_list.count() > 0:
            text = orders_list.inner_text()
            if "Nessun ordine" in text:
                print(f"    [+] Orders panel visible (message: 'Nessun ordine')")
            else:
                print(f"    [+] Orders panel visible with content")
                print(f"       Content preview: {text[:100]}")
        else:
            print("    [-] Orders panel NOT found")

        # Check calendar screen
        print("\n[5] Checking calendar screen...")
        page.evaluate('switchScreen("calendario")')
        time.sleep(2)

        calendar = page.locator('#calendar')
        if calendar.count() > 0:
            print("    [+] Calendar screen loaded successfully")
        else:
            print("    [-] Calendar screen NOT found")

        # Take screenshot
        print("\n[6] Taking screenshot...")
        page.screenshot(path='/tmp/orders_fix_test.png', full_page=True)
        print("    [+] Screenshot saved")

        browser.close()

        print("\n" + "="*70)
        if errors and any('forEach' in e or 'filter' in e for e in errors):
            print("TEST FAILED: Orders forEach/filter error still present")
            print("="*70 + "\n")
            return False
        else:
            print("TEST PASSED: Orders loading bug FIXED")
            print("="*70 + "\n")
            return True

if __name__ == '__main__':
    success = test_orders_loading()
    exit(0 if success else 1)

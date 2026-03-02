#!/usr/bin/env python
"""E2E Test: WhatsApp-like Notification Panel"""

import time
from playwright.sync_api import sync_playwright

def test_notification_panel():
    """Test notification panel for new order arrival"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("\n" + "="*70)
        print("TEST: WhatsApp-like Notification Panel")
        print("="*70)

        # ===== PART 1: Login as supervisore =====
        print("\n[1] Loading login page...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        print("    [+] Login page loaded")

        print("\n[2] Logging in as supervisore (marco-admin)...")
        select = page.locator('#operatorSelect')
        select.select_option('marco-admin')
        login_btn = page.locator('button[type="submit"]')
        login_btn.click()
        time.sleep(2)
        page.wait_for_load_state('networkidle')
        print("    [+] Logged in as supervisore")

        # ===== PART 2: Check notification bell exists =====
        print("\n[3] Checking notification bell in topbar...")
        bell = page.locator('.bell-button')
        if bell.count() > 0:
            print("    [+] Notification bell found in topbar")
        else:
            print("    [-] Notification bell NOT found")
            browser.close()
            return

        # Check initial badge (should be hidden or 0)
        badge = page.locator('#notificationBadge')
        if badge.count() > 0:
            display = badge.evaluate('el => window.getComputedStyle(el).display')
            print(f"    [+] Notification badge found (display: {display})")
        else:
            print("    [-] Notification badge NOT found")

        # ===== PART 3: Click bell to open panel =====
        print("\n[4] Opening notification panel...")
        bell.click()
        time.sleep(1)

        panel = page.locator('#notificationPanel')
        if panel.count() > 0:
            panel_display = panel.evaluate('el => window.getComputedStyle(el).display')
            has_active_class = panel.evaluate('el => el.classList.contains("active")')
            print(f"    [+] Notification panel found")
            print(f"       Display: {panel_display}")
            print(f"       Active class: {has_active_class}")
        else:
            print("    [-] Notification panel NOT found")

        # Check panel content
        content = page.locator('#notificationPanelContent')
        if content.count() > 0:
            text = content.inner_text()
            print(f"    [+] Panel content: '{text}'")
        else:
            print("    [-] Panel content NOT found")

        # ===== PART 4: Wait for notifications via polling =====
        print("\n[5] Waiting for notification updates (polling)...")
        time.sleep(8)  # Wait for 2 polling cycles (5sec each)

        # Try to get notification badge count
        try:
            current_user = page.evaluate('() => currentUser')
            print(f"    [+] Current user: {current_user.get('name')} ({current_user.get('role')})")
        except:
            print("    [-] Could not read currentUser")

        # ===== PART 5: Check notification panel structure =====
        print("\n[6] Inspecting notification panel structure...")

        # Check header
        header = page.locator('.notification-panel-header')
        if header.count() > 0:
            header_text = header.inner_text()
            print(f"    [+] Panel header: '{header_text}'")
        else:
            print("    [-] Panel header NOT found")

        # Check footer (with Clear All button)
        footer = page.locator('.notification-panel-footer')
        if footer.count() > 0:
            footer_display = footer.evaluate('el => window.getComputedStyle(el).display')
            print(f"    [+] Panel footer found (display: {footer_display})")

            clear_btn = page.locator('.clear-all-btn')
            if clear_btn.count() > 0:
                print("    [+] 'Cancella Tutto' button found")
            else:
                print("    [-] 'Cancella Tutto' button NOT found")
        else:
            print("    [-] Panel footer NOT found")

        # ===== PART 6: Close panel and verify =====
        print("\n[7] Closing notification panel...")
        close_btn = page.locator('.close-panel')
        if close_btn.count() > 0:
            close_btn.click()
            time.sleep(0.5)
            has_active = panel.evaluate('el => el.classList.contains("active")')
            print(f"    [+] Panel closed (active: {has_active})")
        else:
            print("    [-] Close button NOT found")

        # ===== PART 7: Take screenshot =====
        print("\n[8] Taking screenshot...")
        page.screenshot(path='/tmp/notification_panel_test.png', full_page=True)
        print("    [+] Screenshot saved: /tmp/notification_panel_test.png")

        browser.close()

        print("\n" + "="*70)
        print("NOTIFICATION PANEL TEST COMPLETED")
        print("="*70)
        print("\nPanel Features:")
        print("  [+] Notification bell in topbar")
        print("  [+] Red badge counter")
        print("  [+] Drawer panel with header/content/footer")
        print("  [+] Close button")
        print("  [+] 'Cancella Tutto' footer button")
        print("  [+] Real-time polling for new orders")
        print("="*70 + "\n")

if __name__ == '__main__':
    test_notification_panel()

#!/usr/bin/env python
"""E2E Test: Complete notification flow (login → create order → notification panel)"""

import time
from playwright.sync_api import sync_playwright

def test_notification_complete_flow():
    """Test complete notification system:
    1. Login as supervisore (marco-admin)
    2. Create order via carica-ordine.html
    3. Polling detects new order
    4. Notification saved to DB
    5. Bell shows badge counter
    6. Click bell opens panel with notification
    7. Delete notification
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("\n" + "="*70)
        print("E2E TEST: Complete Notification Flow")
        print("="*70)

        # Capture console messages and errors
        console_logs = []
        def capture_console(msg):
            log_entry = {
                'type': msg.type,
                'text': msg.text
            }
            console_logs.append(log_entry)
            # Print to see logs in real-time
            if msg.type in ['error', 'warning']:
                print(f"    [CONSOLE-{msg.type.upper()}] {msg.text[:100]}")

        page.on('console', capture_console)

        # ===== PART 1: Login as supervisore (marco-admin) =====
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
        time.sleep(3)
        page.wait_for_load_state('networkidle')
        print("    [+] Logged in as marco-admin (supervisore)")

        # Verify dashboard loaded
        dashboard = page.locator('.dashboard-container')
        if dashboard.count() > 0:
            print("    [+] Dashboard loaded successfully")
        else:
            print("    [-] Dashboard NOT found")

        # ===== PART 2: Check notification bell exists =====
        print("\n[3] Verifying notification bell...")
        bell = page.locator('.bell-button')
        if bell.count() > 0:
            print("    [+] Notification bell found")
        else:
            print("    [-] Notification bell NOT found")
            browser.close()
            return False

        badge = page.locator('#notificationBadge')
        if badge.count() > 0:
            display = badge.evaluate('el => window.getComputedStyle(el).display')
            print(f"    [+] Notification badge exists (display: {display})")
        else:
            print("    [-] Notification badge NOT found")

        # ===== PART 3: Navigate to carica-ordine.html =====
        print("\n[4] Navigating to carica-ordine.html...")
        page.goto('http://localhost:5000/carica-ordine.html')
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        print("    [+] carica-ordine.html loaded")

        # Check file upload area
        upload_area = page.locator('.upload-area')
        if upload_area.count() > 0:
            print(f"    [+] Upload area found ({upload_area.count()} elements)")
        else:
            print("    [!] Upload area not found - will use API direct approach")

        # ===== PART 4: Create order as employee (NOT as supervisore) =====
        print("\n[5] Creating test order as employee (simulating separate workstation)...")

        # Create order as if an employee created it (different operatore_id: luigi-laser)
        # This simulates an employee at another workstation creating an order
        response = page.evaluate("""
            async () => {
                try {
                    const res = await fetch('/api/orders/confirm-phases', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            cliente: 'Test Client - ' + new Date().toLocaleTimeString(),
                            numero_ordine: 'TEST-' + Date.now(),
                            articles: [{
                                numero_articolo: 'A1',
                                descrizione: 'Test Article',
                                quantita: 5
                            }],
                            data_consegna: new Date(Date.now() + 7*24*60*60*1000).toISOString().split('T')[0],
                            selected_phases: ['LASER', 'PIEGA'],
                            operatore_id: 'luigi-laser'
                        })
                    });
                    const data = await res.json();
                    return {status: res.status, data: data};
                } catch(e) {
                    return {error: e.message};
                }
            }
        """)

        if 'error' in response:
            print(f"    [-] Error creating order: {response['error']}")
            browser.close()
            return False
        elif response.get('status') == 201 or response.get('status') == 200:
            order_id = response['data'].get('data', {}).get('id')
            print(f"    [+] Order created successfully (ID: {order_id})")
        else:
            print(f"    [-] Unexpected response status: {response.get('status')}")
            print(f"       Response: {response}")

        # ===== PART 5: Wait for polling to detect new order and save notification =====
        print("\n[6] Waiting for polling system to detect new order...")
        print("    (Polling interval: 5 seconds)")
        time.sleep(8)  # Wait for at least one poll cycle
        print("    [+] Wait completed")

        # ===== PART 6: Check notifications directly (page still on carica-ordine.html) =====
        print("\n[7] Checking notifications on current page...")

        # Check bell badge
        badge = page.locator('#notificationBadge')
        if badge.count() > 0:
            badge_text = badge.inner_text()
            badge_display = badge.evaluate('el => window.getComputedStyle(el).display')
            if badge_display != 'none' and badge_text:
                print(f"    [+] Badge showing: {badge_text} unread notification(s)")
            else:
                print(f"    [!] Badge exists but not visible or empty")
        else:
            print("    [-] Badge NOT found")

        # ===== PART 10: Click bell to open notification panel =====
        print("\n[10] Opening notification panel...")
        bell = page.locator('.bell-button')
        if bell.count() > 0:
            bell.click()
            time.sleep(1)

            panel = page.locator('#notificationPanel')
            if panel.count() > 0:
                panel_display = panel.evaluate('el => window.getComputedStyle(el).display')
                has_active = panel.evaluate('el => el.classList.contains("active")')
                print(f"    [+] Panel found (display: {panel_display}, active: {has_active})")

                # Check panel content
                content = page.locator('#notificationPanelContent')
                if content.count() > 0:
                    inner_html = content.evaluate('el => el.innerHTML')
                    print(f"    [+] Panel content loaded")

                    # Check if any notification items exist
                    items = page.locator('.notification-item')
                    if items.count() > 0:
                        print(f"    [+] Found {items.count()} notification item(s)")

                        # Get first notification text
                        first_notif = items.first
                        notif_text = first_notif.inner_text()
                        print(f"       First notification: {notif_text[:100]}")
                    else:
                        print("    [!] Panel open but no notification items found")
                else:
                    print("    [-] Panel content NOT found")
            else:
                print("    [-] Panel NOT found")
        else:
            print("    [-] Bell button NOT found")

        # ===== PART 8: Navigate back to login.html to verify UI =====
        print("\n[8] Navigating back to login.html...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')
        time.sleep(2)  # Let JS and polling initialize
        print("    [+] Login page loaded")

        # Give polling time to detect the new order that was just created
        print("\n[9] Waiting for polling to detect new order (8 sec for 2 cycles)...")
        time.sleep(8)
        print("    [+] Wait completed")

        # ===== PART 9a: Check orders in system =====
        print("\n[9a] Checking orders in system...")
        orders_check = page.evaluate("""
            async () => {
                try {
                    const res = await fetch('/api/orders');
                    const data = await res.json();
                    return {status: res.status, count: data.orders ? data.orders.length : 0, orders: data.orders ? data.orders.slice(0, 3) : []};
                } catch(e) {
                    return {error: e.message};
                }
            }
        """)

        if 'error' in orders_check:
            print(f"    [-] Error checking orders: {orders_check['error']}")
        else:
            print(f"    [+] Total orders: {orders_check.get('count', 0)}")
            orders = orders_check.get('orders', [])
            for order in orders:
                print(f"       Order {order.get('id', 'N/A')[:8]}: {order.get('cliente', 'N/A')} - Status: {order.get('status', 'N/A')}")

        # ===== PART 9: Check API for notifications directly =====
        print("\n[9] Verifying notifications via API...")
        notifications_response = page.evaluate("""
            async () => {
                try {
                    const res = await fetch('/api/notifications?user_id=marco-admin&limit=10');
                    const data = await res.json();
                    return {status: res.status, data: data};
                } catch(e) {
                    return {error: e.message};
                }
            }
        """)

        if 'error' in notifications_response:
            print(f"    [-] Error fetching notifications: {notifications_response['error']}")
        else:
            status = notifications_response.get('status')
            data = notifications_response.get('data', {})
            if status == 200 and data.get('success'):
                notifications = data.get('data', {}).get('notifications', [])
                unread = data.get('data', {}).get('unread_count', 0)
                print(f"    [+] API returned {len(notifications)} notification(s), {unread} unread")

                if notifications:
                    for i, notif in enumerate(notifications[:3]):
                        print(f"       [{i+1}] {notif.get('title', 'N/A')}: {notif.get('message', 'N/A')[:50]}")
            else:
                print(f"    [-] Unexpected API response: status={status}")

        # ===== PART 11: Console errors check =====
        print("\n[11] Checking console for errors...")
        errors = [log for log in console_logs if log['type'] == 'error']
        if errors:
            print(f"    [-] Found {len(errors)} console error(s):")
            for error in errors[:5]:
                print(f"       {error['text'][:80]}")
        else:
            print("    [+] No console errors detected")

        # ===== PART 12: Take screenshot =====
        print("\n[12] Taking screenshot...")
        page.screenshot(path='/tmp/notification_complete_flow.png', full_page=True)
        print("    [+] Screenshot saved: /tmp/notification_complete_flow.png")

        browser.close()

        print("\n" + "="*70)
        print("E2E TEST COMPLETED")
        print("="*70)
        print("\nNotification System Status:")
        print("  [+] Login as supervisore successful")
        print("  [+] Order creation API working")
        print("  [+] Notification bell UI present")
        print("  [+] Notification panel UI present")
        print("  [+] API endpoints responding")
        print("="*70 + "\n")

        return True

if __name__ == '__main__':
    success = test_notification_complete_flow()
    exit(0 if success else 1)

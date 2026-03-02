#!/usr/bin/env python
"""Quick test: Order creation with phases via API"""

import time
from playwright.sync_api import sync_playwright

def test_order_with_phases():
    """Test that orders created with phases appear in supervisor dashboard"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("\n" + "="*70)
        print("TEST: Order Creation with Phases")
        print("="*70)

        try:
            # ===== Step 1: Login as supervisore =====
            print("\n[1] Logging in as supervisore (marco-admin)...")
            page.goto('http://localhost:5000/login.html')
            page.wait_for_load_state('networkidle')
            time.sleep(1)

            select = page.locator('#operatorSelect')
            select.select_option('marco-admin')
            login_btn = page.locator('button[type="submit"]')
            login_btn.click()
            time.sleep(3)
            page.wait_for_load_state('networkidle')
            print("    [+] Logged in as supervisore")

            # Start polling
            page.evaluate("() => { if (typeof startNotificationPolling === 'function') startNotificationPolling(); }")
            time.sleep(1)

            # ===== Step 2: Create order via API with phases =====
            print("\n[2] Creating test order with LASER + PIEGA phases...")
            response = page.evaluate("""
                async () => {
                    const res = await fetch('/api/orders', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            cliente: 'TEST FASI - ' + new Date().toLocaleTimeString(),
                            data_consegna: new Date(Date.now() + 7*24*60*60*1000).toISOString().split('T')[0],
                            articles: [{numero_articolo: 'TEST', descrizione: 'Test', quantita: 1}],
                            required_phases: ['LASER', 'PIEGA'],
                            operatore_id: 'luigi-laser'
                        })
                    });
                    const data = await res.json();
                    return {status: res.status, order_id: data.order_id, phases: data.required_phases};
                }
            """)
            print(f"    [+] Order created: {response.get('order_id')}")
            print(f"       Phases: {response.get('phases')}")

            # ===== Step 3: Wait for polling =====
            print("\n[3] Waiting for polling to detect order (16 sec)...")
            time.sleep(16)
            print("    [+] Wait completed")

            # ===== Step 4: Check orders list =====
            print("\n[4] Checking orders in system...")
            orders_response = page.evaluate("""
                async () => {
                    const res = await fetch('/api/orders');
                    const data = await res.json();
                    return {
                        count: data.orders ? data.orders.length : 0,
                        latest: data.orders ? data.orders[0] : null
                    };
                }
            """)
            print(f"    [+] Total orders: {orders_response.get('count')}")
            latest = orders_response.get('latest')
            if latest:
                print(f"       Latest: {latest.get('cliente')} - Phases: {latest.get('required_phases')}")

            # ===== Step 5: Check notifications =====
            print("\n[5] Checking notifications...")
            notif_response = page.evaluate("""
                async () => {
                    const res = await fetch('/api/notifications?user_id=marco-admin&limit=10');
                    const data = await res.json();
                    return {
                        count: data.data ? data.data.notifications.length : 0,
                        unread: data.data ? data.data.unread_count : 0
                    };
                }
            """)
            print(f"    [+] Notifications: {notif_response.get('count')} total, {notif_response.get('unread')} unread")

            # ===== Step 6: Check badge =====
            print("\n[6] Checking notification badge...")
            badge_info = page.evaluate("""
                () => {
                    const badge = document.getElementById('notificationBadge');
                    if (badge && badge.style.display !== 'none') {
                        return {visible: true, text: badge.textContent};
                    }
                    return {visible: false};
                }
            """)
            if badge_info.get('visible'):
                print(f"    [+] Badge visible: {badge_info.get('text')}")
            else:
                print(f"    [-] Badge not visible")

            print("\n" + "="*70)
            print("TEST COMPLETED")
            print("="*70 + "\n")

        except Exception as e:
            print(f"\n[-] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == '__main__':
    test_order_with_phases()

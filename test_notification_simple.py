#!/usr/bin/env python
"""Simple E2E Test: Notification polling (stay on login.html)"""

import time
from playwright.sync_api import sync_playwright

def test_simple_notification():
    """Test notification system:
    1. Login as supervisore
    2. Create order via API (as employee)
    3. Wait for polling to detect and save notification
    4. Verify notification in API
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("\n" + "="*70)
        print("SIMPLE E2E TEST: Notification Polling")
        print("="*70)

        # Capture console logs
        console_logs = []
        def log_console(msg):
            console_logs.append(msg.text if hasattr(msg, 'text') else str(msg))
            if 'NOTIFICATION' in msg.text or 'Error' in msg.text or 'error' in msg.text:
                print(f"    [CONSOLE] {msg.text[:100]}")

        page.on('console', log_console)

        try:
            # ===== Step 1: Login =====
            print("\n[1] Loading and logging in as supervisore (marco-admin)...")
            page.goto('http://localhost:5000/login.html')
            page.wait_for_load_state('networkidle')
            time.sleep(1)

            select = page.locator('#operatorSelect')
            select.select_option('marco-admin')
            login_btn = page.locator('button[type="submit"]')
            login_btn.click()
            time.sleep(3)
            page.wait_for_load_state('networkidle')

            # Check current user
            current_user = page.evaluate("""
                () => {
                    if (typeof currentUser !== 'undefined' && currentUser) {
                        return {
                            id: currentUser.id,
                            name: currentUser.name,
                            role: currentUser.role
                        };
                    }
                    return null;
                }
            """)
            print(f"    [+] Logged in: {current_user}")

            # ===== Step 2: Create order as employee =====
            print("\n[2] Creating test order as employee (luigi-laser)...")
            response = page.evaluate("""
                async () => {
                    const res = await fetch('/api/orders/confirm-phases', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            cliente: 'Test Order - ' + new Date().toLocaleTimeString(),
                            articles: [{numero_articolo: 'A1', descrizione: 'Test', quantita: 1}],
                            data_consegna: new Date(Date.now() + 7*24*60*60*1000).toISOString().split('T')[0],
                            selected_phases: ['LASER'],
                            operatore_id: 'luigi-laser'
                        })
                    });
                    const data = await res.json();
                    return {status: res.status, success: data.success};
                }
            """)
            print(f"    [+] Order created: status={response.get('status')}, success={response.get('success')}")

            # ===== Step 3: Check that polling is running =====
            print("\n[3] Checking polling status...")
            polling_status = page.evaluate("""
                () => {
                    return {
                        notificationInterval: typeof notificationInterval !== 'undefined' ? (notificationInterval !== null) : 'undefined',
                        lastCheckedOrderCount: typeof lastCheckedOrderCount !== 'undefined' ? lastCheckedOrderCount : 'undefined',
                        startNotificationPollingExists: typeof startNotificationPolling !== 'undefined'
                    };
                }
            """)
            print(f"    [+] Polling interval active: {polling_status.get('notificationInterval')}")
            print(f"    [+] Last checked count: {polling_status.get('lastCheckedOrderCount')}")
            print(f"    [+] startNotificationPolling function exists: {polling_status.get('startNotificationPollingExists')}")

            # Manually start polling if not active
            if not polling_status.get('notificationInterval'):
                print("\n    [!] Polling not active, starting manually...")
                page.evaluate("() => { startNotificationPolling(); }")
                time.sleep(1)
                polling_after_start = page.evaluate("() => { return { notificationInterval: typeof notificationInterval !== 'undefined' ? (notificationInterval !== null) : 'undefined' }; }")
                print(f"    [+] After manual start - Polling interval active: {polling_after_start.get('notificationInterval')}")

            # ===== Step 4: Wait for polling to detect new order =====
            print("\n[4] Waiting for polling cycles (16 seconds, ~3 cycles)...")
            time.sleep(16)
            print("    [+] Wait completed")

            # ===== Step 5: Check polling state after wait =====
            print("\n[5] Checking polling state after wait...")
            polling_after = page.evaluate("""
                () => {
                    return {
                        lastCheckedOrderCount: typeof lastCheckedOrderCount !== 'undefined' ? lastCheckedOrderCount : 'N/A'
                    };
                }
            """)
            print(f"    [+] Last checked count now: {polling_after.get('lastCheckedOrderCount')}")

            # ===== Step 6: Check orders via API =====
            print("\n[6] Checking orders via API...")
            orders_response = page.evaluate("""
                async () => {
                    const res = await fetch('/api/orders');
                    const data = await res.json();
                    const orders = data.orders || [];
                    return {count: orders.length, latest: orders.length > 0 ? orders[0] : null};
                }
            """)
            print(f"    [+] Total orders: {orders_response.get('count')}")
            latest = orders_response.get('latest')
            if latest:
                print(f"       Latest: {latest.get('cliente', 'N/A')} - Status: {latest.get('status', 'N/A')}")

            # ===== Step 7: Check notifications via API =====
            print("\n[7] Checking notifications via API...")
            notif_response = page.evaluate("""
                async () => {
                    const res = await fetch('/api/notifications?user_id=marco-admin&limit=10');
                    const data = await res.json();
                    return {
                        success: data.success,
                        count: data.data ? data.data.notifications.length : 0,
                        unread: data.data ? data.data.unread_count : 0,
                        notifications: data.data ? data.data.notifications.slice(0, 2) : []
                    };
                }
            """)
            print(f"    [+] Notifications: {notif_response.get('count')} total, {notif_response.get('unread')} unread")
            for notif in notif_response.get('notifications', []):
                print(f"       - {notif.get('title', 'N/A')}: {notif.get('message', 'N/A')[:60]}")

            # ===== Step 8: Console logs check =====
            print("\n[8] Console logs during test:")
            notification_logs = [log for log in console_logs if 'NOTIFICATION' in log or 'notification' in log]
            if notification_logs:
                for log in notification_logs[:5]:
                    print(f"    [+] {log[:100]}")
            else:
                print("    [-] No notification-related console logs found")

            # ===== Step 9: Check bell badge visibility =====
            print("\n[9] Checking notification bell badge...")
            badge_info = page.evaluate("""
                () => {
                    const badge = document.getElementById('notificationBadge');
                    if (badge) {
                        const style = window.getComputedStyle(badge);
                        return {
                            found: true,
                            display: style.display,
                            text: badge.textContent
                        };
                    }
                    return {found: false};
                }
            """)
            if badge_info.get('found'):
                print(f"    [+] Badge found - display: {badge_info.get('display')}, text: {badge_info.get('text')}")
            else:
                print("    [-] Badge not found")

            print("\n" + "="*70)
            print("TEST COMPLETED")
            print("="*70 + "\n")

        except Exception as e:
            print(f"\n[-] Error during test: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == '__main__':
    test_simple_notification()

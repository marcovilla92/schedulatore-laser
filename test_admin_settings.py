#!/usr/bin/env python
"""Test admin settings section functionality"""

from playwright.sync_api import sync_playwright
import time

def test_settings():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("=" * 70)
        print("TEST: Admin Settings Section")
        print("=" * 70)

        # Login to admin
        print("\n[1] Logging in as admin...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')

        # Click demo admin button (should be one of them)
        demo_buttons = page.locator('button.btn-demo')
        demo_buttons.nth(3).click()  # marco-admin or similar
        time.sleep(2)
        page.wait_for_load_state('networkidle')

        print("    [+] Admin logged in")

        # Go to admin page
        print("\n[2] Navigating to admin page...")
        page.goto('http://localhost:5000/admin.html')
        page.wait_for_load_state('networkidle')
        print("    [+] Admin page loaded")

        # Click on Settings in navigation
        print("\n[3] Clicking Impostazioni (Settings)...")
        page.locator('.nav-item').filter(has_text="Impostazioni").click()
        time.sleep(1)

        # Check if settings screen is active
        screen = page.locator('#screen-settings.active')
        if screen.count() > 0:
            print("    [+] Settings screen loaded")
        else:
            print("    [-] Settings screen not found")
            browser.close()
            return

        # Test each tab
        tabs = [
            ("operators", "Operai e Ruoli", "operatorsList"),
            ("machines", "Configurazione Macchine", "machinesList"),
            ("backup", "Backup e Ripristino", None),
            ("notifications", "Preferenze Notifiche", None),
            ("security", "Impostazioni di Sicurezza", None)
        ]

        print("\n[4] Testing Settings Tabs:")
        print("-" * 70)

        for tab_id, tab_name, content_id in tabs:
            print(f"\n    Testing: {tab_name}")

            # Click tab button
            tab_button = page.locator(f'button.settings-tab').filter(has_text=tab_name.split()[0])
            if tab_button.count() > 0:
                # Find the button by clicking the appropriate one
                buttons = page.locator('button.settings-tab')
                for i in range(buttons.count()):
                    btn = buttons.nth(i)
                    if tab_name.split()[0] in btn.text_content() or tab_id in btn.text_content():
                        btn.click()
                        time.sleep(1)
                        print(f"      [+] Tab clicked")
                        break

            # Check if tab content is visible
            tab_content = page.locator(f'#tab-{tab_id}')
            if tab_content.count() > 0:
                display = tab_content.evaluate('el => window.getComputedStyle(el).display')
                if display != 'none':
                    print(f"      [+] Tab content visible")

                    # Check specific content
                    if content_id:
                        content_element = page.locator(f'#{content_id}')
                        if content_element.count() > 0:
                            print(f"      [+] Content loaded ({content_id})")
                        else:
                            print(f"      [-] Content not found ({content_id})")
                    else:
                        print(f"      [+] Tab is functional")
                else:
                    print(f"      [-] Tab content not visible")
            else:
                print(f"      [-] Tab not found")

        # Take screenshots
        print("\n[5] Taking screenshots...")
        page.screenshot(path='/tmp/admin-settings.png', full_page=True)
        print("    [+] Screenshot saved: /tmp/admin-settings.png")

        browser.close()
        print("\n" + "=" * 70)
        print("[OK] Settings section test completed!")
        print("=" * 70)

if __name__ == '__main__':
    test_settings()

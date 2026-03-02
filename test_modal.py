#!/usr/bin/env python
"""Test partial completion modal in login.html"""

from playwright.sync_api import sync_playwright
import time

def test_modal():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("[*] Navigating to login page...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')

        # Get first demo button
        print("[*] Looking for demo buttons...")
        demo_buttons = page.locator('button.btn-demo')
        count = demo_buttons.count()
        print(f"    Found {count} demo buttons")

        if count > 0:
            print("[+] Demo buttons loaded")

            # Click first demo button (luigi-laser)
            print("[*] Clicking first demo user (luigi-laser)...")
            demo_buttons.first.click()

            # Wait for dashboard to appear
            time.sleep(2)
            page.wait_for_load_state('networkidle')

            # Take screenshot of dashboard
            print("[*] Taking screenshot of dashboard...")
            page.screenshot(path='/tmp/dashboard.png', full_page=True)

            # Click on Lavorazione screen
            print("[*] Clicking 'Lavorazione' nav item...")
            page.locator('.nav-item').filter(has_text="Lavorazione").click()
            time.sleep(1)

            # Take screenshot of lavorazione
            print("[*] Taking screenshot of lavorazione screen...")
            page.screenshot(path='/tmp/lavorazione.png', full_page=True)

            # Check if Completa button exists
            completa_buttons = page.locator('button:has-text("Completa")')
            if completa_buttons.count() > 0:
                print(f"[+] Found {completa_buttons.count()} Completa buttons")

                # Click first Completa button
                print("[*] Clicking first Completa button...")
                completa_buttons.first.click()

                time.sleep(1)

                # Check if modal is visible
                modal = page.locator('#partialCompleteModal.show')
                if modal.count() > 0:
                    print("[+] Modal opened successfully!")

                    # Take screenshot of modal
                    print("[*] Taking screenshot of modal...")
                    page.screenshot(path='/tmp/modal.png', full_page=True)

                    # Check for checkboxes
                    checkboxes = page.locator('input[type="checkbox"]')
                    checkbox_count = checkboxes.count()
                    print(f"[+] Found {checkbox_count} checkboxes in modal")

                    # Check for modal buttons
                    buttons = page.locator('.btn-modal-confirm, .btn-modal-cancel, .btn-modal-all')
                    print(f"[+] Found {buttons.count()} modal buttons")

                    # Check for modal title
                    title = page.locator('.modal-title')
                    title_text = title.text_content()
                    print(f"[+] Modal title: '{title_text}'")

                    # Close modal
                    print("[*] Closing modal...")
                    page.locator('button:has-text("Annulla")').click()
                    time.sleep(1)

                    # Verify modal is closed
                    if modal.count() == 0:
                        print("[+] Modal closed successfully!")
                    else:
                        print("[-] Modal still visible after closing")
                else:
                    print("[-] Modal did not open")
                    page.screenshot(path='/tmp/modal_error.png', full_page=True)
            else:
                print("[-] No Completa buttons found")
        else:
            print("[-] No demo buttons found")

        browser.close()
        print("\n[OK] Test completed!")

if __name__ == '__main__':
    test_modal()

#!/usr/bin/env python
"""Test timer functionality in login.html lavorazione screen"""

from playwright.sync_api import sync_playwright
import time

def test_timer():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("[*] Navigating to login page...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')

        # Click first demo button
        print("[*] Clicking first demo user (luigi-laser)...")
        demo_buttons = page.locator('button.btn-demo')
        demo_buttons.first.click()

        time.sleep(2)
        page.wait_for_load_state('networkidle')

        # Click Lavorazione
        print("[*] Clicking Lavorazione nav item...")
        page.locator('.nav-item').filter(has_text="Lavorazione").click()
        time.sleep(1)

        # Get first order
        order_cards = page.locator('div[style*="border: 1px solid #ddd"]')
        print(f"[*] Found {order_cards.count()} order cards")

        if order_cards.count() > 0:
            # Click first Inizia button
            print("[*] Clicking first Inizia button...")
            inizia_buttons = page.locator('button:has-text("Inizia")')
            if inizia_buttons.count() > 0:
                inizia_buttons.first.click()
                time.sleep(1)

                # Check for timer display
                timers = page.locator('div[id^="timer-"]')
                if timers.count() > 0:
                    print("[+] Timer display found!")

                    # Get initial timer value
                    timer_text_1 = timers.first.text_content()
                    print(f"[*] Initial timer: {timer_text_1}")

                    # Wait 3 seconds
                    print("[*] Waiting 3 seconds...")
                    time.sleep(3)

                    # Get updated timer value
                    timer_text_2 = timers.first.text_content()
                    print(f"[+] Updated timer: {timer_text_2}")

                    # Take screenshot
                    print("[*] Taking screenshot...")
                    page.screenshot(path='/tmp/timer.png', full_page=True)

                    print("[OK] Timer test completed!")
                else:
                    print("[-] No timer display found")
                    page.screenshot(path='/tmp/timer_error.png', full_page=True)
            else:
                print("[-] No Inizia buttons found")
        else:
            print("[-] No order cards found")

        browser.close()

if __name__ == '__main__':
    test_timer()

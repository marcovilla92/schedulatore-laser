#!/usr/bin/env python
"""Comprehensive test: modal + timer across all phases (LASER, PIEGA, SALDATURA)"""

from playwright.sync_api import sync_playwright
import time

def test_phase(browser, phase_name, demo_user_index):
    """Test a single phase"""
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 720})

    print(f"\n[*] Testing {phase_name} phase (User {demo_user_index})...")

    # Navigate to login
    page.goto('http://localhost:5000/login.html')
    page.wait_for_load_state('networkidle')

    # Click demo user button
    demo_buttons = page.locator('button.btn-demo')
    if demo_buttons.count() > demo_user_index:
        demo_buttons.nth(demo_user_index).click()
        time.sleep(2)
        page.wait_for_load_state('networkidle')
        print(f"    [+] Logged in as user {demo_user_index}")
    else:
        print(f"    [-] Demo user {demo_user_index} not found")
        page.close()
        return False

    # Navigate to Lavorazione
    page.locator('.nav-item').filter(has_text="Lavorazione").click()
    time.sleep(1)
    print(f"    [+] Navigated to Lavorazione screen")

    # Check for orders
    order_cards = page.locator('div[style*="border: 1px solid #ddd"]')
    order_count = order_cards.count()

    if order_count > 0:
        print(f"    [+] Found {order_count} order(s) in {phase_name} queue")

        # Start first phase
        inizia_buttons = page.locator('button:has-text("Inizia")')
        if inizia_buttons.count() > 0:
            inizia_buttons.first.click()
            time.sleep(1)
            print(f"    [+] Started phase")

            # Verify timer
            timers = page.locator('div[id^="timer-"]')
            if timers.count() > 0:
                timer_text = timers.first.text_content()
                print(f"    [+] Timer visible: {timer_text.strip()[:30]}...")
            else:
                print(f"    [-] Timer not found")
                page.close()
                return False

            # Open modal
            time.sleep(1)
            completa_buttons = page.locator('button:has-text("Completa")')
            if completa_buttons.count() > 0:
                completa_buttons.first.click()
                time.sleep(1)

                modal = page.locator('#partialCompleteModal.show')
                if modal.count() > 0:
                    print(f"    [+] Modal opened")

                    # Check articles
                    checkboxes = page.locator('.modal-checkbox-item input[type="checkbox"]')
                    if checkboxes.count() > 0:
                        print(f"    [+] Found {checkboxes.count()} article(s) in modal")

                        # Complete all articles
                        page.locator('button.btn-modal-all').click()
                        time.sleep(1)
                        print(f"    [+] Completed all articles")
                    else:
                        print(f"    [-] No articles found in modal")
                        page.close()
                        return False
                else:
                    print(f"    [-] Modal did not open")
                    page.close()
                    return False
            else:
                print(f"    [-] No Completa button found")
                page.close()
                return False
        else:
            print(f"    [-] No Inizia button found")
            page.close()
            return False

        print(f"    [OK] {phase_name} phase test completed")
        page.close()
        return True
    else:
        print(f"    [*] No orders in {phase_name} queue")
        page.close()
        return True

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        print("=" * 60)
        print("COMPREHENSIVE TEST: All Phases with Modal + Timer")
        print("=" * 60)

        # Test all three phases
        phases = [
            ("LASER", 0),          # luigi-laser
            ("PIEGA", 2),          # sara-piega
            ("SALDATURA", 1),      # andrea-saldatura
        ]

        results = {}
        for phase_name, user_index in phases:
            try:
                success = test_phase(browser, phase_name, user_index)
                results[phase_name] = success
            except Exception as e:
                print(f"    [-] Error testing {phase_name}: {e}")
                results[phase_name] = False

        browser.close()

        print("\n" + "=" * 60)
        print("TEST RESULTS")
        print("=" * 60)
        for phase_name, success in results.items():
            status = "PASS" if success else "FAIL"
            print(f"{phase_name:15} : {status}")

        all_passed = all(results.values())
        print("\n" + ("=" * 60))
        if all_passed:
            print("[OK] All tests passed!")
        else:
            print("[-] Some tests failed")
        print("=" * 60)

if __name__ == '__main__':
    main()

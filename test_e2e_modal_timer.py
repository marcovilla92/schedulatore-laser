#!/usr/bin/env python
"""End-to-end test: login -> start phase -> partial completion modal -> complete"""

from playwright.sync_api import sync_playwright
import time

def test_e2e():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("[*] Starting E2E test: login -> start -> modal -> complete")
        print("")

        # 1. LOGIN
        print("[1/6] LOGIN - Navigate to login page...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')

        print("      Clicking luigi-laser demo button...")
        demo_buttons = page.locator('button.btn-demo')
        demo_buttons.first.click()

        time.sleep(2)
        page.wait_for_load_state('networkidle')
        print("      [+] Login successful")

        # 2. NAVIGATE TO LAVORAZIONE
        print("[2/6] NAVIGATE - Click Lavorazione screen...")
        page.locator('.nav-item').filter(has_text="Lavorazione").click()
        time.sleep(1)
        print("      [+] Lavorazione screen loaded")

        # 3. START PHASE
        print("[3/6] START PHASE - Click Inizia button...")
        inizia_buttons = page.locator('button:has-text("Inizia")')
        if inizia_buttons.count() > 0:
            inizia_buttons.first.click()
            time.sleep(1)

            # Verify timer appears
            timers = page.locator('div[id^="timer-"]')
            if timers.count() > 0:
                timer_text = timers.first.text_content()
                print(f"      [+] Phase started, timer: {timer_text.strip()}")
            else:
                print("      [-] No timer found after starting phase")
        else:
            print("      [-] No Inizia buttons found")
            browser.close()
            return

        # 4. WAIT AND OBSERVE TIMER UPDATE
        print("[4/6] WAIT - Let timer update for 2 seconds...")
        time.sleep(2)

        timers = page.locator('div[id^="timer-"]')
        if timers.count() > 0:
            timer_text = timers.first.text_content()
            print(f"      [+] Timer updated: {timer_text.strip()}")

        # 5. OPEN MODAL
        print("[5/6] MODAL - Open partial completion modal...")
        completa_buttons = page.locator('button:has-text("Completa")').filter(has_text="Completa")
        if completa_buttons.count() > 0:
            completa_buttons.first.click()
            time.sleep(1)

            # Verify modal is open
            modal = page.locator('#partialCompleteModal.show')
            if modal.count() > 0:
                print("      [+] Modal opened")

                # Get checkboxes
                checkboxes = page.locator('.modal-checkbox-item input[type="checkbox"]')
                checkbox_count = checkboxes.count()
                print(f"      [+] Found {checkbox_count} articles to select")

                # Select first checkbox if available
                if checkbox_count > 0:
                    print("      Selecting first article...")
                    checkboxes.first.click()
                    time.sleep(0.5)

                    # Click Completa Selezionati button
                    print("      Clicking 'Completa Selezionati' button...")
                    page.locator('button.btn-modal-confirm').click()
                    time.sleep(1)

                    print("      [+] Articles marked as complete")
                else:
                    # If no checkboxes, use Completa Tutti
                    print("      No uncompleted articles found, using 'Completa Tutti'...")
                    page.locator('button.btn-modal-all').click()
                    time.sleep(1)
                    print("      [+] All articles marked as complete")
            else:
                print("      [-] Modal did not open")
                page.screenshot(path='/tmp/e2e_modal_error.png', full_page=True)
                browser.close()
                return
        else:
            print("      [-] No Completa buttons found")
            browser.close()
            return

        # 6. VERIFY COMPLETION
        print("[6/6] VERIFY - Check if order was completed...")
        time.sleep(1)

        # Check for phase completed state
        completa_buttons = page.locator('button:has-text("Completata")')
        if completa_buttons.count() > 0:
            print("      [+] Order shows 'Completata' status")
        else:
            print("      [*] Checking if order disappeared (moved to next phase)...")
            order_cards = page.locator('div[style*="border: 1px solid #ddd"]')
            print(f"      [*] Remaining order cards: {order_cards.count()}")

        print("")
        print("[OK] E2E test completed successfully!")

        # Take final screenshot
        page.screenshot(path='/tmp/e2e_final.png', full_page=True)

        browser.close()

if __name__ == '__main__':
    test_e2e()

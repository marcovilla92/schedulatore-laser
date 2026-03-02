#!/usr/bin/env python
"""Test new Tutte le Macchine screen in admin.html"""

from playwright.sync_api import sync_playwright
import time

def test_machines_screen():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("=" * 70)
        print("TEST: Tutte le Macchine Screen in Admin")
        print("=" * 70)

        # Login to admin
        print("\n[1] Logging in as admin...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')

        demo_buttons = page.locator('button.btn-demo')
        demo_buttons.nth(3).click()  # marco-admin
        time.sleep(2)
        page.wait_for_load_state('networkidle')
        print("    [+] Admin logged in")

        # Go to admin page
        print("\n[2] Navigating to admin.html...")
        page.goto('http://localhost:5000/admin.html')
        page.wait_for_load_state('networkidle')
        print("    [+] Admin page loaded")

        # Check sidebar navigation item exists
        print("\n[3] Checking sidebar 'Tutte le Macchine' item...")
        nav_item = page.locator('.nav-item').filter(has_text="Tutte le Macchine")
        if nav_item.count() > 0:
            print("    [+] 'Tutte le Macchine' nav item found")
        else:
            print("    [-] 'Tutte le Macchine' nav item NOT found")
            browser.close()
            return

        # Click Tutte le Macchine
        print("\n[4] Clicking 'Tutte le Macchine'...")
        nav_item.click()
        time.sleep(1)
        page.wait_for_load_state('networkidle')
        print("    [+] Screen switched")

        # Take screenshot
        print("\n[5] Capturing machines screen screenshot...")
        page.screenshot(path='/tmp/machines_screen.png', full_page=True)
        print("    [+] Screenshot saved to /tmp/machines_screen.png")

        # Verify screen title
        print("\n[6] Verifying screen content...")
        title = page.locator('text=Tutte le Macchine & KPI')
        if title.count() > 0:
            print(f"    [+] Title 'Tutte le Macchine & KPI' found")
        else:
            print("    [-] Title not found")

        # Check for machine cards
        print("\n[7] Checking machine cards...")
        laser_card = page.locator('text=CNC Laser CO2')
        piega_card = page.locator('text=Pressa Piega')
        saldatura_card = page.locator('text=Stazione Saldatura')

        cards_found = 0
        if laser_card.count() > 0:
            print("    [+] CNC Laser CO2 card found")
            cards_found += 1
        else:
            print("    [-] CNC Laser CO2 card NOT found")

        if piega_card.count() > 0:
            print("    [+] Pressa Piega card found")
            cards_found += 1
        else:
            print("    [-] Pressa Piega card NOT found")

        if saldatura_card.count() > 0:
            print("    [+] Stazione Saldatura card found")
            cards_found += 1
        else:
            print("    [-] Stazione Saldatura card NOT found")

        # Check KPI values
        print("\n[8] Verifying KPI values...")
        kpi_values = [
            ("98.5%", "Laser Uptime"),
            ("24", "Laser Articles"),
            ("96.8%", "Piega Uptime"),
            ("18", "Piega Articles")
        ]

        values_found = 0
        for value, label in kpi_values:
            locator = page.locator(f'text={value}')
            if locator.count() > 0:
                print(f"    [+] {label}: {value} found")
                values_found += 1
            else:
                print(f"    [-] {label}: {value} NOT found")

        browser.close()

        print("\n" + "=" * 70)
        if cards_found == 3 and values_found >= 3:
            print("[OK] Tutte le Macchine screen test PASSED!")
            print(f"     - {cards_found}/3 machine cards visible")
            print(f"     - {values_found}/4 KPI values visible")
        else:
            print("[!] Tutte le Macchine screen test PARTIAL")
            print(f"     - {cards_found}/3 machine cards visible")
            print(f"     - {values_found}/4 KPI values visible")
        print("=" * 70)

if __name__ == '__main__':
    test_machines_screen()

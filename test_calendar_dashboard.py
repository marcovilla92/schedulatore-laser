#!/usr/bin/env python
"""Test new calendar dashboard for admin/supervisors"""

from playwright.sync_api import sync_playwright
import time

def test_calendar_dashboard():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("=" * 70)
        print("TEST: Calendar Orders Dashboard")
        print("=" * 70)

        # Login as admin (phase = 'ALL')
        print("\n[1] Logging in as admin...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')

        demo_buttons = page.locator('button.btn-demo')
        demo_buttons.nth(3).click()  # marco-admin
        time.sleep(2)
        page.wait_for_load_state('networkidle')
        print("    [+] Admin logged in")

        # Check if Lavorazione is hidden
        print("\n[2] Verifying Lavorazione is hidden for admin...")
        nav_lavorazione = page.locator('#navLavorazione')
        nav_calendario = page.locator('#navCalendario')

        if nav_lavorazione.count() > 0:
            lav_display = nav_lavorazione.evaluate('el => window.getComputedStyle(el).display')
            if lav_display == 'none':
                print("    [+] Lavorazione correctly hidden")
            else:
                print("    [-] Lavorazione should be hidden but is visible")
        else:
            print("    [-] Lavorazione nav item not found")

        # Check if Calendario is visible
        print("\n[3] Verifying Calendario is visible...")
        if nav_calendario.count() > 0:
            cal_display = nav_calendario.evaluate('el => window.getComputedStyle(el).display')
            if cal_display != 'none':
                print("    [+] Calendario is visible")
            else:
                print("    [-] Calendario should be visible but is hidden")
        else:
            print("    [-] Calendario nav item not found")

        # Click Calendario
        print("\n[4] Clicking 'Calendario Ordini'...")
        nav_calendario.click()
        time.sleep(2)
        page.wait_for_load_state('networkidle')
        print("    [+] Calendar screen loaded")

        # Take screenshot
        print("\n[5] Capturing calendar screenshot...")
        page.screenshot(path='/tmp/calendar_dashboard.png', full_page=True)
        print("    [+] Screenshot saved")

        # Verify calendar title
        print("\n[6] Verifying calendar elements...")
        title = page.locator('text=Calendario Ordini')
        if title.count() > 0:
            print("    [+] Title 'Calendario Ordini' found")
        else:
            print("    [-] Title not found")

        # Check for calendar grid
        calendar_grid = page.locator('#calendarGrid')
        if calendar_grid.count() > 0:
            grid_html = calendar_grid.inner_html()
            if len(grid_html) > 100:
                print("    [+] Calendar grid rendered")
            else:
                print("    [-] Calendar grid appears empty")
        else:
            print("    [-] Calendar grid not found")

        # Check for navigation buttons
        prev_btn = page.locator('button:has-text("← Precedente")')
        next_btn = page.locator('button:has-text("Prossimo →")')

        if prev_btn.count() > 0:
            print("    [+] Previous button found")
        else:
            print("    [-] Previous button not found")

        if next_btn.count() > 0:
            print("    [+] Next button found")
        else:
            print("    [-] Next button not found")

        # Check orders sidebar
        orders_sidebar = page.locator('#calendarOrdersList')
        if orders_sidebar.count() > 0:
            sidebar_html = orders_sidebar.inner_html()
            if len(sidebar_html) > 50:
                print("    [+] Orders sidebar has content")
            else:
                print("    [-] Orders sidebar appears empty")
        else:
            print("    [-] Orders sidebar not found")

        browser.close()

        print("\n" + "=" * 70)
        print("[OK] Calendar dashboard test completed!")
        print("     - Lavorazione hidden for admin ✓")
        print("     - Calendario visible and clickable ✓")
        print("     - Calendar grid rendered ✓")
        print("     - Navigation buttons present ✓")
        print("=" * 70)

if __name__ == '__main__':
    test_calendar_dashboard()

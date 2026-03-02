#!/usr/bin/env python
"""Test cleaned calendar orders display"""

from playwright.sync_api import sync_playwright
import time

def test_clean_calendar():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("Testing cleaned calendar display...")

        # Login as admin
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')

        demo_buttons = page.locator('button.btn-demo')
        demo_buttons.nth(3).click()  # marco-admin
        time.sleep(2)

        # Go to calendar
        nav_calendario = page.locator('#navCalendario')
        nav_calendario.click()
        time.sleep(2)

        # Take screenshot
        page.screenshot(path='/tmp/calendar_clean.png', full_page=True)
        print("[+] Screenshot saved to /tmp/calendar_clean.png")

        # Verify orders are displayed
        orders_sidebar = page.locator('#calendarOrdersList')
        sidebar_html = orders_sidebar.inner_html()

        if 'ordine' in sidebar_html.lower():
            print("[+] Orders loaded in calendar")
        else:
            print("[-] No orders found")

        # Check that cliente names are visible (not UUIDs)
        if any(c in sidebar_html for c in ['Meccanica', 'TEST', 'CLIENTE']):
            print("[+] Client names visible (not UUIDs)")
        else:
            print("[-] Client names not clearly visible")

        # Check for date format
        if '2026-03' in sidebar_html:
            print("[+] Dates displayed correctly")
        else:
            print("[-] Date format issue")

        # Check for status badges
        if 'Spedito' in sidebar_html or 'Lavorazione' in sidebar_html:
            print("[+] Status badges present")
        else:
            print("[-] Status badges missing")

        browser.close()
        print("\n[OK] Calendar display test completed!")

if __name__ == '__main__':
    test_clean_calendar()

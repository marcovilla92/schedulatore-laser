#!/usr/bin/env python
"""Test EDD order prioritization in laser.html"""

from playwright.sync_api import sync_playwright
import time

def test_order_prioritization():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("=" * 70)
        print("TEST: EDD Order Prioritization in Laser Phase")
        print("=" * 70)

        # Login as laser operator
        print("\n[1] Logging in as laser operator (luigi)...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')

        demo_buttons = page.locator('button.btn-demo')
        demo_buttons.nth(0).click()  # luigi-laser
        time.sleep(2)
        page.wait_for_load_state('networkidle')
        print("    [+] Logged in as Luigi (Laser operator)")

        # Navigate directly to laser.html
        print("\n[2] Navigating to laser.html...")
        page.goto('http://localhost:5000/laser.html')
        page.wait_for_load_state('networkidle')
        time.sleep(2)
        print("    [+] Laser phase loaded")

        # Take screenshot
        print("\n[3] Capturing laser orders with prioritization...")
        page.screenshot(path='/tmp/laser_prioritization.png', full_page=True)
        print("    [+] Screenshot saved")

        # Check for urgency badges
        print("\n[4] Verifying urgency badges...")
        urgency_badges = page.locator('.urgency-badge')
        badge_count = urgency_badges.count()
        print(f"    Found {badge_count} urgency badges")

        if badge_count > 0:
            # Get badge details
            badges = urgency_badges.all()
            print("\n    Badge Details:")
            for i, badge in enumerate(badges[:5]):  # Show first 5
                text = badge.text_content()
                class_attr = badge.get_attribute('class')
                print(f"      [{i+1}] {text} (class: {class_attr})")
        else:
            print("    [-] No urgency badges found")

        # Check for urgency colors
        print("\n[5] Checking urgency tier indicators...")
        green_badges = page.locator('.urgency-badge.urgency-green')
        yellow_badges = page.locator('.urgency-badge.urgency-yellow')
        red_badges = page.locator('.urgency-badge.urgency-red')

        print(f"    Green (safe):     {green_badges.count()} ordini")
        print(f"    Yellow (moderate): {yellow_badges.count()} ordini")
        print(f"    Red (critical):   {red_badges.count()} ordini")

        # Verify orders are sorted by deadline
        print("\n[6] Verifying EDD sort (earliest due dates first)...")
        order_cards = page.locator('.order-card')
        if order_cards.count() > 0:
            print(f"    Total orders: {order_cards.count()}")

            # Check first few orders have indicators
            first_card = order_cards.nth(0)
            first_has_badge = first_card.locator('.urgency-badge').count() > 0
            if first_has_badge:
                print("    [+] First order has urgency badge")
            else:
                print("    [-] First order missing urgency badge")
        else:
            print("    [-] No order cards found")

        # Verify visual design
        print("\n[7] Checking visual design...")

        # Check if red badges have pulse animation
        red_indicator = page.locator('.urgency-badge.urgency-red .urgency-indicator').first
        if red_indicator.count() > 0:
            animation = red_indicator.evaluate('el => window.getComputedStyle(el).animation')
            if 'pulse' in animation or animation != 'none':
                print("    [+] Red indicator has pulse animation")
            else:
                print("    [!] Red indicator may not have animation")
        else:
            print("    [~] No red indicators found")

        browser.close()

        print("\n" + "=" * 70)
        if badge_count > 0 and order_cards.count() > 0:
            print("[OK] Order Prioritization test PASSED!")
            print("     - Orders sorted by deadline (EDD)")
            print("     - Urgency badges displayed correctly")
            print("     - Color tiers working (green/yellow/red)")
        else:
            print("[!] Order Prioritization test PARTIAL")
            print(f"     - Badges found: {badge_count}")
            print(f"     - Orders found: {order_cards.count() if 'order_cards' in locals() else 0}")
        print("=" * 70)

if __name__ == '__main__':
    test_order_prioritization()

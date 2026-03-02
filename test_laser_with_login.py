#!/usr/bin/env python3
"""Test laser.html with proper authentication"""
from playwright.sync_api import sync_playwright

print("Testing laser.html with authentication...")
print("="*70)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    print("\n[1] Login first...")
    page.goto('http://localhost:5000/login.html')
    page.wait_for_load_state('networkidle')

    # Select luigi-laser
    page.locator('select').first.select_option('luigi-laser')
    page.locator('button:has-text("Accedi")').click()
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1000)

    print("    [OK] Logged in as luigi-laser")

    print("\n[2] Navigate to laser.html...")
    page.goto('http://localhost:5000/laser.html')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    print("    [OK] Loaded")

    print("\n[3] Check page content...")
    text = page.locator('body').text_content()

    # Look for order data
    has_meccanica = 'Meccanica' in text or 'meccanica' in text.lower()
    has_piastra = 'Piastra' in text or 'piastra' in text.lower()
    has_angolare = 'Angolare' in text or 'angolare' in text.lower()

    print(f"    Client 'Meccanica': {'[OK]' if has_meccanica else '[NO]'}")
    print(f"    Article 'Piastra': {'[OK]' if has_piastra else '[NO]'}")
    print(f"    Article 'Angolare': {'[OK]' if has_angolare else '[NO]'}")

    # Count order cards
    cards = page.locator('.order-card').count()
    print(f"\n    Order cards found: {cards}")

    if cards > 0:
        print("\n[4] Order details:")
        for i in range(min(2, cards)):
            try:
                title = page.locator('.order-card').nth(i).locator('.order-title').text_content()
                print(f"      Order {i+1}: {title[:50]}")
            except:
                pass

    print("\n[5] Screenshot...")
    page.screenshot(path='laser-with-login.png', full_page=True)
    print("    Saved: laser-with-login.png")

    print("\n" + "="*70)
    if has_meccanica and cards > 0:
        print("SUCCESS! Orders displaying correctly!")
    else:
        print("ISSUE: Orders not displaying despite login")

    browser.close()

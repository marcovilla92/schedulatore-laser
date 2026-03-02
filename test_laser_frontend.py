#!/usr/bin/env python3
"""Debug laser.html frontend"""
from playwright.sync_api import sync_playwright

print("Testing laser.html frontend...")
print("="*70)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Capture console messages
    console_logs = []
    page.on('console', lambda msg: console_logs.append({
        'type': msg.type,
        'text': msg.text
    }))

    print("\n[1] Navigate to laser.html...")
    page.goto('http://localhost:5000/laser.html')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    print("[2] Check for orders on page...")
    text = page.locator('body').text_content()

    # Look for key indicators
    checks = {
        "Page title contains 'Laser'": 'laser' in text.lower() or 'LASER' in text,
        "Orders section visible": 'ordine' in text.lower() or 'order' in text.lower(),
        "Client names visible": 'Meccanica' in text or 'cliente' in text.lower(),
        "Quantity shown": 'qty' in text.lower() or 'quantita' in text.lower(),
    }

    print("\nPage content checks:")
    for check, result in checks.items():
        status = "[OK]" if result else "[NO]"
        print(f"  {status} {check}")

    print("\n[3] Console messages:")
    for log in console_logs[:5]:
        print(f"  [{log['type'].upper()}] {log['text'][:80]}")

    print("\n[4] Check API endpoint directly...")
    try:
        api_response = page.evaluate('''async () => {
            try {
                const resp = await fetch('/api/phase/LASER/orders');
                const data = await resp.json();
                return {
                    status: resp.status,
                    count: data.length,
                    first: data.length > 0 ? data[0].cliente : null
                };
            } catch (e) {
                return { error: e.message };
            }
        }''')
        print(f"  API /api/phase/LASER/orders: {api_response}")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n[5] Take screenshot...")
    page.screenshot(path='laser-frontend-debug.png', full_page=True)
    print("  Saved: laser-frontend-debug.png")

    print("\n[6] Look for specific HTML elements...")
    try:
        orders_div = page.locator('[class*="order"], [id*="order"]').count()
        print(f"  Found {orders_div} order-related elements")

        cards = page.locator('[class*="card"], [class*="order"]').count()
        print(f"  Found {cards} card/order elements")
    except:
        pass

    print("\n[7] Try to find order by cliente name...")
    if 'Meccanica' in text:
        print("  [OK] Found 'Meccanica' on page!")
    else:
        print("  [NO] 'Meccanica' not found - orders not displaying")

    browser.close()

print("\n" + "="*70)
print("CONCLUSION:")
print("If 'Meccanica' not found: laser.html not loading orders from API")
print("Check browser console for JavaScript errors")

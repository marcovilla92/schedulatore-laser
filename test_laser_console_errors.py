#!/usr/bin/env python3
"""Check console errors in laser.html"""
from playwright.sync_api import sync_playwright

print("Checking laser.html console for errors...")
print("="*70)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Capture ALL console messages (not just errors)
    console_messages = []
    def log_console(msg):
        console_messages.append({
            'type': msg.type,
            'text': msg.text,
            'location': msg.location if hasattr(msg, 'location') else None
        })

    page.on('console', log_console)

    # Also capture page errors
    page.on('pageerror', lambda err: print(f"PAGE ERROR: {err}"))

    # Login
    print("\n[1] Logging in...")
    page.goto('http://localhost:5000/login.html')
    page.wait_for_load_state('networkidle')
    page.locator('select').first.select_option('luigi-laser')
    page.locator('button:has-text("Accedi")').click()
    page.wait_for_load_state('networkidle')

    # Go to laser.html
    print("[2] Loading laser.html...")
    page.goto('http://localhost:5000/laser.html')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(3000)

    print("\n[3] Console messages captured:")
    if console_messages:
        for msg in console_messages:
            print(f"\n  [{msg['type'].upper()}] {msg['text'][:100]}")
            if msg['location']:
                print(f"          at {msg['location']}")
    else:
        print("  (No console messages)")

    print("\n[4] Check for order cards in DOM...")
    cards = page.locator('.order-card').count()
    print(f"  Order cards found: {cards}")

    if cards == 0:
        print("\n  Checking ordersContainer...")
        container = page.locator('#ordersContainer')
        html = container.inner_html()
        print(f"  Container HTML: {html[:200]}")

    print("\n[5] Try manual API call from page...")
    try:
        result = page.evaluate('''async () => {
            try {
                console.log("Fetching /api/phase/LASER/orders");
                const resp = await fetch("/api/phase/LASER/orders");
                console.log("Response status:", resp.status);
                const data = await resp.json();
                console.log("Data:", data.length);
                return {success: true, count: data.length};
            } catch (e) {
                console.error("API Error:", e.message);
                return {error: e.message};
            }
        }''')
        print(f"  API Result: {result}")
    except Exception as e:
        print(f"  Evaluation error: {e}")

    browser.close()

print("\n" + "="*70)
print("If no console errors but no cards: renderOrders() may not be called")

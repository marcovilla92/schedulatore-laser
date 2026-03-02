#!/usr/bin/env python3
"""
Debug: Check browser console for JavaScript errors on approva-ordine page
"""
import sys
from playwright.sync_api import sync_playwright

def test_console_debug():
    """Check for console errors"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Capture console messages
        console_messages = []
        page.on('console', lambda msg: console_messages.append({
            'type': msg.type,
            'text': msg.text,
            'location': msg.location
        }))

        print("Logging in as marco-admin...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')
        page.locator('select:first-of-type').select_option('marco-admin')
        page.locator('button:has-text("Accedi al Dashboard")').click()
        page.wait_for_load_state('networkidle')

        print("Navigating to approva-ordine.html...")
        page.goto('http://localhost:5000/approva-ordine.html')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(3000)

        print("\n" + "="*60)
        print("CONSOLE OUTPUT:")
        print("="*60)

        if console_messages:
            for msg in console_messages:
                print(f"[{msg['type'].upper()}] {msg['text']}")
                if msg['location']:
                    print(f"        at {msg['location']}")
        else:
            print("No console messages captured")

        # Check page HTML structure
        print("\n" + "="*60)
        print("PAGE STRUCTURE CHECK:")
        print("="*60)

        # Get the rendered HTML
        html_content = page.content()

        # Look for key elements
        if '<table' in html_content:
            print("[OK] Table element present in HTML")
        else:
            print("[FAIL] Table element NOT in HTML")

        if 'renderArticles' in html_content:
            print("[OK] renderArticles function defined in HTML")
        else:
            print("[FAIL] renderArticles function NOT in HTML")

        if 'loadOrder' in html_content:
            print("[OK] loadOrder function defined in HTML")
        else:
            print("[FAIL] loadOrder function NOT in HTML")

        # Check for DOMContentLoaded listener
        if 'DOMContentLoaded' in html_content:
            print("[OK] DOMContentLoaded listener defined")
        else:
            print("[FAIL] DOMContentLoaded listener NOT defined")

        # Check for renderArticles call
        if 'renderArticles()' in html_content:
            print("[OK] renderArticles() called in script")
        else:
            print("[FAIL] renderArticles() NOT called")

        # Try to manually call renderArticles
        print("\n" + "="*60)
        print("MANUAL FUNCTION EXECUTION:")
        print("="*60)

        try:
            result = page.evaluate('''() => {
                // Check if renderArticles is defined
                if (typeof renderArticles === 'function') {
                    return 'renderArticles function exists';
                } else {
                    return 'renderArticles function NOT found';
                }
            }''')
            print(f"renderArticles check: {result}")
        except Exception as e:
            print(f"Error checking renderArticles: {e}")

        # Check window globals
        try:
            globals_check = page.evaluate('''() => {
                return {
                    hasOrderData: typeof orderData !== 'undefined',
                    hasLoadOrder: typeof loadOrder !== 'undefined',
                    hasRenderArticles: typeof renderArticles !== 'undefined',
                    hasParseDoc: typeof parseDoc !== 'undefined'
                };
            }''')
            print(f"Window globals: {globals_check}")
        except Exception as e:
            print(f"Error checking globals: {e}")

        # Take screenshot for visual verification
        page.screenshot(path='test-console-debug.png', full_page=True)
        print("\nScreenshot saved: test-console-debug.png")

        browser.close()
        return True

if __name__ == '__main__':
    try:
        test_console_debug()
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

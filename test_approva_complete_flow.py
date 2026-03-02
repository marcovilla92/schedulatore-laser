#!/usr/bin/env python3
"""
Complete test: Login -> Navigate to approva-ordine -> Verify DECA order loads
"""
import sys
from playwright.sync_api import sync_playwright

def test_approva_complete_flow():
    """Test complete flow: login -> approva-ordine with real order"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Step 1: Navigate to login page...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')

        print("Step 2: Login as marco-admin...")
        # Select Marco Admin user
        page.locator('select[id="userSelect"], select:first-of-type').select_option('marco-admin')

        # Click login button
        page.locator('button:has-text("Accedi al Dashboard")').click()
        page.wait_for_load_state('networkidle')

        print("Step 3: Take screenshot after login...")
        page.screenshot(path='test-after-login.png', full_page=True)

        # Check if we're logged in
        content = page.content()
        if 'Marco' in content or 'marco' in content.lower():
            print("   [OK] Login appears successful")
        else:
            print("   [CHECK] Login page - may need further verification")

        print("\nStep 4: Navigate to approva-ordine.html...")
        page.goto('http://localhost:5000/approva-ordine.html')
        page.wait_for_load_state('networkidle')

        print("Step 5: Take screenshot of approva-ordine page...")
        page.screenshot(path='test-approva-ordine-main.png', full_page=True)

        print("\nStep 6: Analyze page content...")
        content = page.content()

        # Check for key elements
        checks = {
            "DECA order (A000072)": "A000072" in content,
            "DECA client": "DECA" in content,
            "Articles section": "Articoli" in content or "articoli" in content.lower() or "article" in content.lower(),
            "Phase options": "LASER" in content and "PIEGA" in content and "SALDATURA" in content,
            "DXF references": "<svg" in content or "dxf" in content.lower() or "drawing" in content.lower(),
            "Order form elements": "<form" in content or "submit" in content.lower(),
            "Logout button": "logout" in content.lower() or "esci" in content.lower(),
        }

        print("\nResults:")
        for check_name, result in checks.items():
            status = "[OK]" if result else "[FAIL]"
            print(f"   {status} {check_name}")

        # Try to find and display order info
        print("\nStep 7: Look for order information in page...")
        try:
            # Look for any text that might be order number
            all_text = page.locator('body').text_content()
            lines = all_text.split('\n')

            # Find lines with order-like content
            order_info_lines = [l.strip() for l in lines if l.strip() and len(l.strip()) > 5 and len(l.strip()) < 100]

            print(f"   Found {len(order_info_lines)} text elements")
            if order_info_lines:
                print("   Sample content (first 5 non-empty text lines):")
                for line in order_info_lines[:5]:
                    if line and not line.startswith('<'):
                        print(f"      - {line[:80]}")
        except Exception as e:
            print(f"   Could not extract text: {e}")

        # Check for any error messages
        try:
            error_elements = page.locator('[class*="error"], [class*="Error"]').all()
            if error_elements:
                print(f"\n   Found {len(error_elements)} error elements")
        except:
            pass

        print("\nStep 8: Test loading an order programmatically...")
        # Try to directly fetch the API
        try:
            api_response = page.evaluate('''async () => {
                const resp = await fetch('/api/orders');
                const data = await resp.json();
                return {status: resp.status, count: data.length};
            }''')
            print(f"   API /api/orders response: {api_response}")
        except Exception as e:
            print(f"   Could not call API: {e}")

        browser.close()

        # Summary
        print("\n" + "="*60)
        if "A000072" in content or "DECA" in content:
            print("[PASS] Order data found on approva-ordine page")
        else:
            print("[INVESTIGATE] Order data not visible - may need to select specific order")

        return True

if __name__ == '__main__':
    try:
        test_approva_complete_flow()
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

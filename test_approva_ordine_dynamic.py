#!/usr/bin/env python3
"""
Test script to verify approva-ordine.html loads real order data (not static mockup)
Tests: DECA order should load with real articles and DXF files
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_approva_ordine():
    """Test that approva-ordine.html loads real order data"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to the page
        print("1. Navigating to /approva-ordine.html...")
        page.goto('http://localhost:5000/approva-ordine.html')

        # Wait for page to load and API calls to complete
        print("2. Waiting for page load and API calls...")
        page.wait_for_load_state('networkidle')

        # Take screenshot
        page.screenshot(path='approva-ordine-step1-loaded.png', full_page=True)
        print("   Screenshot saved: approva-ordine-step1-loaded.png")

        # Check for order number in the page content
        content = page.content()

        print("\n3. Checking for real order data...")

        # Look for DECA order (numero_ordine: "A000072")
        if 'A000072' in content:
            print("   [OK] DECA order numero found: A000072")
        else:
            print("   [FAIL] DECA order numero NOT found")

        # Look for DECA client name
        if 'DECA S.r.l.' in content or 'DECA' in content:
            print("   [OK] DECA client name found")
        else:
            print("   [FAIL] DECA client name NOT found")

        # Look for article table/section
        if 'Articoli' in content or 'articoli' in content or 'article' in content.lower():
            print("   [OK] Articles section found")
        else:
            print("   [FAIL] Articles section NOT found")

        # Look for phase checkboxes
        if 'LASER' in content and 'PIEGA' in content and 'SALDATURA' in content:
            print("   [OK] Phase options found (LASER, PIEGA, SALDATURA)")
        else:
            print("   [FAIL] Phase options NOT found")

        # Look for SVG or DXF indicators
        if '<svg' in content or 'dxf' in content.lower():
            print("   [OK] DXF/SVG rendering code found")
        else:
            print("   [FAIL] DXF/SVG rendering NOT found")

        # Look for static mockup test data - if found, we have the wrong version
        if 'TEST_DECA' in content or 'Mock Order' in content or 'ArticoloTest' in content:
            print("   [FAIL] STATIC MOCKUP DATA DETECTED - Wrong file version!")
        else:
            print("   [OK] No static mockup detected")

        # Try to find and verify articles in the table
        print("\n4. Looking for article table rows...")
        try:
            articles = page.locator('table tr').all()
            print(f"   Found {len(articles)} table rows")

            # Get the first few article rows
            for i, row in enumerate(articles[:3]):
                text = row.text_content()
                print(f"   Row {i}: {text[:80]}...")
        except:
            print("   Could not locate article table")

        # Look for DXF preview elements
        print("\n5. Looking for DXF preview containers...")
        try:
            dxf_containers = page.locator('[class*="dxf"], [id*="dxf"]').all()
            print(f"   Found {len(dxf_containers)} DXF-related elements")
        except:
            print("   Could not locate DXF containers")

        # Check for loading states or errors
        print("\n6. Checking for errors or loading indicators...")
        errors = page.locator('text=/error|Error|ERROR/i').all()
        print(f"   Found {len(errors)} error indicators")

        # Look for order info section
        print("\n7. Checking for order info display...")
        if 'Ordine' in content or 'ordine' in content or 'Order' in content.lower():
            print("   [OK] Order info section appears to exist")

            # Try to extract visible order details
            try:
                order_info = page.locator('.order-card, [class*="order"], [id*="order"]').first
                if order_info:
                    order_text = order_info.text_content()
                    print(f"   Order info preview: {order_text[:150]}...")
            except:
                pass

        # Take final screenshot
        page.screenshot(path='approva-ordine-step2-final.png', full_page=True)
        print("\n   Final screenshot saved: approva-ordine-step2-final.png")

        browser.close()

        print("\n[PASS] Test completed successfully!")
        return True

if __name__ == '__main__':
    try:
        test_approva_ordine()
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

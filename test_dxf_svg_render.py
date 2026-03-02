"""Test DXF SVG rendering"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print("\nDXF SVG RENDERING TEST")
    print("="*70 + "\n")

    # Upload
    page.goto('http://localhost:5000/login.html')
    page.wait_for_load_state('networkidle')
    page.locator('select#operatorSelect').select_option('giulia-impiegata')
    page.locator('button:has-text("Accedi")').click()
    page.wait_for_load_state('networkidle')

    page.goto('http://localhost:5000/carica-ordine.html')
    page.wait_for_load_state('networkidle')
    page.locator('#pdf-input').set_input_files("072-24 Ordine Ls - C23-304-02e03 -.pdf")
    page.wait_for_timeout(800)
    page.locator('#dxf-input').set_input_files([
        '072-24/12A401102-00.dxf',
        '072-24/12A402101-00.dxf',
        '072-24/12B200103.dxf'
    ])
    page.wait_for_timeout(1000)
    page.locator('button:has-text("CARICA ORDINE")').click()
    page.wait_for_load_state('networkidle')
    print("[1] Order uploaded with 3 DXF files")

    # View
    page.evaluate('''
        localStorage.setItem('currentUser', JSON.stringify({
            id: 'marco-admin',
            role: 'Supervisore'
        }));
    ''')

    page.goto('http://localhost:5000/approva-ordine.html', wait_until='domcontentloaded')
    page.wait_for_load_state('domcontentloaded')
    page.wait_for_timeout(3000)

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(2000)

    print("[2] Page loaded, scrolled to latest order\n")

    # Check for SVG rendering
    svgs = page.locator('svg').all()
    print(f"[3] SVG elements found: {len(svgs)}")

    if len(svgs) > 0:
        print("    [SUCCESS] DXF geometry is being rendered!")
        svg = svgs[0]
        lines = page.locator('line').all()
        circles = page.locator('circle').all()
        print(f"    Lines in drawing: {len(lines)}")
        print(f"    Circles in drawing: {len(circles)}")

    # Check tabs
    tabs = page.locator('[id^="dxf-tab-"]').all()
    print(f"\n[4] DXF tabs: {len(tabs)}")

    # Click second tab
    if len(tabs) > 1:
        print("\n[5] Clicking second tab to view different drawing...")
        tabs[1].click()
        page.wait_for_timeout(1000)

        svgs_after = page.locator('svg').all()
        print(f"    SVG found after tab click: {len(svgs_after) > 0}")

    # Take screenshot
    print("\n[6] Taking screenshot...")
    page.screenshot(path='dxf_svg_render_result.png', full_page=True)
    print("    Saved: dxf_svg_render_result.png")

    print("\n" + "="*70)
    print("EXPECTED: You should see technical drawings rendered in the preview!")
    print("="*70 + "\n")

    page.wait_for_timeout(10000)
    browser.close()

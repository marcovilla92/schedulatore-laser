"""Test DXF rendering with three-dxf library"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print("\n" + "="*70)
    print("TEST: DXF Rendering with three-dxf")
    print("="*70)

    # Capture console
    console_logs = []
    page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

    # Upload order
    print("\n[1] Upload order with DXF...")
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
    print("[OK]")

    # View approva-ordine
    print("\n[2] View approva-ordine with DXF preview...")
    page.evaluate('''
        localStorage.setItem('currentUser', JSON.stringify({
            id: 'marco-admin',
            role: 'Supervisore',
            permissions: ['supervisione']
        }));
    ''')

    page.goto('http://localhost:5000/approva-ordine.html', wait_until='domcontentloaded')
    page.wait_for_load_state('domcontentloaded')
    page.wait_for_timeout(3000)

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(2000)

    print("[OK] Page loaded and scrolled")

    # Check for THREE rendering
    print("\n[3] Check DXF rendering...")

    has_three = page.evaluate("typeof THREE !== 'undefined'")
    print(f"    THREE.js loaded: {has_three}")

    has_three_dxf = page.evaluate("typeof window.ThreeDXF !== 'undefined'")
    print(f"    three-dxf loaded: {has_three_dxf}")

    # Check for canvas elements
    canvases = page.locator('canvas').all()
    print(f"    Canvas elements found: {len(canvases)}")

    if len(canvases) > 0:
        print("    [SUCCESS] DXF files are being rendered!")
    else:
        print("    [INFO] No canvas yet - may still be rendering")

    # Check console for errors
    print("\n[4] Console messages:")
    errors = [log for log in console_logs if 'error' in log.lower()]
    if errors:
        for err in errors[:3]:
            print(f"    {err}")
    else:
        print("    No errors detected")

    dxf_logs = [log for log in console_logs if 'DXF' in log or 'Rendered' in log]
    for log in dxf_logs[:5]:
        print(f"    {log}")

    # Check tabs
    tabs = page.locator('[id^="dxf-tab-"]').all()
    print(f"\n[5] DXF tabs: {len(tabs)} found")

    # Take screenshot
    page.screenshot(path='dxf_three_test.png', full_page=True)
    print("\n[6] Screenshot saved: dxf_three_test.png")

    print("\n" + "="*70)
    print("Browser stays open for 10 seconds for visual inspection")
    print("="*70 + "\n")

    page.wait_for_timeout(10000)
    browser.close()

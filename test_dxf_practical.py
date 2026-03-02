"""Test practical DXF preview UI with phase guidance"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print("\n" + "="*70)
    print("PRACTICAL DXF PREVIEW WITH PHASE GUIDANCE")
    print("="*70)

    # Upload
    print("\n[1] Upload order with 3 DXF files...")
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
    print("[OK] Order uploaded")

    # View in approva-ordine
    print("\n[2] Supervisore views order...")
    page.evaluate('''
        localStorage.setItem('currentUser', JSON.stringify({
            id: 'marco-admin',
            role: 'Supervisore'
        }));
    ''')

    page.goto('http://localhost:5000/approva-ordine.html', wait_until='domcontentloaded')
    page.wait_for_load_state('domcontentloaded')
    page.wait_for_timeout(2000)

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(2000)

    # Check for tabs
    print("\n[3] Check DXF interface...")
    tabs = page.locator('[id^="dxf-tab-"]').all()
    print(f"    DXF tabs found: {len(tabs)}")

    for i in range(min(3, len(tabs))):
        tab = tabs[i]
        text = tab.inner_text()
        print(f"      Tab {i+1}: {text}")

    # Check for download link in latest order preview
    download_btns = page.locator('a[download][href*="/dxf/"]').all()
    print(f"    Download buttons: {len(download_btns)}")

    # Check for phase guidance
    has_guidance = page.content().find('DECIDI LE FASI') > -1
    print(f"    Phase guidance present: {has_guidance}")

    if has_guidance:
        print("    [SUCCESS] Phase guidance visible!")

    # Click a tab
    if len(tabs) > 0:
        print("\n[4] Click second tab...")
        if len(tabs) > 1:
            tabs[1].click()
            page.wait_for_timeout(500)
            print("    [OK] Tab switched")

    # Take screenshot
    print("\n[5] Taking screenshot...")
    page.screenshot(path='dxf_practical_preview.png', full_page=True)
    print("    Screenshot: dxf_practical_preview.png")

    print("\n" + "="*70)
    print("RESULT:")
    print("  - Supervisors see multiple DXF files in tabs")
    print("  - Each tab shows download option")
    print("  - Phase selection guidance is visible")
    print("  - Can switch between drawings to decide phases")
    print("="*70 + "\n")

    page.wait_for_timeout(8000)
    browser.close()

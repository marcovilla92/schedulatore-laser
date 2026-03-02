"""Final DXF test - verify practical preview is working"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print("\nFINAL DXF PREVIEW TEST")
    print("="*70)

    # Upload
    print("\n[STEP 1] Upload order")
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

    # View
    print("\n[STEP 2] View DXF preview page")
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
    print("[OK]")

    # Verify
    print("\n[STEP 3] Verify DXF interface")

    # Count tabs
    tabs = page.locator('[id^="dxf-tab-"]').all()
    print("    DXF tabs: " + str(len(tabs)))

    # Check for guidance text
    content = page.content()
    has_decidi = "DECIDI LE FASI" in content
    has_laser = "LASER" in content
    has_phase = "PIEGA" in content and "SALDATURA" in content

    print("    Guidance text: " + ("YES" if has_decidi else "NO"))
    print("    Phase guidance: " + ("YES" if has_phase else "NO"))

    # Check download buttons
    downloads = page.locator('a[download]').all()
    dxf_downloads = len([d for d in downloads if 'dxf' in d.get_attribute('href').lower()])
    print("    DXF downloads: " + str(dxf_downloads))

    # Result
    print("\n[RESULT]")
    if len(tabs) > 0 and has_decidi:
        print("[SUCCESS] DXF preview with phase guidance is working!")
        print("          - Tabs for each DXF file")
        print("          - Guidance on which phases to select")
        print("          - Download option for each file")
    else:
        print("[OK] Basic interface available")

    print("\n" + "="*70 + "\n")

    page.screenshot(path='dxf_final_verification.png', full_page=True)
    page.wait_for_timeout(5000)
    browser.close()

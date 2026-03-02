"""Test DXF files as downloadable technical drawings"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print("\n" + "="*70)
    print("TEST: DXF Files as Downloadable Technical Drawings")
    print("="*70)

    # Login as impiegata
    print("\n[1] Login as impiegata...")
    page.goto('http://localhost:5000/login.html')
    page.wait_for_load_state('networkidle')
    page.locator('select#operatorSelect').select_option('giulia-impiegata')
    page.wait_for_timeout(300)
    page.locator('button:has-text("Accedi")').click()
    page.wait_for_load_state('networkidle')
    print("[OK] Logged in")

    # Upload order with DXF
    print("[2] Upload order with DXF files...")
    page.goto('http://localhost:5000/carica-ordine.html')
    page.wait_for_load_state('networkidle')
    page.locator('#pdf-input').set_input_files("072-24 Ordine Ls - C23-304-02e03 -.pdf")
    page.wait_for_timeout(1000)
    page.locator('#dxf-input').set_input_files([
        '072-24/12A401102-00.dxf',
        '072-24/12A402101-00.dxf',
        '072-24/12B200103.dxf'
    ])
    page.wait_for_timeout(1000)
    page.locator('button:has-text("CARICA ORDINE")').click()
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(500)
    print("[OK] Order uploaded")

    # Switch to supervisore
    print("[3] Switch to supervisore...")
    page.evaluate('''
        localStorage.setItem('currentUser', JSON.stringify({
            id: 'marco-admin',
            name: 'Marco Rossi',
            role: 'Supervisore',
            initials: 'MR',
            phase: 'ALL',
            permissions: ['overview', 'supervisione', 'lavorazione', 'archive']
        }));
    ''')

    # Open approva-ordine
    print("[4] Open approva-ordine.html...")
    page.goto('http://localhost:5000/approva-ordine.html')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Scroll to latest order
    print("[5] Scroll to latest order...")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1500)

    # Check for DXF download links
    print("[6] Verify DXF file links...")
    links = page.locator('a[download]').all()
    print(f"    Found {len(links)} download link(s)")

    dxf_links = [link for link in links if 'dxf' in link.get_attribute('href').lower()]
    print(f"    DXF files available: {len(dxf_links)}")

    for i, link in enumerate(dxf_links[:3]):
        href = link.get_attribute('href')
        text = link.locator('div').first.inner_text() if link.locator('div').first.is_visible() else "N/A"
        print(f"      {i+1}. {text}")
        print(f"         URL: {href}")

    # Take screenshot
    print("\n[7] Take screenshot...")
    page.screenshot(path='dxf_download_ui.png', full_page=True)
    print("    Screenshot saved: dxf_download_ui.png")

    print("\n" + "="*70)
    print("EXPECTED RESULT:")
    print("  - DXF files shown as downloadable cards")
    print("  - Each card has a download button (arrow icon)")
    print("  - Files can be clicked to download")
    print("  - Hover effect shows download action is available")
    print("="*70 + "\n")

    page.wait_for_timeout(10000)
    browser.close()

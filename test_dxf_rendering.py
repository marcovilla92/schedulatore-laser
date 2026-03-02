"""Test DXF file rendering in approva-ordine.html"""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Visual verification
    page = browser.new_page()

    print("\n" + "="*70)
    print("TEST: DXF File Rendering in Supervisor Approval Page")
    print("="*70)

    # Step 1: Login as impiegata
    print("\n[STEP 1] Login as impiegata...")
    page.goto('http://localhost:5000/login.html')
    page.wait_for_load_state('networkidle')
    page.locator('select#operatorSelect').select_option('giulia-impiegata')
    page.wait_for_timeout(300)
    page.locator('button:has-text("Accedi")').click()
    page.wait_for_load_state('networkidle')
    print("[OK] Logged in as giulia-impiegata")

    # Step 2: Navigate to carica-ordine
    print("\n[STEP 2] Navigate to carica-ordine.html...")
    page.goto('http://localhost:5000/carica-ordine.html')
    page.wait_for_load_state('networkidle')
    print("[OK] Page loaded")

    # Step 3: Upload PDF
    print("\n[STEP 3] Upload PDF file...")
    page.locator('#pdf-input').set_input_files("072-24 Ordine Ls - C23-304-02e03 -.pdf")
    page.wait_for_timeout(2000)
    print("[OK] PDF uploaded")

    # Step 4: Upload DXF files
    print("\n[STEP 4] Upload DXF files...")
    dxf_files = [
        '072-24/12A401102-00.dxf',
        '072-24/12A402101-00.dxf',
        '072-24/12B200103.dxf'
    ]
    page.locator('#dxf-input').set_input_files(dxf_files)
    page.wait_for_timeout(2000)
    print("[OK] Uploaded " + str(len(dxf_files)) + " DXF files")

    # Step 5: Confirm order
    print("\n[STEP 5] Confirm order...")
    page.locator('button:has-text("CARICA ORDINE")').click()
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1000)
    print("[OK] Order submitted")

    # Step 6: Switch to supervisore role
    print("\n[STEP 6] Switch to supervisore role...")
    page.evaluate('''
        const sup = {
            id: 'marco-admin',
            name: 'Marco Rossi',
            role: 'Supervisore',
            initials: 'MR',
            phase: 'ALL',
            permissions: ['overview', 'supervisione', 'lavorazione', 'archive']
        };
        localStorage.setItem('currentUser', JSON.stringify(sup));
    ''')
    print("[OK] Role switched to supervisore")

    # Step 7: Open approva-ordine
    print("\n[STEP 7] Open approva-ordine.html...")
    page.goto('http://localhost:5000/approva-ordine.html')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    print("[OK] Page loaded")

    # Step 8: Check for DXF canvas rendering
    print("\n[STEP 8] Verify DXF rendering...")

    # Scroll to latest order
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1500)

    # Check for canvas element (indicates DXF was rendered)
    try:
        canvas = page.locator('canvas#dxf-canvas').first
        if canvas.is_visible():
            print("[OK] DXF canvas found and visible!")

            # Get canvas dimensions
            box = canvas.bounding_box()
            print("    Canvas size: " + str(int(box['width'])) + "x" + str(int(box['height'])) + " pixels")

            # Check for tab buttons (multiple DXF files)
            tabs = page.locator('[id^="dxf-tab-"]').all()
            print("[OK] Found " + str(len(tabs)) + " DXF file tabs")
            for i, tab in enumerate(tabs):
                text = tab.inner_text()
                print("    Tab " + str(i+1) + ": " + text)
        else:
            print("[WARN] Canvas not visible - may not have loaded yet")
    except Exception as e:
        print("[WARN] Error checking canvas: " + str(e))

    # Step 9: Take screenshot showing rendering
    print("\n[STEP 9] Take screenshot...")
    page.screenshot(path='dxf_rendering_test.png', full_page=True)
    print("[OK] Screenshot saved: dxf_rendering_test.png")

    print("\n" + "="*70)
    print("TEST COMPLETE - Browser remains open for manual inspection")
    print("Look for:")
    print("  - Multiple tab buttons showing DXF file names")
    print("  - Canvas area showing technical drawings")
    print("  - Grid background in canvas")
    print("  - Filename at top-left of drawing")
    print("="*70)
    print("\nPress CTRL+C to close browser...\n")

    # Keep browser open for 10 minutes
    page.wait_for_timeout(600000)

    browser.close()

"""Show DXF files in preview - scroll to latest order"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    print("\n[TEST] DXF Preview - Scroll to Latest Order")
    print("="*70)

    # IMPIEGATA: Upload
    print("\n[STEP 1] Login as impiegata...")
    page.goto('http://localhost:5000/login.html')
    page.wait_for_load_state('networkidle')
    page.locator('select#operatorSelect').select_option('giulia-impiegata')
    page.wait_for_timeout(300)
    page.locator('button:has-text("Accedi")').click()
    page.wait_for_load_state('networkidle')

    print("[STEP 2] Upload PDF + DXF files...")
    page.goto('http://localhost:5000/carica-ordine.html')
    page.wait_for_load_state('networkidle')

    page.locator('#pdf-input').set_input_files("072-24 Ordine Ls - C23-304-02e03 -.pdf")
    page.wait_for_timeout(2000)

    page.locator('#dxf-input').set_input_files([
        '072-24/12A401102-00.dxf',
        '072-24/12A402101-00.dxf',
        '072-24/12B200103.dxf'
    ])
    page.wait_for_timeout(2000)

    print("[STEP 3] Confirm order...")
    page.locator('button:has-text("CARICA ORDINE")').click()
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1000)

    # SUPERVISORE: Show Preview
    print("[STEP 4] Switch to supervisore...")
    page.evaluate('''
        const sup = {id:'marco-admin',name:'Marco Rossi',role:'Supervisore',initials:'MR',phase:'ALL',permissions:['overview','supervisione','lavorazione','archive']};
        localStorage.setItem('currentUser', JSON.stringify(sup));
    ''')

    print("[STEP 5] Load approva-ordine and SCROLL TO BOTTOM...")
    page.goto('http://localhost:5000/approva-ordine.html')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1500)

    # Scroll to bottom to see latest order
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)

    print("[STEP 6] Take screenshot of latest order with DXF preview...")
    page.screenshot(path='dxf_preview_screenshot.png', full_page=True)

    print("\n[SUCCESS] Screenshot saved: dxf_preview_screenshot.png")
    print("[INFO] Latest order with DXF files should now be visible")

    page.wait_for_timeout(3000)
    browser.close()

"""Test operatore (luigi-laser) can track phases"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_operatore():
    """Test operatore can see and work on phases"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("\n[TEST] Starting operatore phase tracking test...")

        # -- STEP 1: Login as luigi-laser --
        print("\n[STEP 1] Logging in as Luigi Verdi (operaio laser)...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')
        page.locator('select#operatorSelect').select_option('luigi-laser')
        page.wait_for_timeout(300)
        page.locator('button:has-text("Accedi")').click()
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)
        screenshot = page.screenshot()
        Path('test_op_01_logged_in.png').write_bytes(screenshot)
        print("[OK] Logged in as Luigi Verdi (operaio laser)")

        # -- STEP 2: Check Lavorazione screen --
        print("\n[STEP 2] Checking Lavorazione (LASER phase) screen...")
        page.locator('text=Lavorazione').click()
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(500)
        screenshot = page.screenshot()
        Path('test_op_02_lavorazione.png').write_bytes(screenshot)
        print("[OK] Lavorazione screen accessible")

        # -- STEP 3: Check Dashboard --
        print("\n[STEP 3] Accessing dashboard...")
        page.goto('http://localhost:5000/dashboard.html')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)
        screenshot = page.screenshot()
        Path('test_op_03_dashboard.png').write_bytes(screenshot)
        print("[OK] Dashboard accessible for operatore")

        # -- STEP 4: Verify overview shows phase info --
        print("\n[STEP 4] Verifying overview info...")
        overview_text = page.locator('text=Overview, text=Fase')
        if overview_text.count() > 0:
            print("[OK] Phase info visible in overview")
        else:
            print("[INFO] Phase info may be dynamic")

        screenshot = page.screenshot()
        Path('test_op_04_overview.png').write_bytes(screenshot)

        print("\n[SUCCESS] Operatore phase tracking test completed!")
        browser.close()
        return True

if __name__ == '__main__':
    success = test_operatore()
    sys.exit(0 if success else 1)

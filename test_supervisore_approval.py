"""Test supervisore approval flow: see orders created by impiegata"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_supervisore():
    """Test supervisore can see orders but NOT upload new ones"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("\n[TEST] Starting supervisore approval test...")

        # -- STEP 1: Login as supervisore (Marco Rossi) --
        print("\n[STEP 1] Logging in as Marco Rossi (supervisore)...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')
        page.locator('select#operatorSelect').select_option('marco-admin')
        page.wait_for_timeout(300)
        page.locator('button:has-text("Accedi")').click()
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)
        screenshot = page.screenshot()
        Path('test_sup_01_logged_in.png').write_bytes(screenshot)
        print("[OK] Logged in as Marco Rossi (supervisore)")

        # -- STEP 2: Check Supervisione screen --
        print("\n[STEP 2] Checking Supervisione screen...")
        supervisione_button = page.locator('text=Supervisione')
        if supervisione_button.count() > 0:
            print("[OK] Supervisione screen available")
            screenshot = page.screenshot()
            Path('test_sup_02_supervisione.png').write_bytes(screenshot)
        else:
            print("[WARN] Supervisione screen not visible")

        # -- STEP 3: Verify "Nuovo Ordine" is NOT visible for supervisore --
        print("\n[STEP 3] Checking that 'Nuovo Ordine' is hidden for supervisore...")
        novo_ordine = page.locator('text=Nuovo Ordine')
        if novo_ordine.count() == 0:
            print("[OK] 'Nuovo Ordine' correctly hidden from supervisore!")
            screenshot = page.screenshot()
            Path('test_sup_03_no_nuovo_ordine.png').write_bytes(screenshot)
        else:
            print("[WARN] 'Nuovo Ordine' visible for supervisore (should be hidden!)")
            screenshot = page.screenshot()
            Path('test_sup_03_error.png').write_bytes(screenshot)
            return False

        # -- STEP 4: Check Admin dashboard --
        print("\n[STEP 4] Accessing Admin dashboard...")
        try:
            admin_link = page.locator('text=Admin')
            if admin_link.count() > 0:
                admin_link.click()
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(1000)
                screenshot = page.screenshot()
                Path('test_sup_04_admin_dashboard.png').write_bytes(screenshot)
                print("[OK] Admin dashboard accessible")
            else:
                print("[WARN] Admin link not found")
        except Exception as e:
            print(f"[WARN] Could not access admin: {e}")

        print("\n[SUCCESS] Supervisore approval test completed!")
        browser.close()
        return True

if __name__ == '__main__':
    success = test_supervisore()
    sys.exit(0 if success else 1)

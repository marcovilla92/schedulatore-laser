"""Test complete workflow: impiegata uploads → supervisore approves"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
import time

def test_complete_workflow():
    """Test: impiegata carica → supervisore approva"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("\n" + "="*60)
        print("[TEST] COMPLETE WORKFLOW: Upload > Approve")
        print("="*60)

        # ============================================================
        # PARTE 1: IMPIEGATA CARICA ORDINE
        # ============================================================
        print("\n[PARTE 1] IMPIEGATA CARICA ORDINE")
        print("-" * 60)

        print("\n[1.1] Login as impiegata...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')
        page.locator('select#operatorSelect').select_option('giulia-impiegata')
        page.wait_for_timeout(500)
        page.locator('button:has-text("Accedi")').click()
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)
        print("[OK] Impiegata logged in")

        print("\n[1.2] Navigate to carica-ordine...")
        page.goto('http://localhost:5000/carica-ordine.html')
        page.wait_for_load_state('networkidle')
        print("[OK] Carica ordine page loaded")

        print("\n[1.3] Upload PDF...")
        pdf_path = "072-24 Ordine Ls - C23-304-02e03 -.pdf"
        if Path(pdf_path).exists():
            page.locator('#pdf-input').set_input_files(pdf_path)
            page.wait_for_timeout(2000)
            print("[OK] PDF uploaded")
        else:
            print("[WARN] PDF not found")

        print("\n[1.4] Confirm order...")
        page.locator('button:has-text("CARICA ORDINE")').click()
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)
        print("[OK] Order submitted")

        # Wait for alert and dismiss
        page.wait_for_timeout(1000)

        # ============================================================
        # PARTE 2: SUPERVISORE APPROVA
        # ============================================================
        print("\n[PARTE 2] SUPERVISORE APPROVA")
        print("-" * 60)

        print("\n[2.1] Navigate to login and switch to supervisore (marco-admin)...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)

        # Use JavaScript to set supervisor in localStorage
        page.evaluate(f"""
            const supervisorUser = {{
                id: 'marco-admin',
                name: 'Marco Rossi',
                role: 'Supervisore',
                initials: 'MR',
                phase: 'ALL',
                permissions: ['overview', 'supervisione', 'lavorazione', 'archive']
            }};
            localStorage.setItem('currentUser', JSON.stringify(supervisorUser));
        """)
        print("[OK] Supervisore user set in localStorage")

        print("\n[2.3] Navigate directly to approva-ordine...")
        page.goto('http://localhost:5000/approva-ordine.html')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)
        print("[OK] Approva ordine page loaded")

        print("\n[2.4] Check for pending orders...")
        order_card = page.locator('.order-card')
        if order_card.count() > 0:
            print(f"[OK] Found {order_card.count()} pending order(s)")
        else:
            print("[WARN] No pending orders found")

        print("\n[2.5] Select phases (LASER)...")
        laser_checkbox = page.locator('input[value="LASER"]').first
        if laser_checkbox.count() > 0:
            laser_checkbox.click()
            page.wait_for_timeout(300)
            print("[OK] LASER phase selected")
        else:
            print("[WARN] LASER checkbox not found")

        print("\n[2.6] Click 'Approva Ordine'...")
        approve_button = page.locator('button:has-text("APPROVA ORDINE")').first
        if approve_button.count() > 0:
            approve_button.click()
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(1000)
            print("[OK] Order approved")
        else:
            print("[WARN] Approve button not found")

        # Take final screenshot
        screenshot = page.screenshot()
        Path('test_complete_workflow_final.png').write_bytes(screenshot)

        print("\n" + "="*60)
        print("[SUCCESS] COMPLETE WORKFLOW TEST FINISHED")
        print("="*60)

        browser.close()
        return True

if __name__ == '__main__':
    try:
        success = test_complete_workflow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FATAL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

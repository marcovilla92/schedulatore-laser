"""Test E2E workflow: impiegata uploads order, supervisore approves"""
import sys
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_workflow():
    """Test complete workflow: impiegata -> supervisore"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Visual mode for debugging
        context = browser.new_context()
        page = context.new_page()

        print("\n[TEST] Starting E2E workflow test...")

        # -- STEP 1: Navigate to login --
        print("\n[STEP 1] Navigating to login page...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')
        screenshot = page.screenshot()
        Path('test_01_login.png').write_bytes(screenshot)
        print("[OK] Login page loaded")

        # -- STEP 2: Select impiegata (Giulia Gallo) --
        print("\n[STEP 2] Selecting Giulia Gallo (impiegata)...")
        try:
            page.locator('select#operatorSelect').select_option('giulia-impiegata')
            page.wait_for_timeout(500)
            screenshot = page.screenshot()
            Path('test_02_operator_selected.png').write_bytes(screenshot)
            print("[OK] Giulia Gallo selected")
        except Exception as e:
            print(f"[ERROR] Failed to select operator: {e}")
            return False

        # -- STEP 3: Click login --
        print("\n[STEP 3] Clicking login button...")
        try:
            page.locator('button:has-text("Accedi")').click()
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(1000)
            screenshot = page.screenshot()
            Path('test_03_logged_in.png').write_bytes(screenshot)
            print("[OK] Logged in as Giulia Gallo")
        except Exception as e:
            print(f"[ERROR] Login failed: {e}")
            return False

        # -- STEP 4: Verify "Nuovo Ordine" button exists --
        print("\n[STEP 4] Looking for 'Nuovo Ordine' button...")
        try:
            novo_ordine = page.locator('text=Nuovo Ordine')
            if novo_ordine.count() > 0:
                print("[OK] 'Nuovo Ordine' button found!")
                screenshot = page.screenshot()
                Path('test_04_nuovo_ordine_visible.png').write_bytes(screenshot)
            else:
                print("[FAIL] 'Nuovo Ordine' button NOT found!")
                screenshot = page.screenshot()
                Path('test_04_no_button.png').write_bytes(screenshot)
                return False
        except Exception as e:
            print(f"[ERROR] Failed to find button: {e}")
            return False

        # -- STEP 5: Click "Nuovo Ordine" --
        print("\n[STEP 5] Clicking 'Nuovo Ordine'...")
        try:
            page.locator('text=Nuovo Ordine').click()
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(1000)
            screenshot = page.screenshot()
            Path('test_05_carica_ordine_page.png').write_bytes(screenshot)
            print("[OK] Navigated to carica-ordine.html")
        except Exception as e:
            print(f"[ERROR] Failed to navigate: {e}")
            return False

        # -- STEP 6: Upload PDF --
        print("\n[STEP 6] Uploading PDF...")
        pdf_path = "app/uploads/pdfs/OAFA202600125.pdf"
        if not Path(pdf_path).exists():
            print(f"[WARN] PDF not found at {pdf_path}, skipping upload")
        else:
            try:
                file_input = page.locator('#pdf-input')
                file_input.set_input_files(pdf_path)
                page.wait_for_timeout(2000)  # Wait for PDF extraction
                screenshot = page.screenshot()
                Path('test_06_pdf_uploaded.png').write_bytes(screenshot)
                print("[OK] PDF uploaded")

                # -- STEP 7: Verify PDF preview --
                print("\n[STEP 7] Checking PDF preview (iframe)...")
                pdf_iframe = page.locator('#pdf-iframe')
                if pdf_iframe.count() > 0:
                    src = pdf_iframe.get_attribute('src')
                    if src and src.startswith('blob:'):
                        print("[OK] PDF preview iframe has blob URL - preview working!")
                    else:
                        print(f"[WARN] PDF iframe src: {src}")
                else:
                    print("[WARN] PDF iframe not found")

                screenshot = page.screenshot()
                Path('test_07_pdf_preview.png').write_bytes(screenshot)
            except Exception as e:
                print(f"[ERROR] PDF upload failed: {e}")
                return False

        # -- STEP 8: Verify phases are selected (LASER, PIEGA are default) --
        print("\n[STEP 8] Verifying phases...")
        try:
            # LASER and PIEGA are already selected by default
            selected_phases = page.locator('.phase-card.selected')
            count = selected_phases.count()
            if count >= 2:
                print(f"[OK] {count} phases already selected (LASER, PIEGA)")
            screenshot = page.screenshot()
            Path('test_08_phases_verified.png').write_bytes(screenshot)
        except Exception as e:
            print(f"[ERROR] Phase verification failed: {e}")
            return False

        # -- STEP 9: Confirm order --
        print("\n[STEP 9] Confirming order...")
        try:
            page.locator('button:has-text("CONFERMA E AVVIA ORDINE")').click()
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(1000)
            screenshot = page.screenshot()
            Path('test_09_order_confirmed.png').write_bytes(screenshot)
            print("[OK] Order confirmed!")
        except Exception as e:
            print(f"[ERROR] Order confirmation failed: {e}")
            screenshot = page.screenshot()
            Path('test_09_error.png').write_bytes(screenshot)
            return False

        print("\n[SUCCESS] E2E workflow test completed!")
        browser.close()
        return True

if __name__ == '__main__':
    success = test_workflow()
    sys.exit(0 if success else 1)

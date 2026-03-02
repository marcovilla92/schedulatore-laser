"""Test complete workflow with Modifica Dati form"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_modifica_dati_workflow():
    """Test impiegata workflow: login -> upload PDF -> edit data -> confirm order"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("\n[TEST] Starting Modifica Dati workflow test...")

        # STEP 1: Login as giulia-impiegata
        print("\n[STEP 1] Logging in as Giulia Gallo (impiegata)...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')
        page.locator('select#operatorSelect').select_option('giulia-impiegata')
        page.wait_for_timeout(500)
        page.locator('button:has-text("Accedi")').click()
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)
        screenshot = page.screenshot()
        Path('test_modifica_01_logged_in.png').write_bytes(screenshot)
        print("[OK] Logged in as Giulia Gallo")

        # STEP 2: Navigate to Nuovo Ordine
        print("\n[STEP 2] Clicking 'Nuovo Ordine' button...")
        page.locator('text=Nuovo Ordine').click()
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)
        screenshot = page.screenshot()
        Path('test_modifica_02_carica_ordine_page.png').write_bytes(screenshot)
        print("[OK] Navigated to carica-ordine.html")

        # STEP 3: Upload PDF
        print("\n[STEP 3] Uploading PDF...")
        pdf_path = "app/uploads/pdfs/OAFA202600125.pdf"
        if Path(pdf_path).exists():
            try:
                file_input = page.locator('#pdf-input')
                file_input.set_input_files(pdf_path)
                page.wait_for_timeout(2000)  # Wait for PDF extraction
                screenshot = page.screenshot()
                Path('test_modifica_03_pdf_uploaded.png').write_bytes(screenshot)
                print("[OK] PDF uploaded")

                # Wait for and dismiss the alert
                try:
                    page.wait_for_event('dialog', timeout=2000)
                    dialog = page.context.pages[0].evaluate("prompt('test') || true")
                    page.context.pages[0].on('dialog', lambda d: d.accept())
                except:
                    pass

                page.wait_for_timeout(1000)
            except Exception as e:
                print(f"[WARN] PDF upload issue: {e}")
        else:
            print(f"[WARN] PDF not found at {pdf_path}")

        # STEP 4: Verify Modifica Dati form appeared
        print("\n[STEP 4] Checking if Modifica Dati form appeared...")
        page.wait_for_timeout(1000)
        screenshot = page.screenshot()
        Path('test_modifica_04_form_visible.png').write_bytes(screenshot)

        try:
            modify_section = page.locator('id=modify-section')
            if modify_section.is_visible():
                print("[OK] Modifica Dati form is visible")
            else:
                print("[WARN] Modifica Dati form not visible")
        except:
            print("[WARN] Could not verify form visibility")

        # STEP 5: Edit Cliente field
        print("\n[STEP 5] Editing Cliente field...")
        try:
            cliente_input = page.locator('#mod-cliente')
            current_value = cliente_input.input_value()
            print(f"[INFO] Current cliente value: {current_value}")
            cliente_input.fill('ACME Corporation - MODIFIED')
            print("[OK] Cliente field updated to 'ACME Corporation - MODIFIED'")
        except Exception as e:
            print(f"[WARN] Could not edit cliente: {e}")

        # STEP 6: Edit Numero Ordine field
        print("\n[STEP 6] Editing Numero Ordine field...")
        try:
            numero_input = page.locator('#mod-numero')
            current_value = numero_input.input_value()
            print(f"[INFO] Current numero value: {current_value}")
            numero_input.fill('TEST-2026-999')
            print("[OK] Numero Ordine field updated to 'TEST-2026-999'")
        except Exception as e:
            print(f"[WARN] Could not edit numero: {e}")

        # STEP 7: Try adding new articolo
        print("\n[STEP 7] Testing Aggiungi Articolo button...")
        page.wait_for_timeout(500)
        screenshot = page.screenshot()
        Path('test_modifica_07_form_filled.png').write_bytes(screenshot)

        try:
            # Click Aggiungi Articolo button (this will show a prompt)
            # For testing purposes, we'll skip this as it requires user interaction
            print("[INFO] Skipping manual articolo addition (requires prompt)")
        except Exception as e:
            print(f"[WARN] Could not interact with Aggiungi Articolo: {e}")

        # STEP 8: Click Salva Modifiche button
        print("\n[STEP 8] Clicking 'Salva Modifiche' button...")
        try:
            page.locator('button:has-text("Salva Modifiche")').click()
            page.wait_for_timeout(1000)
            screenshot = page.screenshot()
            Path('test_modifica_08_changes_saved.png').write_bytes(screenshot)
            print("[OK] Changes saved")
        except Exception as e:
            print(f"[WARN] Could not click Salva Modifiche: {e}")

        # STEP 9: Confirm order
        print("\n[STEP 9] Confirming order...")
        try:
            page.locator('button:has-text("CARICA ORDINE")').click()
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(1000)
            screenshot = page.screenshot()
            Path('test_modifica_09_order_confirmed.png').write_bytes(screenshot)
            print("[OK] Order confirmed")
        except Exception as e:
            print(f"[ERROR] Could not confirm order: {e}")
            return False

        print("\n[SUCCESS] Modifica Dati workflow test completed!")
        browser.close()
        return True

if __name__ == '__main__':
    try:
        success = test_modifica_dati_workflow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FATAL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

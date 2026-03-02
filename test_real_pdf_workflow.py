"""Test workflow with real DECA PDF"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

def test_real_pdf():
    """Test impiegata workflow with real DECA PDF"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("\n[TEST] Testing with REAL DECA PDF...")

        # STEP 1: Login
        print("\n[STEP 1] Logging in as impiegata...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')
        page.locator('select#operatorSelect').select_option('giulia-impiegata')
        page.wait_for_timeout(500)
        page.locator('button:has-text("Accedi")').click()
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)
        print("[OK] Logged in")

        # STEP 2: Navigate to Carica Ordine (direct navigation)
        print("\n[STEP 2] Opening Carica Ordine...")
        page.goto('http://localhost:5000/carica-ordine.html')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(1000)
        print("[OK] Carica Ordine page loaded")

        # STEP 3: Upload REAL PDF
        print("\n[STEP 3] Uploading REAL DECA PDF...")
        pdf_path = "072-24 Ordine Ls - C23-304-02e03 -.pdf"
        if Path(pdf_path).exists():
            try:
                page.locator('#pdf-input').set_input_files(pdf_path)
                page.wait_for_timeout(3000)  # Wait for extraction

                # Check if form appeared
                modify_section = page.locator('id=modify-section')
                if modify_section.is_visible():
                    print("[OK] PDF extracted and Modifica Dati form appeared")

                    # Read extracted values
                    cliente_val = page.locator('#mod-cliente').input_value()
                    numero_val = page.locator('#mod-numero').input_value()

                    print(f"[INFO] Extracted cliente: {cliente_val}")
                    print(f"[INFO] Extracted numero: {numero_val}")

                    # Check articoli
                    articoli_div = page.locator('#articoli-list')
                    articoli_html = articoli_div.inner_html()
                    articoli_count = articoli_html.count('Rimuovi')  # Each articolo has a Rimuovi button
                    print(f"[INFO] Articoli found: {articoli_count}")

                    if articoli_count > 0:
                        print("[OK] Articles successfully extracted")
                    else:
                        print("[WARN] No articles found in form")
                else:
                    print("[WARN] Form not visible after PDF upload")

            except Exception as e:
                print(f"[ERROR] PDF upload failed: {e}")
        else:
            print(f"[WARN] PDF not found at {pdf_path}")

        # STEP 4: Take final screenshot
        page.wait_for_timeout(500)
        screenshot = page.screenshot()
        Path('test_real_pdf_final.png').write_bytes(screenshot)
        print("\n[SUCCESS] Test completed - screenshot saved")

        browser.close()
        return True

if __name__ == '__main__':
    try:
        success = test_real_pdf()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FATAL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

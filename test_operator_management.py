#!/usr/bin/env python
"""Test operator management: add and delete operators"""

from playwright.sync_api import sync_playwright
import time

def test_operator_management():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("=" * 70)
        print("TEST: Operator Management (Add/Delete)")
        print("=" * 70)

        # Login to admin
        print("\n[1] Logging in as admin...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')

        demo_buttons = page.locator('button.btn-demo')
        demo_buttons.nth(3).click()  # marco-admin
        time.sleep(2)
        page.wait_for_load_state('networkidle')
        print("    [+] Admin logged in")

        # Go to admin page
        print("\n[2] Navigating to admin.html...")
        page.goto('http://localhost:5000/admin.html')
        page.wait_for_load_state('networkidle')
        print("    [+] Admin page loaded")

        # Click Settings
        print("\n[3] Opening Settings...")
        page.locator('.nav-item').filter(has_text="Impostazioni").click()
        time.sleep(1)
        print("    [+] Settings opened")

        # Click Operai e Ruoli tab
        print("\n[4] Clicking Operai e Ruoli tab...")
        page.locator('button.settings-tab').filter(has_text="Operai").click()
        time.sleep(1)
        print("    [+] Tab opened")

        # Get initial operator count
        initial_rows = page.locator('table tbody tr').count()
        print(f"    Initial operators: {initial_rows}")

        # Click "Aggiungi Operaio" button
        print("\n[5] Opening Add Operator modal...")
        page.locator('button:has-text("Aggiungi Operaio")').click()
        time.sleep(1)

        modal = page.locator('#addOperatorModal')
        if modal.count() > 0:
            display = modal.evaluate('el => window.getComputedStyle(el).display')
            if display == 'flex':
                print("    [+] Modal opened")
            else:
                print("    [-] Modal not visible")
                browser.close()
                return
        else:
            print("    [-] Modal not found")
            browser.close()
            return

        # Fill in form with unique ID (timestamp)
        print("\n[6] Filling operator form...")
        import datetime
        unique_id = f"testop-{int(datetime.datetime.now().timestamp())}"
        page.locator('#newUserID').fill(unique_id)
        page.locator('#newUserName').fill('Test Operator')
        page.locator('#newUserRole').select_option('Operaio')
        page.locator('#newUserPhase').select_option('LASER')

        # Check some permissions
        page.locator('#perm-overview').check()
        page.locator('#perm-lavorazione').check()
        print("    [+] Form filled")

        # Submit
        print("\n[7] Submitting form...")
        page.locator('button:has-text("Crea Operaio")').click()
        time.sleep(2)
        page.wait_for_load_state('networkidle')

        # Check if operator was added
        final_rows = page.locator('table tbody tr').count()
        if final_rows > initial_rows:
            print("    [+] Operator added successfully")
            added = True
        else:
            print("    [-] Operator not added")
            added = False

        # Try to delete the operator
        if added:
            print("\n[8] Deleting operator...")
            # Wait a moment for table to fully render
            time.sleep(1)

            # Take screenshot before deletion
            page.screenshot(path='/tmp/before-delete.png', full_page=True)

            # Find the delete button for the new operator
            delete_buttons = page.locator('button:has-text("Elimina")')
            print(f"    Found {delete_buttons.count()} delete buttons")

            if delete_buttons.count() > 0:
                # Click the last delete button (most recent operator)
                delete_buttons.last.click()
                time.sleep(1)

                print("    [+] Delete button clicked")

                # Wait for confirmation modal to appear
                time.sleep(1)

                # Find and click the confirmation button
                confirm_btn = page.locator('#confirmDelete-ok')
                if confirm_btn.count() > 0:
                    confirm_btn.click()
                    print("    [+] Confirmation clicked")
                    time.sleep(2)
                else:
                    # Try finding button by text
                    confirm_btn = page.locator('button:has-text("Elimina")').nth(1)
                    if confirm_btn.count() > 0:
                        confirm_btn.click()
                        print("    [+] Confirmation clicked (by text)")
                        time.sleep(2)
                    else:
                        print("    [-] Confirmation button not found")

                # Take screenshot after deletion
                page.screenshot(path='/tmp/after-delete.png', full_page=True)

                final_rows_after_delete = page.locator('table tbody tr').count()
                print(f"    Rows before: {final_rows}, after: {final_rows_after_delete}")

                if final_rows_after_delete < final_rows:
                    print("    [+] Operator deleted successfully")
                    deleted = True
                else:
                    print("    [-] Operator not deleted")
                    deleted = False
            else:
                print("    [-] Delete button not found")
                deleted = False
        else:
            deleted = False

        browser.close()

        print("\n" + "=" * 70)
        if added and deleted:
            print("[OK] Operator management test PASSED!")
            print("     - Operator created successfully")
            print("     - Operator deleted successfully")
        elif added:
            print("[!] Operator management test PARTIAL")
            print(f"     - Operator created: YES")
            print(f"     - Operator deleted: NO")
        else:
            print("[!] Operator management test FAILED")
            print("     - Operator creation failed")
        print("=" * 70)

if __name__ == '__main__':
    test_operator_management()

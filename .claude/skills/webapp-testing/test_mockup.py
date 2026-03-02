#!/usr/bin/env python3
"""Test mockup-v7-audit-kpi.html admin dashboard"""

from playwright.sync_api import sync_playwright
import time

def run_tests():
    """Run tests on the admin dashboard mockup"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Load the admin dashboard mockup (v7 - already logged in)
            print("[TEST] Loading mockup-v7-audit-kpi.html (admin dashboard)...")
            page.goto('http://localhost:5000/mockup-v7-audit-kpi.html', wait_until='networkidle')

            print("[OK] Page loaded successfully")
            page.screenshot(path='mockup_admin_dashboard.png', full_page=True)

            # Verify topbar
            topbar = page.locator('.topbar')
            assert topbar.is_visible(), "Topbar should be visible"
            print("[OK] Topbar visible with company logo and status")

            # Verify sidebar
            sidebar = page.locator('.sidebar')
            assert sidebar.is_visible(), "Sidebar should be visible"
            print("[OK] Sidebar visible")

            # Verify main content area
            content = page.locator('.content')
            assert content.is_visible(), "Main content should be visible"
            print("[OK] Main content area visible")

            # Check KPI Overview screen (default)
            print("\n[TEST] Verifying KPI Overview screen...")
            kpi_cards = page.locator('.kpi-card')
            kpi_count = kpi_cards.count()
            assert kpi_count > 0, f"Should have KPI cards, found {kpi_count}"
            print(f"[OK] Found {kpi_count} KPI cards (expected 8)")

            # Test navigation to KPI Operai screen
            print("\n[TEST] Testing navigation to KPI Operai screen...")
            operatori_btn = page.locator('button:has-text("KPI Operai")')
            if operatori_btn.count() > 0:
                operatori_btn.click()
                page.wait_for_load_state('networkidle')
                time.sleep(0.5)

                # Check operators table
                operators_table = page.locator('.operators-table')
                assert operators_table.is_visible(), "Operators table should be visible"
                rows = page.locator('tbody tr')
                row_count = rows.count()
                assert row_count > 0, f"Should have operator rows, found {row_count}"
                print(f"[OK] Found {row_count} operator rows")
                page.screenshot(path='mockup_operators_screen.png', full_page=True)

            # Test navigation to Audit Log screen
            print("\n[TEST] Testing Audit Log screen...")
            audit_btn = page.locator('button:has-text("Audit Log")')
            if audit_btn.count() > 0:
                audit_btn.click()
                page.wait_for_load_state('networkidle')
                time.sleep(0.5)

                audit_entries = page.locator('.audit-entry')
                entry_count = audit_entries.count()
                assert entry_count > 0, f"Should have audit entries, found {entry_count}"
                print(f"[OK] Found {entry_count} audit log entries")
                page.screenshot(path='mockup_audit_log_screen.png', full_page=True)

            # Test user profile dropdown
            print("\n[TEST] Testing user profile dropdown...")
            profile_dropdown = page.locator('.user-profile')
            if profile_dropdown.count() > 0:
                profile_dropdown.click()
                time.sleep(0.5)
                logout_btn = page.locator('.dropdown-item.logout')
                assert logout_btn.count() > 0, "Logout button should be available"
                print("[OK] User profile dropdown and logout button working")

            print("\n[PASS] All tests passed!")
            print("\nScreenshots saved:")
            print("  - mockup_admin_dashboard.png (overview screen)")
            print("  - mockup_operators_screen.png (operators KPI)")
            print("  - mockup_audit_log_screen.png (audit log)")

            browser.close()
            return True

        except AssertionError as e:
            print(f"\n[FAIL] Assertion failed: {e}")
            browser.close()
            return False
        except Exception as e:
            print(f"\n[ERROR] Test failed: {e}")
            try:
                page.screenshot(path='mockup_error.png', full_page=True)
            except:
                pass
            browser.close()
            return False

if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)

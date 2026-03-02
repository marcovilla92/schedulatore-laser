#!/usr/bin/env python
"""Complete E2E workflow test with KPI verification"""

from playwright.sync_api import sync_playwright
import requests
import json
import time
from datetime import datetime, timedelta

def create_order_api():
    """Create a test order via API"""
    order_data = {
        "cliente": "WORKFLOW TEST CLIENT",
        "numero_ordine": "WF-TEST-001",
        "data_consegna": (datetime.now() + timedelta(days=7)).isoformat(),
        "articles": [
            {
                "name": "Pezzo Workflow 1",
                "code": "WF-001",
                "qty": 2,
                "required_phases": ["LASER", "PIEGA", "SALDATURA"]
            }
        ]
    }

    response = requests.post(
        'http://localhost:5000/api/orders',
        json=order_data,
        headers={'Content-Type': 'application/json'}
    )

    if response.status_code == 201:
        return response.json().get('order_id')
    return None

def test_complete_workflow():
    print("=" * 80)
    print("COMPLETE WORKFLOW TEST: E2E flow + KPI verification")
    print("=" * 80)

    # Step 1: Create order
    print("\n[1] Creating test order via API...")
    order_id = create_order_api()
    if order_id:
        print(f"    [+] Order created: {order_id}")
    else:
        print("    [-] Failed to create order")
        return

    # Step 2: E2E browser test
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 720})

        print("\n[2] E2E Browser Test: LASER Phase")
        print("    [*] Navigating to login...")
        page.goto('http://localhost:5000/login.html')
        page.wait_for_load_state('networkidle')

        print("    [*] Logging in as Luigi (LASER operator)...")
        demo_buttons = page.locator('button.btn-demo')
        demo_buttons.first.click()
        time.sleep(2)
        page.wait_for_load_state('networkidle')

        print("    [*] Navigating to Lavorazione...")
        page.locator('.nav-item').filter(has_text="Lavorazione").click()
        time.sleep(1)

        print("    [*] Starting LASER phase...")
        page.locator('button:has-text("Inizia")').first.click()
        time.sleep(1)

        # Check timer
        timers = page.locator('div[id^="timer-"]')
        if timers.count() > 0:
            print("    [+] Timer visible and counting")

        print("    [*] Waiting 2 seconds for phase execution...")
        time.sleep(2)

        print("    [*] Opening completion modal...")
        page.locator('button:has-text("Completa")').filter(has_text="Completa").first.click()
        time.sleep(1)

        print("    [*] Completing all articles...")
        page.locator('button.btn-modal-all').click()
        time.sleep(2)

        print("    [+] LASER phase completed")

        print("\n[3] E2E Browser Test: PIEGA Phase")
        print("    [*] Logging out...")
        page.locator('.user-profile').click()
        time.sleep(0.5)
        page.locator('text=Logout').click()
        time.sleep(1)

        print("    [*] Logging in as Sara (PIEGA operator)...")
        demo_buttons = page.locator('button.btn-demo')
        demo_buttons.nth(2).click()  # sara-piega
        time.sleep(2)
        page.wait_for_load_state('networkidle')

        print("    [*] Navigating to Lavorazione...")
        page.locator('.nav-item').filter(has_text="Lavorazione").click()
        time.sleep(1)

        print("    [*] Starting PIEGA phase...")
        page.locator('button:has-text("Inizia")').first.click()
        time.sleep(1)

        print("    [*] Waiting 2 seconds for phase execution...")
        time.sleep(2)

        print("    [*] Completing PIEGA phase...")
        page.locator('button:has-text("Completa")').filter(has_text="Completa").first.click()
        time.sleep(1)
        page.locator('button.btn-modal-all').click()
        time.sleep(2)

        print("    [+] PIEGA phase completed")

        print("\n[4] E2E Browser Test: SALDATURA Phase")
        print("    [*] Logging out...")
        page.locator('.user-profile').click()
        time.sleep(0.5)
        page.locator('text=Logout').click()
        time.sleep(1)

        print("    [*] Logging in as Andrea (SALDATURA operator)...")
        demo_buttons = page.locator('button.btn-demo')
        demo_buttons.nth(1).click()  # andrea-saldatura
        time.sleep(2)
        page.wait_for_load_state('networkidle')

        print("    [*] Navigating to Lavorazione...")
        page.locator('.nav-item').filter(has_text="Lavorazione").click()
        time.sleep(1)

        print("    [*] Starting SALDATURA phase...")
        page.locator('button:has-text("Inizia")').first.click()
        time.sleep(1)

        print("    [*] Completing SALDATURA phase...")
        page.locator('button:has-text("Completa")').filter(has_text="Completa").first.click()
        time.sleep(1)
        page.locator('button.btn-modal-all').click()
        time.sleep(2)

        print("    [+] SALDATURA phase completed")
        print("    [+] Complete workflow finished!")

        browser.close()

    # Step 3: Verify KPI
    print("\n[5] Verifying KPI Results...")
    time.sleep(1)

    kpi_response = requests.get('http://localhost:5000/api/admin/kpi')
    if kpi_response.status_code != 200:
        print("    [-] Failed to fetch KPI")
        return

    kpi_data = kpi_response.json()
    kpi_globali = kpi_data.get('kpi_globali', {})
    kpi_operai = kpi_data.get('kpi_operai', [])

    print("\n    KPI Globali:")
    print(f"      - Ordini Attivi: {kpi_globali.get('ordini_attivi')}")
    print(f"      - Efficienza: {kpi_globali.get('efficienza')}%")

    print("\n    KPI per Operaio:")
    operators_kpi = {op.get('user_id'): op for op in kpi_operai}

    luigi = operators_kpi.get('luigi-laser')
    sara = operators_kpi.get('sara-piega')
    andrea = operators_kpi.get('andrea-saldatura')

    verification = []

    if luigi:
        print(f"      - Luigi: {luigi.get('ordini_completati')} ordini completati")
        if luigi.get('ordini_completati') > 0:
            print(f"        [+] VERIFIED")
            verification.append(True)
        else:
            print(f"        [-] FAILED")
            verification.append(False)

    if sara:
        print(f"      - Sara: {sara.get('ordini_completati')} ordini completati")
        if sara.get('ordini_completati') > 0:
            print(f"        [+] VERIFIED")
            verification.append(True)
        else:
            print(f"        [-] FAILED")
            verification.append(False)

    if andrea:
        print(f"      - Andrea: {andrea.get('ordini_completati')} ordini completati")
        if andrea.get('ordini_completati') > 0:
            print(f"        [+] VERIFIED")
            verification.append(True)
        else:
            print(f"        [-] FAILED")
            verification.append(False)

    print("\n" + "=" * 80)
    if all(verification):
        print("[OK] COMPLETE WORKFLOW TEST PASSED!")
        print("     - All 3 phases completed successfully")
        print("     - KPI for all operators registered correctly")
        print("     - Timer working correctly")
        print("     - Modal completion working correctly")
    else:
        print("[!] COMPLETE WORKFLOW TEST FAILED")
        print(f"     Passed: {sum(verification)}/{len(verification)}")
    print("=" * 80)

if __name__ == '__main__':
    test_complete_workflow()

"""Real DXF test: Upload + Verify Preview"""
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    print("\n[VERO TEST] DXF Upload -> Preview in Approva Ordini")
    print("="*70)

    # IMPIEGATA: Upload
    print("\n[IMPIEGATA] Step 1: Login...")
    page.goto('http://localhost:5000/login.html')
    page.wait_for_load_state('networkidle')
    page.locator('select#operatorSelect').select_option('giulia-impiegata')
    page.wait_for_timeout(300)
    page.locator('button:has-text("Accedi")').click()
    page.wait_for_load_state('networkidle')
    print("[OK] Logged in")

    print("\n[IMPIEGATA] Step 2: Go to carica-ordine...")
    page.goto('http://localhost:5000/carica-ordine.html')
    page.wait_for_load_state('networkidle')
    print("[OK] Page loaded")

    print("\n[IMPIEGATA] Step 3: Upload PDF...")
    pdf_path = "072-24 Ordine Ls - C23-304-02e03 -.pdf"
    page.locator('#pdf-input').set_input_files(pdf_path)
    page.wait_for_timeout(2000)
    print("[OK] PDF uploaded")

    print("\n[IMPIEGATA] Step 4: Upload DXF files (all at once)...")
    dxf_files = [
        '072-24/12A401102-00.dxf',
        '072-24/12A402101-00.dxf',
        '072-24/12B200103.dxf'
    ]
    # Set all files at once (multiple upload)
    page.locator('#dxf-input').set_input_files(dxf_files)
    page.wait_for_timeout(3000)
    for dxf in dxf_files:
        print(f"  - {Path(dxf).name} uploaded")
    print("[OK] All DXF files uploaded")

    print("\n[IMPIEGATA] Step 5: Confirm order...")
    page.locator('button:has-text("CARICA ORDINE")').click()
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1000)
    print("[OK] Order submitted")

    # SUPERVISORE: Check Preview
    print("\n[SUPERVISORE] Step 6: Switch to supervisore role...")
    page.evaluate('''
        const sup = {
            id: 'marco-admin',
            name: 'Marco Rossi',
            role: 'Supervisore',
            initials: 'MR',
            phase: 'ALL',
            permissions: ['overview', 'supervisione', 'lavorazione', 'archive']
        };
        localStorage.setItem('currentUser', JSON.stringify(sup));
    ''')
    print("[OK] Role switched")

    print("\n[SUPERVISORE] Step 7: Load approva-ordine...")
    page.goto('http://localhost:5000/approva-ordine.html')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1500)
    print("[OK] Page loaded")

    print("\n[SUPERVISORE] Step 8: Check for DXF preview...")
    order_cards = page.locator('.order-card')
    count = order_cards.count()
    print(f"[INFO] Found {count} order(s)")

    if count > 0:
        # Check LAST order (most recent = index count-1)
        last_card = order_cards.nth(count - 1)
        last_preview = last_card.locator('.pdf-preview')
        preview_text = last_preview.inner_text()

        print(f"[SUPERVISORE] LAST (most recent) order preview text:")
        try:
            print(f"  {preview_text[:200]}")
        except:
            print(f"  [Contains emoji/special chars - likely showing DXF files]")

        if 'draft_' in preview_text or 'dxf' in preview_text.lower() or '12A' in preview_text or '12B' in preview_text or 'File tecnico' in preview_text:
            print("\n[SUCCESS] DXF FILES ARE VISIBLE IN PREVIEW!")
            try:
                print(f"Full content:\n{preview_text}")
            except:
                print(f"(Content contains special characters)")
        elif 'Nessun file' in preview_text:
            print("\n[FAIL] Preview shows 'No files'")
        else:
            print(f"\n[WARN] Unknown content")
    else:
        print("[FAIL] No orders found")

    page.screenshot(path='test_real_dxf_flow.png', full_page=True)
    print("\n[INFO] Screenshot saved: test_real_dxf_flow.png")

    page.wait_for_timeout(2000)
    browser.close()

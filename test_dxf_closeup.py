"""Close-up test of DXF preview UI for latest order"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.set_viewport_size({"width": 1400, "height": 900})

    # Login and upload
    page.goto('http://localhost:5000/login.html')
    page.wait_for_load_state('networkidle')
    page.locator('select#operatorSelect').select_option('giulia-impiegata')
    page.wait_for_timeout(300)
    page.locator('button:has-text("Accedi")').click()
    page.wait_for_load_state('networkidle')

    page.goto('http://localhost:5000/carica-ordine.html')
    page.wait_for_load_state('networkidle')
    page.locator('#pdf-input').set_input_files("072-24 Ordine Ls - C23-304-02e03 -.pdf")
    page.wait_for_timeout(1000)
    page.locator('#dxf-input').set_input_files([
        '072-24/12A401102-00.dxf',
        '072-24/12A402101-00.dxf',
        '072-24/12B200103.dxf'
    ])
    page.wait_for_timeout(1000)
    page.locator('button:has-text("CARICA ORDINE")').click()
    page.wait_for_load_state('networkidle')

    # Switch to supervisore and open approva-ordine
    page.evaluate('''
        localStorage.setItem('currentUser', JSON.stringify({
            id: 'marco-admin',
            name: 'Marco Rossi',
            role: 'Supervisore',
            initials: 'MR',
            phase: 'ALL',
            permissions: ['overview', 'supervisione', 'lavorazione', 'archive']
        }));
    ''')

    page.goto('http://localhost:5000/approva-ordine.html')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Scroll to bottom to see latest order
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1500)

    # Get latest order card and take focused screenshot
    cards = page.locator('.order-card').all()
    if cards:
        last_card = cards[-1]

        # Scroll it into view
        last_card.scroll_into_view_if_needed()
        page.wait_for_timeout(500)

        # Get the card bounds
        box = last_card.bounding_box()

        # Take screenshot of just the DXF preview section
        dxf_preview = last_card.locator('[id^="dxf-preview-"]').first
        if dxf_preview.is_visible():
            dxf_box = dxf_preview.bounding_box()
            print(f"\nDXF Preview Area:")
            print(f"  Position: ({int(dxf_box['x'])}, {int(dxf_box['y'])})")
            print(f"  Size: {int(dxf_box['width'])}x{int(dxf_box['height'])}")
            print(f"  Content:")

            # Get the HTML content
            html = dxf_preview.inner_html()
            if "File Tecnici" in html:
                print("    [OK] DXF files section found")

                # Count download links
                links = dxf_preview.locator('a').all()
                print(f"    [OK] {len(links)} download link(s) found")

                for i, link in enumerate(links):
                    text = link.inner_text()
                    href = link.get_attribute('href')
                    print(f"      - Link {i+1}: {text.split(chr(10))[0]}")

    # Take full screenshot
    page.screenshot(path='dxf_final_result.png', full_page=True)
    print("\nScreenshot saved: dxf_final_result.png")

    # Show the DXF section clearly - scroll to latest order
    print("\nBrowser will stay open for 15 seconds - look at the latest order")
    print("You should see:")
    print("  - 'FILE TECNICI (3)' header with icon")
    print("  - 3 downloadable DXF files")
    print("  - Each with download icon and filename")
    print("  - 'Scarica per aprire' (Download to open) subtitle\n")

    page.wait_for_timeout(15000)
    browser.close()

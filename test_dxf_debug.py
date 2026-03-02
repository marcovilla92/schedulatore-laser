"""Debug DXF rendering - capture console logs"""
from playwright.sync_api import sync_playwright
import json

def log_console_message(msg):
    """Capture console logs"""
    if msg.type == 'error':
        print(f"[BROWSER ERROR] {msg.text}")
    elif msg.type == 'warning':
        print(f"[BROWSER WARN] {msg.text}")
    else:
        print(f"[BROWSER LOG] {msg.text}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.on("console", log_console_message)

    print("\n" + "="*70)
    print("DXF RENDERING DEBUG TEST")
    print("="*70)

    # Login as impiegata
    print("\n[1] Login...")
    page.goto('http://localhost:5000/login.html')
    page.wait_for_load_state('networkidle')
    page.locator('select#operatorSelect').select_option('giulia-impiegata')
    page.wait_for_timeout(300)
    page.locator('button:has-text("Accedi")').click()
    page.wait_for_load_state('networkidle')

    # Upload order
    print("[2] Upload order...")
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
    page.wait_for_timeout(500)
    print("[OK] Order uploaded")

    # Switch to supervisore
    print("[3] Switch to supervisore...")
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

    # Open approva-ordine
    print("[4] Open approva-ordine...")
    page.goto('http://localhost:5000/approva-ordine.html')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(3000)

    # Check DOM
    print("\n[5] Check page structure...")

    # Find order cards
    order_cards = page.locator('.order-card').count()
    print(f"    Found {order_cards} order card(s)")

    if order_cards > 0:
        # Get last order
        last_order = page.locator('.order-card').last

        # Check for DXF preview div
        dxf_preview = last_order.locator('[id^="dxf-preview-"]').first
        if dxf_preview.is_visible():
            print("    DXF preview div found")

            # Check for tabs
            tabs = last_order.locator('[id^="dxf-tab-"]').all()
            print(f"    Found {len(tabs)} tab button(s)")

            # Check for canvas
            canvas = page.locator('canvas#dxf-canvas').first
            if canvas.is_visible():
                print("    Canvas FOUND and visible")
                box = canvas.bounding_box()
                print(f"    Canvas size: {int(box['width'])}x{int(box['height'])}")
            else:
                print("    Canvas NOT visible")
                # Try to find why
                container = page.locator('[id^="dxf-canvas-container-"]').first
                if container.is_visible():
                    html = container.inner_html()
                    print(f"    Container HTML: {html[:200]}")
        else:
            print("    DXF preview div NOT found")

    # Scroll to latest
    print("\n[6] Scroll to latest order...")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(2000)

    # Take screenshot
    print("[7] Take screenshot...")
    page.screenshot(path='dxf_debug_screenshot.png', full_page=True)
    print("    Screenshot saved: dxf_debug_screenshot.png")

    # Check console for errors during loading
    print("\n[8] Check network requests...")
    # Try to manually render one DXF
    print("\n[9] Test DXF rendering manually...")

    # Check if dxf-parser library loaded
    has_parser = page.evaluate("typeof DxfParser !== 'undefined'")
    print(f"    DxfParser library loaded: {has_parser}")

    # Try to fetch DXF file
    print("\n[10] Test DXF file fetch...")
    try:
        orders_resp = page.evaluate('''
            async function test() {
                const resp = await fetch('/api/orders');
                const orders = await resp.json();
                if (orders.length > 0) {
                    const lastOrder = orders[orders.length - 1];
                    console.log('Last order:', lastOrder.id);
                    const dxfFiles = lastOrder.dxf_files || [];
                    console.log('DXF files:', dxfFiles.length);
                    if (dxfFiles.length > 0) {
                        const fileName = dxfFiles[0].filename || dxfFiles[0].file_name || dxfFiles[0];
                        const dxfUrl = `/api/orders/${lastOrder.id}/dxf/${fileName}`;
                        console.log('DXF URL:', dxfUrl);
                        const dxfResp = await fetch(dxfUrl);
                        console.log('DXF response status:', dxfResp.status);
                        const dxfText = await dxfResp.text();
                        console.log('DXF content length:', dxfText.length);
                        return {
                            orderId: lastOrder.id,
                            fileName: fileName,
                            dxfUrl: dxfUrl,
                            status: dxfResp.status,
                            contentLength: dxfText.length,
                            firstChars: dxfText.substring(0, 100)
                        };
                    }
                }
                return null;
            }
            return await test();
        ''')
        print(f"    Fetch result: {json.dumps(orders_resp, indent=2)}")
    except Exception as e:
        print(f"    Error: {str(e)}")

    print("\n" + "="*70)
    print("DEBUG COMPLETE - Keeping browser open")
    print("="*70 + "\n")

    page.wait_for_timeout(30000)  # Keep open 30 seconds
    browser.close()

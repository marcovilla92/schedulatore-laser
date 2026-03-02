"""Visual test - see DXF preview in browser"""
from pathlib import Path
from playwright.sync_api import sync_playwright

print("\n" + "="*70)
print("APRI IL BROWSER E GUARDA - DXF FILES SARANNO VISIBILI")
print("="*70)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # HEADLESS=FALSE = vedi il browser!
    context = browser.new_context()
    page = context.new_page()

    # IMPIEGATA
    page.goto('http://localhost:5000/login.html')
    page.wait_for_load_state('networkidle')
    page.locator('select#operatorSelect').select_option('giulia-impiegata')
    page.wait_for_timeout(300)
    page.locator('button:has-text("Accedi")').click()
    page.wait_for_load_state('networkidle')

    page.goto('http://localhost:5000/carica-ordine.html')
    page.wait_for_load_state('networkidle')

    print("\n[IMPIEGATA] Uploadando PDF...")
    page.locator('#pdf-input').set_input_files("072-24 Ordine Ls - C23-304-02e03 -.pdf")
    page.wait_for_timeout(2000)

    print("[IMPIEGATA] Uploadando DXF files...")
    page.locator('#dxf-input').set_input_files([
        '072-24/12A401102-00.dxf',
        '072-24/12A402101-00.dxf',
        '072-24/12B200103.dxf'
    ])
    page.wait_for_timeout(2000)
    print("[OK] DXF files uploaded")

    print("[IMPIEGATA] Confirming order...")
    page.locator('button:has-text("CARICA ORDINE")').click()
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1500)
    print("[OK] Order submitted\n")

    # SUPERVISORE
    print("[SUPERVISORE] Setting role...")
    page.evaluate('''
        localStorage.setItem('currentUser', JSON.stringify({
            id:'marco-admin',name:'Marco Rossi',role:'Supervisore',
            initials:'MR',phase:'ALL',
            permissions:['overview','supervisione','lavorazione','archive']
        }));
    ''')

    print("[SUPERVISORE] Opening approva-ordine.html...")
    page.goto('http://localhost:5000/approva-ordine.html')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1500)

    print("\n" + "="*70)
    print("BROWSER APERTO - GUARDA APPROVA-ORDINE.HTML")
    print("SCROLLA IN BASSO PER VEDERE L'ORDINE PIU' RECENTE CON DXF FILES")
    print("="*70)
    print("\nPremi CTRL+C quando hai finito...\n")

    # Keep browser open for 5 minutes
    page.wait_for_timeout(300000)

    browser.close()

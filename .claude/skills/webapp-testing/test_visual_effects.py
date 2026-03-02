#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test React Bits visual effects across all 7 frontend pages."""

from playwright.sync_api import sync_playwright
import time

pages_to_test = [
    ("laser.html", ["Aurora", "Spotlight", "Shimmer"]),
    ("piega.html", ["Aurora", "Spotlight", "Shimmer"]),
    ("saldatura.html", ["Aurora", "Spotlight", "Shimmer"]),
    ("dashboard.html", ["Aurora"]),
    ("welcome.html", ["Aurora"]),
    ("ordini_estratti.html", ["Aurora"]),
    ("archive.html", ["Aurora"]),
]

def check_effect(page, page_name, effect_name):
    """Verify that a visual effect is present in the page CSS."""
    if effect_name == "Aurora":
        # Check for auroraFloat keyframe animation
        result = page.evaluate("""
            () => {
                const html = document.documentElement.innerHTML;
                return html.includes('auroraFloat') && html.includes('filter: blur(40px)');
            }
        """)
        return result

    elif effect_name == "Spotlight":
        # Check for spotlight CSS on order cards
        result = page.evaluate("""
            () => {
                const html = document.documentElement.innerHTML;
                return html.includes('--mouse-x') && html.includes('addSpotlightToCards');
            }
        """)
        return result

    elif effect_name == "Shimmer":
        # Check for shimmer ::after CSS on buttons
        result = page.evaluate("""
            () => {
                const html = document.documentElement.innerHTML;
                return html.includes('translateX(-200%)') && html.includes('translateX(400%)');
            }
        """)
        return result

    return False

def test_visual_effects():
    """Test all visual effects on all pages."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("\n[VISUAL EFFECTS TEST]")
        print("=" * 50)

        all_passed = True

        for page_name, effects in pages_to_test:
            url = f"http://localhost:5000/{page_name}"
            print(f"\n[PAGE] {page_name.upper()}")
            print(f"   URL: {url}")

            try:
                page.goto(url, wait_until="networkidle", timeout=10000)
                time.sleep(0.5)  # Extra time for animations to be defined

                page_passed = True
                for effect in effects:
                    has_effect = check_effect(page, page_name, effect)
                    status = "[OK]" if has_effect else "[FAIL]"
                    print(f"   {status} {effect}")
                    if not has_effect:
                        page_passed = False
                        all_passed = False

                # Take screenshot
                screenshot_path = f"/tmp/{page_name}_effect.png"
                page.screenshot(path=screenshot_path, full_page=True)
                print(f"   [SCREENSHOT] {screenshot_path}")

            except Exception as e:
                print(f"   [ERROR] {str(e)[:80]}")
                all_passed = False

        browser.close()

        print("\n" + "=" * 50)
        if all_passed:
            print("[SUCCESS] All visual effects verified!")
        else:
            print("[FAILED] Some effects failed verification")

        return all_passed

if __name__ == "__main__":
    success = test_visual_effects()
    exit(0 if success else 1)

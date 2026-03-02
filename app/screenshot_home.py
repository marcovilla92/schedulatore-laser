#!/usr/bin/env python
"""Take screenshot of homepage"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    try:
        page.goto('http://localhost:5000', timeout=10000)
        page.wait_for_load_state('networkidle')
        page.screenshot(path='screenshot_home.png', full_page=True)
        print("Screenshot saved: screenshot_home.png")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        browser.close()

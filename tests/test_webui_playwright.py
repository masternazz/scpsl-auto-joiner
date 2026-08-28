from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("width,height", [(800, 600), (960, 640), (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)])
def test_webui_pages_render_without_horizontal_overflow(width, height):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[{id:'1',name:'Private Test Server',ip:'127.0.0.1',port:7777}],groups:[],
              settings:{retry_interval_s:2,max_attempts:0,max_minutes:0,connection_method:'automatic'},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            get_servers: async () => ({servers:[]}), save_setting: async (k,v) => ({settings:{[k]:v}}),
            delete_server: async () => ({ok:true}),
            get_update_status: async () => ({ok:true,update:null}),
            set_theme: async p => ({theme:{preset:p}}), get_calibration_state: async () => ({calibration:{calibrated:false,points:{}}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("h1")
        assert page.locator("body").evaluate("document.documentElement.scrollWidth") <= width
        assert page.locator(".content").evaluate("el => el.scrollHeight >= el.clientHeight")
        assert page.locator(".collapse").evaluate("el => el.getBoundingClientRect().top >= 24 && el.getBoundingClientRect().top <= 42")
        assert page.locator(".collapse").evaluate("el => Math.abs((el.getBoundingClientRect().left + el.offsetWidth / 2) - document.querySelector('.sidebar').getBoundingClientRect().right) < 2")
        page.locator(".collapse").click()
        assert page.locator(".sidebar").evaluate("el => el.classList.contains('collapsed')")
        page.locator(".collapse").click()
        assert page.locator(".sidebar").evaluate("el => !el.classList.contains('collapsed')")
        for target, title in [("servers", "Servers"), ("packs", "Text Packs"), ("diagnostics", "Diagnostics"), ("settings", "Settings"), ("help", "Help"), ("docs", "Documentation"), ("join", "Auto-Join")]:
            page.locator(f".nav-item[data-page='{target}']").click()
            assert page.locator("h1").inner_text() == title
            assert page.locator("body").evaluate("document.documentElement.scrollWidth") <= width
            assert page.locator(".content").evaluate("el => el.scrollHeight >= el.clientHeight")
            if target == "settings":
                assert page.locator("#accentColor").count() == 1
                assert page.locator("#themeEditor").count() == 1
                assert page.locator("#customThemeCss").count() == 0
                assert page.locator("#resetAppearance").count() == 1
                assert page.locator('[data-theme="light"]').count() == 1
                assert page.locator('[data-theme="light-warm"]').count() == 1
                assert page.locator('[data-theme="light-slate"]').count() == 1
                page.locator('[data-theme="light-warm"]').click()
                assert page.locator("html").evaluate("el => el.classList.contains('light-warm')")
                assert page.locator("#checkUpdates").count() == 1
                assert page.locator("#installUpdate").is_hidden()
                page.locator("#checkUpdates").click()
                assert page.locator("#updateStatus").inner_text() == "You are up to date."
                page.locator('[data-theme="light"]').click()
                assert page.locator("html").evaluate("el => el.classList.contains('light-mode')")
                page.locator("#resetAppearance").click()
                assert page.locator("#confirmModal").is_visible()
                assert page.locator("#confirmTitle").inner_text() == "Reset appearance"
                assert "default violet" in page.locator("#confirmMessage").inner_text()
                page.locator("#confirmCancel").click()
                assert page.locator("#confirmModal").is_hidden()
                page.locator("#resetAppearance").click()
                page.locator("#confirmAccept").click()
                assert page.locator("#confirmModal").is_hidden()
            if target == "servers":
                page.wait_for_selector("[data-delete]")
                page.locator("[data-delete]").first.click()
                assert page.locator("#confirmModal").is_visible()
                assert page.locator("#confirmTitle").inner_text() == "Delete saved server"
                page.locator("#confirmCancel").click()
                assert page.locator("[data-delete]").count() == 1
            if target == "docs":
                assert "Custom CSS" in page.locator(".content").inner_text()
                assert "Accent color" in page.locator(".content").inner_text()
        browser.close()

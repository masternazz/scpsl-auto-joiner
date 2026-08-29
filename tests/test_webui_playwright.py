from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).parents[1]


def test_webui_boot_symbols_use_encoding_safe_markup():
    source = (ROOT / "webui" / "index.html").read_text(encoding="utf-8")
    assert "&#8249;" in source
    assert "&#9776;" in source
    assert "&hellip;" in source
    assert "â" not in source
    assert "Ã" not in source


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
                assert page.locator("#audioTools").count() == 1
                assert page.locator('[data-setting="mute_game_audio"]').count() == 1
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


def test_webui_waits_for_delayed_pywebview_bridge():
    """The real WebView bridge arrives after the document script sometimes."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto((ROOT / "webui" / "index.html").as_uri())
        assert page.locator(".boot-state").is_visible()
        page.evaluate("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[],groups:[],settings:{},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}})
          }};
          window.dispatchEvent(new Event('pywebviewready'));
        """)
        page.wait_for_selector("h1")
        assert page.locator("h1").inner_text() == "Auto-Join"
        assert page.locator(".boot-state").count() == 0
        browser.close()


def test_webui_accepts_bridge_that_is_ready_before_boot_listener():
    """A fast WebView2 handshake must not be missed by the boot code."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,version:'0.3.21',servers:[],groups:[],settings:{},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("h1")
        assert page.locator("h1").inner_text() == "Auto-Join"
        assert page.locator(".boot-state").count() == 0
        browser.close()


def test_webui_applies_persisted_theme_and_custom_css():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,version:'0.3.7',servers:[],groups:[],settings:{},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},
              theme:{preset:'light-slate',custom:{compiled:'.app-theme .panel { outline: 3px solid rgb(1, 2, 3); }'}}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("h1")
        page.wait_for_selector(".boot-state", state="detached")
        assert page.locator("html").evaluate("el => el.classList.contains('light-slate')")
        assert page.locator("#storedCustomTheme").count() == 1
        assert page.locator(".panel").first.evaluate("el => getComputedStyle(el).outlineStyle") == "solid"
        browser.close()


def test_webui_parity_controls_are_interactive_without_native_prompts():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("dialog", lambda dialog: (errors.append(f"native dialog: {dialog.type}"), dialog.dismiss()))
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[{id:'1',name:'Private',ip:'127.0.0.1',port:7777}],groups:[],
              settings:{retry_interval_s:2,max_attempts:0,max_minutes:0,connection_method:'automatic',mute_game_audio:false},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            save_server: async (n,ip,p) => ({ok:true,server:{id:'2',name:n,ip,port:p}}),
            save_group: async (n,ids,id) => ({ok:true,group:{id:id||'g1',name:n,server_ids:ids}}),
            save_setting: async (k,v) => { window.savedSettings = window.savedSettings || []; window.savedSettings.push([k,v]); return {ok:true,settings:{[k]:v}}; },
            export_local_data: async () => ({ok:true,path:'export.json'}),
            reset_local_storage: async () => ({ok:true,servers:[],groups:[],settings:{},calibration:{calibrated:false,points:{}}}),
            open_translation_folder: async () => ({ok:true}),
            restore_translation_backup: async () => ({ok:true,packs:{packs:[],active_pack:null}})
            ,search_translation_packs: async () => ({ok:true,results:[{full_name:'owner/pack',html_url:'https://github.com/owner/pack',description:'Test pack',updated_at:'2026-08-28'}]})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("h1")
        page.locator(".nav-item[data-page='servers']").click()
        page.wait_for_selector("#groupEditor")
        page.locator("#addServer").click()
        page.wait_for_selector(".form-modal")
        assert page.locator(".form-modal h2").inner_text() == "Add saved server"
        page.locator("[data-form-cancel]").click()
        page.locator("#addGroup").click()
        assert page.locator(".form-modal h2").inner_text() == "Create server group"
        page.locator("[data-form-cancel]").click()
        page.locator("[data-rename]").first.click()
        assert page.locator(".form-modal h2").inner_text() == "Rename saved server"
        page.locator("[data-form-cancel]").click()
        page.locator(".nav-item[data-page='settings']").click()
        page.wait_for_selector("#storageTools")
        page.wait_for_selector("#advancedSettings")
        page.locator("#navigationMode").select_option("manual")
        page.locator("#accentColor").evaluate("(el) => { el.value = '#123abc'; el.dispatchEvent(new Event('input', {bubbles:true})); }")
        page.wait_for_function("window.savedSettings?.some(([key, value]) => key === 'custom_accent' && value === '#123abc')")
        assert page.locator("html").evaluate("el => getComputedStyle(el).getPropertyValue('--accent').trim()") == "#123abc"
        page.locator(".nav-item[data-page='packs']").click()
        page.wait_for_selector("#packLinkTools")
        page.locator("#searchPacks").click()
        page.wait_for_selector("[data-repo-install]")
        assert errors == []
        browser.close()


def test_server_row_actions_do_not_select_server_or_navigate_away():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[
              {id:'1',name:'Private One',ip:'127.0.0.1',port:7777},
              {id:'2',name:'Private Two',ip:'127.0.0.2',port:7778}],groups:[],
              settings:{},calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            refresh_server_status: async () => ({ok:true,status:{players:1,max_players:20,latency_ms:4}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("h1")
        page.locator(".nav-item[data-page='servers']").click()
        page.wait_for_selector("[data-refresh]")
        page.locator("[data-server='2']").evaluate("el => el.onclick()")
        assert page.locator("h1").inner_text() == "Auto-Join"
        page.locator(".nav-item[data-page='servers']").click()
        page.wait_for_selector("[data-refresh]")
        page.locator("[data-refresh]").first.click()
        assert page.locator("h1").inner_text() == "Servers"
        page.locator("[data-server='2'] main").click()
        assert page.locator("h1").inner_text() == "Auto-Join"
        browser.close()


def test_light_theme_choices_persist_through_the_bridge():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.add_init_script("""
          window.themeCalls = [];
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[],groups:[],settings:{},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            set_theme: async preset => { window.themeCalls.push(preset); return {ok:true,theme:{preset:preset,custom:null}}; }
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("h1")
        page.locator(".nav-item[data-page='settings']").click()
        page.locator('[data-theme="light-warm"]').click()
        page.wait_for_function("window.themeCalls.includes('light-warm')")
        assert page.locator("html").evaluate("el => el.classList.contains('light-warm')")
        assert page.locator("html").evaluate("el => getComputedStyle(el).getPropertyValue('--accent').trim()") == "#8a5a24"
        browser.close()


def test_translation_picker_uses_native_paths_in_webview2():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.add_init_script("""
          window.pickerCalls = [];
          window.importCalls = [];
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[],groups:[],settings:{},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            pick_translation_source: async kind => { window.pickerCalls.push(kind); return {ok:true,path: kind === 'folder' ? 'C:/packs/custom' : 'C:/packs/custom.zip'}; },
            import_translation_pack: async path => { window.importCalls.push(path); return {ok:true,packs:{packs:[],active_pack:null}}; }
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("h1")
        page.locator(".nav-item[data-page='packs']").click()
        page.locator("#pickPack").click()
        page.wait_for_function("window.importCalls.includes('C:/packs/custom.zip')")
        page.locator("#pickFolder").click()
        page.wait_for_function("window.importCalls.includes('C:/packs/custom')")
        assert page.evaluate("window.pickerCalls") == ["file", "folder"]
        browser.close()

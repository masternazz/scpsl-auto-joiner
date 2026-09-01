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


def test_product_expansion_panels_render_without_console_errors():
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.add_init_script("""
          const server = {id:'s1',name:'Private Test',ip:'127.0.0.1',port:7777,tags:[],notes:'',notification_profile:{}};
          window.pywebview={api:{
            get_app_state:async()=>({ok:true,servers:[server],groups:[],settings:{notifications_enabled:true},calibration:{calibrated:false,points:{}},calibration_profiles:{profiles:[],active:null},packs:{packs:[],active_pack:null},theme:{preset:'violet'},storage:{}}),
            get_join_explanations:async()=>({items:[]}), get_recovery_actions:async()=>({actions:[{id:'diagnostics',label:'Open Diagnostics'}]}),
            run_setup_check:async()=>({checks:[{id:'query',label:'A2S server query',ok:null,detail:'Choose a server.'}]}), calibration_target_map:async()=>({targets:[]}),
            save_setting:async(k,v)=>({ok:true,settings:{[k]:v}}), create_backup:async()=>({ok:true}), create_support_bundle:async()=>({ok:true}),
            save_collection:async()=>({ok:true}), get_servers:async()=>({servers:[server]}), get_calibration_state:async()=>({calibration:{calibrated:false,points:{}}}),
            get_update_status:async()=>({ok:true,update:null}), set_theme:async p=>({theme:{preset:p}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("#whyJoinPanel")
        page.locator(".nav-item[data-page='diagnostics']").click()
        page.wait_for_selector("#setupCheckPanel")
        assert page.locator("#setupServer").count() == 1
        page.locator(".nav-item[data-page='settings']").click()
        page.wait_for_selector(".safe-backup-panel")
        assert page.locator('[data-product-setting="slot_alert_actions"]').count() == 1
        assert not errors
        browser.close()


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
        for target, title in [("servers", "Servers"), ("packs", "Text Packs"), ("diagnostics", "Diagnostics"), ("settings", "Settings"), ("help", "Quick start"), ("docs", "Documentation"), ("join", "Auto-Join")]:
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
                page.locator('[data-appearance-mode="light"]').click()
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


def test_webui_exposes_monitoring_discord_and_destination_tools():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,version:'0.3.25',servers:[{id:'s1',name:'Private',ip:'127.0.0.1',port:7777}],groups:[],settings:{},calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            get_monitor_status: async () => ({running:false,servers:0}),
            start_background_monitor: async () => ({ok:true}), stop_background_monitor: async () => ({ok:true}),
            get_discord_status: async () => ({ok:true,enabled:false}), set_discord_enabled: async enabled => ({ok:true,enabled}),
            preview_destination: async () => ({ok:false,error:'invalid'}), import_destination: async () => ({ok:true})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("h1")
        page.locator(".nav-item[data-page='settings']").click()
        assert page.locator("#backgroundMonitor").count() == 1
        assert page.locator("#discordPresence").count() == 1
        assert "Never paste a client secret" in page.locator("#discordApplication").inner_text()
        assert "Names and Join requests stay private" in page.locator("#discordPlayerSharing").inner_text()
        page.locator(".nav-item[data-page='servers']").click()
        assert page.locator("#destinationTools").count() == 1
        page.locator("#destinationInput").fill('{"schema":"scpsl-autojoin.destination"}')
        page.locator("#importDestination").click()
        assert page.locator("#destinationPreview").inner_text() == "Preview the destination before importing."
        browser.close()


def test_servers_exposes_history_and_smart_group_controls():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,version:'0.3.25',servers:[{id:'s1',name:'Private',ip:'127.0.0.1',port:7777,status:{players:4,max_players:20,latency_ms:12}}],groups:[{id:'g1',name:'Favorites',server_ids:['s1'],policy:{strategy:'ordered_retry',minimum_players:0,maximum_fill_percent:100,loop:null}}],settings:{},calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            get_server_insights: async () => ({ok:true,insights:{samples:8,peak_players:8,average_latency_ms:20,full_frequency:0,availability_likelihood:1,periods:{'24h':{},'7d':{},'30d':{}}}}),
            save_server_profile: async () => ({ok:true}), save_group_policy: async () => ({ok:true}),
            get_monitor_status: async () => ({running:false,servers:0})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("h1")
        page.locator(".nav-item[data-page='servers']").click()
        assert page.locator("[data-history='s1']").count() == 1
        assert page.locator("#groupStrategy").count() == 1
        page.locator("[data-history='s1']").click()
        assert page.locator("#serverHistory").is_visible()
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
        page.set_default_timeout(3_000)
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


def test_webui_can_select_and_start_an_ordered_group():
    """Groups are first-class Auto-Join targets, not a hidden Servers action."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.startCalls = [];
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[{id:'s1',name:'Private',ip:'127.0.0.1',port:7777}],
              groups:[{id:'g1',name:'Private fallback',server_ids:['s1']}], settings:{retry_interval_s:2},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            start_join: async (id, type) => { window.startCalls.push({id, type}); return {ok:true}; },
            stop_join: async () => ({ok:true})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("#targetType")
        page.locator("#targetType").select_option("group")
        page.locator("#targetSelect").select_option("g1")
        assert page.locator("#targetSelect").input_value() == "g1"
        assert page.locator("#start").is_disabled() is False
        page.locator("#start").click()
        page.wait_for_timeout(100)
        assert page.evaluate("window.startCalls") == [{"id": "g1", "type": "group"}]
        assert page.evaluate("window.startCalls[0]") == {"id": "g1", "type": "group"}
        browser.close()


def test_webui_shows_existing_appdata_migration_notice():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[{id:'s1',name:'Old private',ip:'127.0.0.1',port:7777}],groups:[],settings:{},
              calibration:{calibrated:true,points:{servers_tab:[100,200]}},packs:{packs:[],active_pack:null},theme:{preset:'violet'},
              storage:{migrated:true,paths:{root:'C:/Users/test/AppData/Local/SCP-SL-Auto-Joiner'}}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.locator(".nav-item[data-page='settings']").click()
        assert page.get_by_text("Imported from existing local data").count() == 1
        browser.close()


def test_webui_renders_structured_retry_and_join_events_in_run_state():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[{id:'s1',name:'Private',ip:'127.0.0.1',port:7777}],groups:[],settings:{retry_interval_s:2},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("#start")
        page.evaluate("window.__appEvent({event:'join_retrying',data:{attempt:4,message:'Server full. Retrying in 2 seconds.'}})")
        assert page.locator(".run-state").inner_text() == "RETRYING"
        assert page.get_by_text("Server full. Retrying in 2 seconds.").count() == 1
        page.evaluate("window.__appEvent({event:'join_succeeded',data:{message:'Connected to server.'}})")
        assert page.locator(".run-state").inner_text() == "JOINED"
        assert page.get_by_text("Connected to server.").count() == 1
        browser.close()


def test_live_join_events_do_not_recreate_the_auto_join_page():
    """Status motion must stay inside the run panel instead of blinking the page."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[{id:'s1',name:'Private',ip:'127.0.0.1',port:7777}],groups:[],settings:{retry_interval_s:2},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector(".run-panel")
        page.evaluate("window.runPanelBeforeEvent = document.querySelector('.run-panel')")

        page.evaluate("window.__appEvent({event:'watching',data:{message:'Watching Private'}})")

        assert page.evaluate("window.runPanelBeforeEvent === document.querySelector('.run-panel')") is True
        browser.close()


def test_webui_renders_watch_and_slot_candidate_states_in_the_run_timeline():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[{id:'s1',name:'Private',ip:'127.0.0.1',port:7777}],groups:[],settings:{retry_interval_s:2},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("#start")
        page.evaluate("window.__appEvent({event:'watching',data:{message:'Watching Private / 18 of 20 players'}})")
        assert page.locator(".run-state").inner_text() == "WATCHING"
        assert "run-watching" in page.locator(".run-panel").get_attribute("class")
        assert page.locator(".timeline .step.current").count() == 1
        page.evaluate("window.__appEvent({event:'slot_candidate',data:{message:'Slot candidate detected / confirming'}})")
        assert page.locator(".run-state").inner_text() == "SLOT CANDIDATE"
        assert "run-slot-candidate" in page.locator(".run-panel").get_attribute("class")
        assert page.locator(".timeline .step.done").count() >= 2
        browser.close()


def test_motion_preference_updates_the_real_renderer_and_respects_reduced_motion():
    """Changing the preference must affect the app root, while OS accessibility wins."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.add_init_script("""
          window.motionCalls = [];
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[],groups:[],settings:{motion_preset:'expressive'},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            save_setting: async (key, value) => { window.motionCalls.push([key, value]); return {ok:true,settings:{[key]:value}}; }
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.locator(".nav-item[data-page='settings']").click()
        assert page.locator("#motionPreset").input_value() == "expressive"
        page.locator("#motionPreset").select_option("contained")
        page.wait_for_function("window.motionCalls.length === 1")
        assert page.locator("html").get_attribute("data-motion") == "contained"
        assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--motion-enter').trim()") == "160ms"
        page.emulate_media(reduced_motion="reduce")
        assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--motion-enter').trim()") == "0ms"
        browser.close()


def test_group_editor_saves_the_visible_member_order():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.groupCalls = [];
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[
              {id:'server-a',name:'First',ip:'127.0.0.1',port:7777},
              {id:'server-b',name:'Second',ip:'127.0.0.1',port:7778}],
              groups:[{id:'group-1',name:'Retry order',server_ids:['server-a','server-b']}],settings:{},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            save_group: async (name, ids, id) => { window.groupCalls.push({name,ids,id}); return {ok:true,group:{id,name,server_ids:ids}}; }
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.locator(".nav-item[data-page='servers']").click()
        page.locator("#mainGroupSelect").select_option("group-1")
        page.locator("[data-main-group-down='server-a']").click()
        page.locator("#mainSaveGroup").click()
        page.wait_for_function("window.groupCalls.length === 1")
        assert page.evaluate("window.groupCalls[0].ids") == ["server-b", "server-a"]
        browser.close()


def test_calibration_wizard_captures_controls_in_required_order():
    controls = ["servers_tab", "direct_connect", "ip_field", "connect_button"]
    labels = ["Servers tab", "Direct Connect button", "Server address field", "Connect button"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.captureCalls = [];
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[],groups:[],settings:{},calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            capture_calibration_point: async name => { window.captureCalls.push(name); return {ok:true,name,point:[100,200]}; },
            save_calibration: async points => ({ok:true,calibration:{calibrated:true,points}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.locator(".nav-item[data-page='diagnostics']").click()
        for control, label in zip(controls, labels):
            assert page.locator("#calibrationControl").inner_text() == label
            page.locator("#captureCalibration").click()
            page.wait_for_function(f"window.captureCalls.includes('{control}')")
        assert page.locator("#saveCalibration").is_enabled()
        browser.close()


def test_help_includes_a_local_readiness_onboarding_panel():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[{id:'s1',name:'Private',ip:'127.0.0.1',port:7777}],groups:[],settings:{},
              calibration:{calibrated:true,points:{servers_tab:[1,2]}},packs:{packs:[],active_pack:null},theme:{preset:'violet'},
              storage:{migrated:false,paths:{root:'C:/Users/test/AppData/Local/SCP-SL-Auto-Joiner'}}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.locator(".nav-item[data-page='help']").click()
        assert page.locator("#onboardingReadiness").count() == 1
        assert "Saved server ready" in page.locator("#onboardingReadiness").inner_text()
        assert "Calibration ready" in page.locator("#onboardingReadiness").inner_text()
        browser.close()


def test_text_packs_page_installs_a_pasted_link_from_the_main_renderer():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.installedLinks = [];
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[],groups:[],settings:{},calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            install_translation_link: async url => { window.installedLinks.push(url); return {ok:true,packs:{packs:[],active_pack:null}}; }
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.locator(".nav-item[data-page='packs']").click()
        page.locator("#directPackLink").fill("https://github.com/example/pack")
        page.locator("#installDirectPackLink").click()
        page.wait_for_function("window.installedLinks.length === 1")
        assert page.evaluate("window.installedLinks") == ["https://github.com/example/pack"]
        browser.close()


def test_settings_main_renderer_exposes_storage_and_advanced_controls():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[],groups:[],settings:{navigation_mode:'automatic',attempt_timeout_s:20,max_unclear:3,browser_refresh_timeout_s:2,group_loop:true,notifications_enabled:true,auto_update:false},calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            save_setting: async (key,value) => ({ok:true,settings:{[key]:value}}),
            export_local_data: async () => ({ok:true,path:'export.json'}),
            reset_local_storage: async () => ({ok:true,servers:[],groups:[],settings:{},calibration:{calibrated:false,points:{}}}),
            open_data_folder: async () => ({ok:true})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.locator(".nav-item[data-page='settings']").click()
        assert page.locator("#mainStorageTools").count() == 1
        assert page.locator("#mainAdvancedSettings").count() == 1
        assert page.locator("#mainOpenDataFolder").count() == 1
        browser.close()


def test_servers_main_renderer_exposes_group_and_remember_workflows():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[{id:'a',name:'First',ip:'127.0.0.1',port:7777},{id:'b',name:'Second',ip:'127.0.0.1',port:7778}],groups:[{id:'g1',name:'Order',server_ids:['a','b']}],settings:{},calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            start_remember: async () => ({ok:true}), save_group: async () => ({ok:true})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.locator(".nav-item[data-page='servers']").click()
        assert page.locator("#mainGroupEditor").count() == 1
        assert page.locator("#rememberServerFromLog").count() == 1
        assert page.locator("[data-main-group-down='a']").count() == 1
        browser.close()


def test_production_page_does_not_load_the_compatibility_script():
    source = (ROOT / "webui" / "index.html").read_text(encoding="utf-8")
    assert "parity.js" not in source


def test_detected_connection_opens_a_prefilled_save_form():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[],groups:[],settings:{},calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            remember_server: async (name,ip,port) => ({ok:true,server:{id:'detected',name,ip,port}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.evaluate("window.__appEvent({event:'server_detected',data:{name:'Private Test',ip:'127.0.0.1',port:7777}})")
        assert page.locator(".form-modal").is_visible()
        assert page.locator("#mainServerFormName").input_value() == "Private Test"
        assert page.locator("#mainServerFormEndpoint").input_value() == "127.0.0.1:7777"
        browser.close()


def test_remember_server_is_a_clear_saved_server_action():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.rememberCalls = 0;
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[],groups:[],settings:{},calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            start_remember: async () => { window.rememberCalls += 1; return {ok:true}; }
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.locator(".nav-item[data-page='servers']").click()
        button = page.locator("#rememberServerFromLog")
        assert button.is_visible()
        assert "Player.log" not in button.get_attribute("title")
        button.click()
        page.wait_for_function("window.rememberCalls === 1")
        assert "Join normally" in page.locator("#rememberServerStatus").inner_text()
        browser.close()


def test_group_editor_can_switch_to_a_new_group_and_include_saved_servers():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_default_timeout(3_000)
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[{id:'a',name:'First',ip:'127.0.0.1',port:7777},{id:'b',name:'Second',ip:'127.0.0.1',port:7778}],groups:[{id:'g1',name:'Existing',server_ids:['a']}],settings:{},calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.locator(".nav-item[data-page='servers']").click()
        page.locator("#mainGroupSelect").select_option("")
        assert page.locator("#mainGroupName").input_value() == ""
        assert page.locator("#mainGroupMembers .member-row").count() == 2
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


def test_webui_feature_controls_are_interactive_without_native_prompts():
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
        page.wait_for_selector("#mainGroupEditor")
        page.locator("#addServer").click()
        page.wait_for_selector(".form-modal")
        assert page.locator(".form-modal h2").inner_text() == "Add saved server"
        page.locator("#mainServerFormCancel").click()
        page.locator("[data-rename]").first.click()
        assert page.locator(".form-modal h2").inner_text() == "Rename saved server"
        page.locator("#mainServerFormCancel").click()
        page.locator(".nav-item[data-page='settings']").click()
        page.wait_for_selector("#mainStorageTools")
        page.wait_for_selector("#mainAdvancedSettings")
        page.locator("#mainNavigationMode").select_option("manual")
        page.locator("#accentColor").evaluate("(el) => { el.value = '#123abc'; el.dispatchEvent(new Event('input', {bubbles:true})); }")
        page.wait_for_function("window.savedSettings?.some(([key, value]) => key === 'custom_accent' && value === '#123abc')")
        assert page.locator("html").evaluate("el => getComputedStyle(el).getPropertyValue('--accent').trim()") == "#123abc"
        page.locator(".nav-item[data-page='packs']").click()
        page.locator("#searchPacks").click()
        page.wait_for_selector("[data-main-repo-install]")
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
        page.locator('[data-appearance-mode="light"]').click()
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


def test_redesigned_pages_expose_remember_theme_and_guides_without_internal_copy():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[{id:'s1',name:'Private',ip:'127.0.0.1',port:7777}],groups:[],
              settings:{retry_interval_s:2,max_attempts:0,max_minutes:0,connection_method:'automatic'},
              calibration:{calibrated:false,points:{}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}}),
            start_remember: async () => ({ok:true}), save_setting: async (k,v) => ({ok:true,settings:{[k]:v}}),
            set_theme: async preset => ({ok:true,theme:{preset,custom:null}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.wait_for_selector("#rememberCurrentServer")
        assert "Player.log" not in page.locator("#rememberCurrentServer").inner_text()
        assert "Player.log" not in page.locator("#rememberCurrentServer").get_attribute("title")
        page.locator(".nav-item[data-page='settings']").click()
        assert page.locator("#appearanceMode").count() == 1
        assert page.locator('[data-appearance-mode="dark"]').count() == 1
        assert page.locator('[data-appearance-mode="light"]').count() == 1
        for token in ["bg", "panel", "text", "muted", "accent", "green", "amber", "red"]:
            assert page.locator(f'[data-theme-token="{token}"]').count() == 1
        page.locator(".nav-item[data-page='help']").click()
        assert page.get_by_role("heading", name="Quick start").count() == 1
        assert page.get_by_text("Choose a destination", exact=True).count() == 1
        page.locator(".nav-item[data-page='docs']").click()
        assert page.locator("#docsNavigation").count() == 1
        assert page.get_by_role("heading", name="In-depth guide").count() == 1
        browser.close()


def test_diagnostics_uses_human_labels_and_hides_raw_calibration_json():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.add_init_script("""
          window.pywebview = {api: {
            get_app_state: async () => ({ok:true,servers:[],groups:[],settings:{},
              calibration:{calibrated:true,points:{servers_tab:[481,99]}},packs:{packs:[],active_pack:null},theme:{preset:'violet'}})
          }};
        """)
        page.goto((ROOT / "webui" / "index.html").as_uri())
        page.locator(".nav-item[data-page='diagnostics']").click()
        assert page.locator("#calibrationControl").inner_text() == "Servers tab"
        assert page.locator("#calPreview pre").count() == 0
        assert "servers_tab" not in page.locator("#calPreview").inner_text()
        browser.close()

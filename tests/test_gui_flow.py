import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QDialog

import gui


class ImmediateThread:
    def __init__(self, target, args=(), daemon=None):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


def app():
    return QApplication.instance() or QApplication([])


def test_saved_server_can_complete_join_from_main_button(monkeypatch):
    qt_app = app()
    calls = []
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {"Canada #2": {"ip": "1.2.3.4", "port": 7778}})
    monkeypatch.setattr(gui.threading, "Thread", ImmediateThread)

    def fake_run(name, on_status, stop_event):
        calls.append((name, stop_event))
        on_status("Attempt 1: connecting...")
        return "success"

    monkeypatch.setattr(gui.joiner, "run", fake_run)
    window = gui.MainWindow()
    window.server_box.setCurrentText("Canada #2")

    window.join_button.click()
    qt_app.processEvents()

    assert calls and calls[0][0] == "Canada #2"
    assert window.status.text() == "Joined successfully."
    assert window.busy is False
    assert window.stop_button.isEnabled() is False
    window.close()


def test_stop_button_sets_controller_cancellation(monkeypatch):
    qt_app = app()
    started = []

    class DeferredThread(ImmediateThread):
        def start(self):
            started.append(self)

    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {"Canada #2": {"ip": "1.2.3.4", "port": 7778}})
    monkeypatch.setattr(gui.threading, "Thread", DeferredThread)
    window = gui.MainWindow()
    window.server_box.setCurrentText("Canada #2")
    window.join_button.click()
    qt_app.processEvents()

    assert started and window.stop_button.isEnabled()
    window.stop_button.click()
    qt_app.processEvents()

    assert window.stop_event.is_set()
    assert window.status.text() == "Stopping auto-join..."
    window.close()


def test_action_buttons_fit_at_minimum_window_size(monkeypatch):
    qt_app = app()
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {})
    window = gui.MainWindow()
    window.resize(window.minimumSize())
    window.show_page(1)
    window.show()
    qt_app.processEvents()

    scroll = window.pages.currentWidget()
    viewport_right = scroll.viewport().mapToGlobal(QPoint(scroll.viewport().width(), 0)).x()
    for button in (window.saved_servers_button, window.join_button, window.remember_button, window.delete_server_button, window.stop_button):
        button_right = button.mapToGlobal(QPoint(button.width(), 0)).x()
        assert button_right <= viewport_right
    window.close()


def test_guided_calibration_hides_once_and_advances_with_hotkey(monkeypatch):
    qt_app = app()
    cfg = {
        "navigation_mode": "automatic",
        "click_points": {
            "play": [0, 0], "servers_tab": [0, 0], "internet_tab": [0, 0],
            "direct_connect": [0, 0], "ip_field": [0, 0], "connect_button": [0, 0],
        },
    }
    saved = []
    points = iter(((200, 100), (980, 360), (1180, 1020), (1260, 1160)))

    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {})
    monkeypatch.setattr(gui.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(gui.config_mod, "save_config", lambda value: saved.append(value.copy()))
    monkeypatch.setattr(gui.winput, "get_cursor_pos", lambda: next(points))
    window = gui.MainWindow()
    visibility_events = []
    original_hide, original_show = window.hide, window.show
    monkeypatch.setattr(window, "hide", lambda: (visibility_events.append("hide"), original_hide())[1])
    monkeypatch.setattr(window, "show", lambda: (visibility_events.append("show"), original_show())[1])
    dialog = gui.CalibrationDialog(window)
    visibility_events.clear()

    assert dialog.capture_button.text() == "Begin guided calibration"
    instructions = dialog.instructions.text().lower()
    assert "press f8" in instructions

    dialog.capture_button.click()
    qt_app.processEvents()
    assert visibility_events == ["hide"]
    assert "Step 1 of 4" in dialog.overlay.message.text()

    for expected_step in range(1, 5):
        dialog.capture_current_point()
        qt_app.processEvents()
        if expected_step < 4:
            assert f"Step {expected_step + 1} of 4" in dialog.overlay.message.text()
            assert not window.isVisible()

    assert dialog.result() == QDialog.Accepted
    assert cfg["navigation_mode"] == "manual"
    assert cfg["calibration_space"] == "physical_v2"
    assert cfg["click_points"]["servers_tab"] == [200, 100]
    assert cfg["click_points"]["direct_connect"] == [980, 360]
    assert cfg["click_points"]["ip_field"] == [1180, 1020]
    assert cfg["click_points"]["connect_button"] == [1260, 1160]
    assert visibility_events == ["hide", "show"]
    assert saved
    window.close()


def test_main_window_opens_calibration_modelessly(monkeypatch):
    qt_app = app()
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {})
    window = gui.MainWindow()
    window.show()

    window.calibrate()
    qt_app.processEvents()

    assert window.calibration_dialog.isVisible()
    assert window.isVisible()
    window.calibration_dialog.reject()
    window.close()


def test_settings_page_saves_timing_mode_and_coordinates(monkeypatch):
    qt_app = app()
    cfg = {
        "navigation_mode": "manual",
        "calibration_space": "physical_v2",
        "retry_interval_s": 6,
        "attempt_timeout_s": 20,
        "max_unclear": 3,
        "max_attempts": 100,
        "max_minutes": 30,
        "click_points": {
            "play": [0, 0], "servers_tab": [200, 100], "internet_tab": [0, 0],
            "direct_connect": [980, 360], "ip_field": [1180, 1020],
            "connect_button": [1260, 1160],
        },
    }
    saved = []
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {})
    monkeypatch.setattr(gui.config_mod, "load_config", lambda: cfg.copy() | {"click_points": {k: v[:] for k, v in cfg["click_points"].items()}})
    monkeypatch.setattr(gui.config_mod, "save_config", lambda value: saved.append(value))

    window = gui.MainWindow()
    window.settings_nav.click()
    qt_app.processEvents()
    assert window.pages.currentIndex() == 3

    window.retry_interval.setValue(9)
    window.attempt_timeout.setValue(35)
    window.max_attempts.setValue(250)
    window.max_minutes.setValue(60)
    window.point_inputs["connect_button"][0].setValue(2500)
    window.point_inputs["connect_button"][1].setValue(1400)
    window.save_settings_button.click()
    qt_app.processEvents()

    assert saved
    assert saved[-1]["retry_interval_s"] == 9
    assert saved[-1]["attempt_timeout_s"] == 35
    assert saved[-1]["max_attempts"] == 250
    assert saved[-1]["max_minutes"] == 60
    assert saved[-1]["click_points"]["connect_button"] == [2500, 1400]
    window.close()


def test_zero_limits_display_and_save_as_unlimited(monkeypatch):
    qt_app = app()
    cfg = gui.config_mod.DEFAULTS.copy() | {
        "click_points": {k: v[:] for k, v in gui.config_mod.DEFAULTS["click_points"].items()},
    }
    saved = []
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {})
    monkeypatch.setattr(gui.config_mod, "load_config", lambda: cfg.copy() | {"click_points": {k: v[:] for k, v in cfg["click_points"].items()}})
    monkeypatch.setattr(gui.config_mod, "save_config", lambda value: saved.append(value))
    window = gui.MainWindow()

    window.max_attempts.setValue(0)
    window.max_minutes.setValue(0)
    assert window.max_attempts.text() == "Unlimited"
    assert window.max_minutes.text() == "Unlimited"
    window.save_settings_button.click()
    qt_app.processEvents()

    assert saved[-1]["max_attempts"] == 0
    assert saved[-1]["max_minutes"] == 0
    window.close()


def test_settings_actions_fit_at_minimum_window_width(monkeypatch):
    qt_app = app()
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {})
    window = gui.MainWindow()
    window.resize(window.minimumSize())
    window.show_page(3)
    window.show()
    qt_app.processEvents()

    scroll = window.pages.currentWidget()
    viewport_right = scroll.viewport().mapToGlobal(QPoint(scroll.viewport().width(), 0)).x()
    for button in (window.open_data_button, window.save_settings_button, window.automatic_button, window.settings_calibration_button):
        button_right = button.mapToGlobal(QPoint(button.width(), 0)).x()
        assert button_right <= viewport_right
    assert scroll.verticalScrollBar().maximum() > 0
    assert scroll.horizontalScrollBar().maximum() == 0
    window.close()


def test_detected_server_name_prefills_confirmation(monkeypatch):
    qt_app = app()
    seen = {}
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {})
    monkeypatch.setattr(gui.resolver, "remember_server", lambda name, ip, port: seen.update(name=name, ip=ip, port=port))

    def fake_get_text(_parent, _title, prompt, _mode, suggested):
        seen["prompt"] = prompt
        seen["suggested"] = suggested
        return suggested, True

    monkeypatch.setattr(gui.QInputDialog, "getText", fake_get_text)
    window = gui.MainWindow()
    window.server_saved("158.69.52.5:7779", "Northwood Official Server - Canada #3")
    qt_app.processEvents()

    assert seen["suggested"] == "Northwood Official Server - Canada #3"
    assert seen["name"] == "Northwood Official Server - Canada #3"
    assert seen["ip"] == "158.69.52.5"
    assert seen["port"] == 7779
    window.close()


def test_saved_server_dropdown_browses_and_filters_without_rebuilding(monkeypatch):
    qt_app = app()
    servers = {
        "Northwood Official Server - Canada #3": {"ip": "158.69.52.5", "port": 7779},
        "King's Playground - US East #1": {"ip": "1.2.3.4", "port": 7777},
    }
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: servers)
    window = gui.MainWindow()
    window.show_page(1)
    window.show()
    original_model = window.server_box.model()

    assert window.saved_servers_button.width() <= 56
    assert window.saved_servers_button.accessibleName() == "Show saved servers"
    assert window.server_count_label.text() == "2 SAVED"
    assert not window.delete_server_button.isEnabled()

    window.saved_servers_button.click()
    qt_app.processEvents()
    assert window.server_box.view().isVisible()
    assert window.server_box.count() == 2

    window.show_server_suggestions("canada")
    qt_app.processEvents()
    assert window.server_box.model() is original_model
    assert window.server_completer.completionModel().rowCount() == 1
    window.server_box.hidePopup()
    window.close()


def test_delete_selected_server_confirms_and_refreshes_picker(monkeypatch):
    qt_app = app()
    servers = {
        "Canada #2": {"ip": "1.2.3.4", "port": 7778},
        "Canada #3": {"ip": "5.6.7.8", "port": 7779},
    }
    deleted = []
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: servers.copy())
    monkeypatch.setattr(gui.resolver, "forget_server", lambda name: deleted.append(name) or bool(servers.pop(name, None)))
    monkeypatch.setattr(gui.QMessageBox, "question", lambda *_args, **_kwargs: gui.QMessageBox.Yes)
    window = gui.MainWindow()
    window.server_box.setCurrentText("Canada #2")
    qt_app.processEvents()

    assert window.delete_server_button.isEnabled()
    window.delete_server_button.click()
    qt_app.processEvents()

    assert deleted == ["Canada #2"]
    assert window.server_box.count() == 1
    assert window.server_count_label.text() == "1 SAVED"
    assert window.server_box.currentText() != "Canada #2"
    window.close()


def test_onboarding_diagnostics_and_settings_wiring(monkeypatch):
    """The Task 6 controls expose the active strategy without starting a game.

    This fails if the four-page shell, safe onboarding checks, diagnostics, or
    persisted method/settings controls are removed or disconnected.
    """
    qt_app = app()
    cfg = gui.config_mod.DEFAULTS.copy() | {
        "click_points": {k: v[:] for k, v in gui.config_mod.DEFAULTS["click_points"].items()},
    }
    saved = []
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {"Canada #2": {"ip": "1.2.3.4", "port": 7778}})
    monkeypatch.setattr(gui.config_mod, "load_config", lambda: cfg.copy() | {"click_points": {k: v[:] for k, v in cfg["click_points"].items()}})
    def save_config(value):
        cfg.update(value)
        saved.append(value.copy())
    monkeypatch.setattr(gui.config_mod, "save_config", save_config)
    monkeypatch.setattr(gui.joiner, "find_game_executable", lambda: None)

    window = gui.MainWindow()

    assert window.pages.count() == 5
    window.servers_nav.click(); qt_app.processEvents()
    assert window.pages.currentIndex() == 1
    window.setup_nav.click(); qt_app.processEvents()
    assert window.pages.currentIndex() == 2
    window.settings_nav.click(); qt_app.processEvents()
    assert window.pages.currentIndex() == 3
    assert "0 = unlimited" in window.unlimited_limits_note.text().lower()

    window.set_connection_method("foreground")
    window.group_loop_checkbox.setChecked(False)
    window.browser_refresh_timeout.setValue(5)
    window.save_settings()
    assert saved[-1]["connection_method"] == "foreground"
    assert saved[-1]["group_loop"] is False
    assert saved[-1]["browser_refresh_timeout_s"] == 5

    window.run_diagnostics()
    assert "Foreground" in window.diagnostics_result.text()
    assert "not detected" in window.diagnostics_result.text().lower()

    window.show_onboarding()
    qt_app.processEvents()
    assert window.onboarding_dialog.isVisible()
    assert "safe direct-connect check" in window.onboarding_result.text().lower()
    window.onboarding_dialog.close()
    window.close()


def test_text_packs_page_is_available_and_scrollable(monkeypatch, tmp_path):
    qt_app = app()
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {})
    monkeypatch.setattr(gui, "find_translations_dir", lambda: str(tmp_path / "Translations"))

    window = gui.MainWindow()

    assert window.pages.count() == 5
    window.packs_nav.click(); qt_app.processEvents()
    assert window.pages.currentIndex() == 4
    assert window.pack_drop_zone.acceptDrops()
    assert window.pack_drop_zone.accessibleName() == "Translation pack drop zone"
    window.close()


def _browser_store():
    return {
        "version": 1,
        "servers": [
            {"id": "canada", "name": "Canada #2", "ip": "1.2.3.4", "port": 7778},
            {"id": "europe", "name": "Europe #1", "ip": "5.6.7.8", "port": 7779},
        ],
        "groups": [{"id": "raid", "name": "Raid night", "server_ids": ["europe", "canada"]}],
    }


def test_versioned_store_never_populates_picker_with_storage_keys(monkeypatch):
    """The GUI accepts a versioned store at the legacy loader boundary.

    Returning the raw store reproduces the reported regression: treating this
    mapping as ``{display_name: endpoint}`` used to show ``version``,
    ``servers``, and ``groups`` in the picker (and could crash during refresh).
    """
    qt_app = app()
    store = _browser_store()
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: store)
    monkeypatch.setattr(gui.resolver, "load_store", lambda: store)

    window = gui.MainWindow()

    assert [window.server_box.itemText(index) for index in range(window.server_box.count())] == ["Canada #2", "Europe #1"]
    assert [window.group_box.itemText(index) for index in range(window.group_box.count())] == ["Raid night"]
    window.close()


def test_server_cards_filter_and_select_a_saved_server(monkeypatch):
    qt_app = app()
    store = _browser_store()
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {
        item["name"]: {"ip": item["ip"], "port": item["port"]} for item in store["servers"]
    })
    monkeypatch.setattr(gui.resolver, "load_store", lambda: store)
    window = gui.MainWindow()

    window.server_search.setText("canada")
    qt_app.processEvents()
    assert list(window.server_card_buttons) == ["Canada #2"]

    window.server_card_buttons["Canada #2"].click()
    qt_app.processEvents()
    assert window.server_box.currentText() == "Canada #2"
    assert "1.2.3.4:7778" in window.endpoint_preview.text()
    window.close()


def test_selected_server_refresh_uses_injected_query_result(monkeypatch):
    qt_app = app()
    store = _browser_store()
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {
        item["name"]: {"ip": item["ip"], "port": item["port"]} for item in store["servers"]
    })
    monkeypatch.setattr(gui.resolver, "load_store", lambda: store)
    monkeypatch.setattr(gui.resolver, "query_server", lambda *_args, **_kwargs: {
        "players": 7, "max_players": 20, "available": True, "latency_ms": 12.5,
    })
    monkeypatch.setattr(gui.threading, "Thread", ImmediateThread)
    window = gui.MainWindow()
    window.server_box.setCurrentText("Canada #2")

    window.refresh_selected_server()
    qt_app.processEvents()

    assert "7 / 20 players" in window.server_card_text["Canada #2"].text()
    assert "12.5 ms" in window.server_card_text["Canada #2"].text()
    window.close()


def test_selected_server_refresh_uses_saved_timeout_preference(monkeypatch):
    qt_app = app()
    store = _browser_store()
    seen = []
    cfg = gui.config_mod.DEFAULTS.copy() | {
        "browser_refresh_timeout_s": 7,
        "click_points": {k: v[:] for k, v in gui.config_mod.DEFAULTS["click_points"].items()},
    }
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {
        item["name"]: {"ip": item["ip"], "port": item["port"]} for item in store["servers"]
    })
    monkeypatch.setattr(gui.resolver, "load_store", lambda: store)
    monkeypatch.setattr(gui.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(gui.resolver, "query_server", lambda ip, port, timeout: seen.append((ip, port, timeout)) or None)
    monkeypatch.setattr(gui.threading, "Thread", ImmediateThread)
    window = gui.MainWindow()
    window.server_box.setCurrentText("Canada #2")

    window.refresh_selected_server()
    qt_app.processEvents()

    assert seen == [("1.2.3.4", 7778, 7)]
    window.close()


def test_save_server_from_form_renames_and_edits_endpoint(monkeypatch):
    qt_app = app()
    store = _browser_store()
    changes = []
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {
        item["name"]: {"ip": item["ip"], "port": item["port"]} for item in store["servers"]
    })
    monkeypatch.setattr(gui.resolver, "load_store", lambda: store)

    def update_server(server_id, name, ip, port):
        changes.append((server_id, name, ip, port))
        item = next(item for item in store["servers"] if item["id"] == server_id)
        item.update(name=name, ip=ip, port=port)

    monkeypatch.setattr(gui.resolver, "update_server", update_server)
    window = gui.MainWindow()
    window.server_box.setCurrentText("Canada #2")
    window.server_name_input.setText("Canada Prime")
    window.server_endpoint_input.setText("9.8.7.6:7780")

    window.save_server_from_form()
    qt_app.processEvents()

    assert changes == [("canada", "Canada Prime", "9.8.7.6", 7780)]
    assert window.server_box.currentText() == "Canada Prime"
    window.close()


def test_delete_selected_server_confirms_through_browser_action(monkeypatch):
    qt_app = app()
    store = _browser_store()
    deleted = []
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {
        item["name"]: {"ip": item["ip"], "port": item["port"]} for item in store["servers"]
    })
    monkeypatch.setattr(gui.resolver, "load_store", lambda: store)
    monkeypatch.setattr(gui.resolver, "forget_server", lambda name: deleted.append(name) or True)
    monkeypatch.setattr(gui.QMessageBox, "question", lambda *_args, **_kwargs: gui.QMessageBox.Yes)
    window = gui.MainWindow()
    window.server_box.setCurrentText("Canada #2")

    window.delete_selected_server()
    qt_app.processEvents()

    assert deleted == ["Canada #2"]
    window.close()


def test_group_reorder_is_saved_and_start_group_runs_in_background(monkeypatch):
    qt_app = app()
    store = _browser_store()
    saved = []
    started = []
    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {
        item["name"]: {"ip": item["ip"], "port": item["port"]} for item in store["servers"]
    })
    monkeypatch.setattr(gui.resolver, "load_store", lambda: store)
    monkeypatch.setattr(gui.resolver, "update_group", lambda group_id, name, ids: saved.append((group_id, name, ids)))
    monkeypatch.setattr(gui.joiner, "run_group", lambda group_id, **_kwargs: started.append(group_id) or "success")
    monkeypatch.setattr(gui.threading, "Thread", ImmediateThread)
    window = gui.MainWindow()

    window.group_box.setCurrentIndex(0)
    window.group_members.setCurrentRow(1)
    window.move_group_member(-1)
    window.create_or_update_group()
    window.start_selected_group()
    qt_app.processEvents()

    assert saved == [("raid", "Raid night", ["canada", "europe"])]
    assert started == ["raid"]
    window.close()

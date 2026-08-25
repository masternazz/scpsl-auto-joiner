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
    window.show()
    qt_app.processEvents()

    scroll = window.pages.currentWidget()
    viewport_right = scroll.viewport().mapToGlobal(QPoint(scroll.viewport().width(), 0)).x()
    for button in (window.join_button, window.remember_button, window.stop_button):
        button_right = button.mapToGlobal(QPoint(button.width(), 0)).x()
        assert button_right <= viewport_right
    window.close()


def test_calibration_explains_and_captures_four_points(monkeypatch):
    qt_app = app()
    cfg = {
        "navigation_mode": "automatic",
        "click_points": {
            "play": [0, 0], "servers_tab": [0, 0], "internet_tab": [0, 0],
            "direct_connect": [0, 0], "ip_field": [0, 0], "connect_button": [0, 0],
        },
    }
    saved = []
    points = iter((QPoint(100, 50), QPoint(490, 180), QPoint(590, 510), QPoint(630, 580)))

    class FakeCursor:
        @staticmethod
        def pos():
            return next(points)

    monkeypatch.setattr(gui.resolver, "load_servers", lambda: {})
    monkeypatch.setattr(gui.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(gui.config_mod, "save_config", lambda value: saved.append(value.copy()))
    monkeypatch.setattr(gui, "QCursor", FakeCursor)
    monkeypatch.setattr(gui.QTimer, "singleShot", lambda _delay, callback: callback())
    window = gui.MainWindow()
    visibility_events = []
    original_hide, original_show = window.hide, window.show
    monkeypatch.setattr(window, "hide", lambda: (visibility_events.append("hide"), original_hide())[1])
    monkeypatch.setattr(window, "show", lambda: (visibility_events.append("show"), original_show())[1])
    dialog = gui.CalibrationDialog(window)
    visibility_events.clear()

    assert dialog.capture_button.text() == "Start 3-second capture"
    instructions = dialog.instructions.text().lower()
    assert "click start" in instructions
    assert "then move" in instructions

    for expected_step in range(1, 5):
        dialog.capture_button.click()
        qt_app.processEvents()
        if expected_step < 4:
            assert f"Captured step {expected_step}" in dialog.countdown.text()

    assert dialog.result() == QDialog.Accepted
    assert cfg["navigation_mode"] == "manual"
    assert cfg["click_points"]["servers_tab"] == [100, 50]
    assert cfg["click_points"]["direct_connect"] == [490, 180]
    assert cfg["click_points"]["ip_field"] == [590, 510]
    assert cfg["click_points"]["connect_button"] == [630, 580]
    assert visibility_events == ["hide", "show"] * 4
    assert saved
    window.close()

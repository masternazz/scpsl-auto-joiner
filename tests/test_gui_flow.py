import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

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

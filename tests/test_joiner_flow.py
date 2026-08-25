import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import joiner


class FakeWatcher:
    def __init__(self):
        self.outcomes = iter(("rejected", "success"))

    def wait_for_marker(self, marker, _timeout, stop_event=None):
        assert marker == joiner.logwatch.CONNECTING_MARK
        return True

    def wait_for_outcome(self, _timeout, stop_event=None):
        return next(self.outcomes)

    def close(self):
        pass


def test_automatic_layout_scales_to_offset_4k_window(monkeypatch):
    clicks = []
    cfg = {"navigation_mode": "automatic", "click_points": {}}
    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner.winput, "get_window_rect", lambda _hwnd: (100, 50, 3940, 2210))
    monkeypatch.setattr(joiner.winput, "focus_window", lambda _hwnd: True)
    monkeypatch.setattr(joiner.winput, "mouse_click", lambda x, y: clicks.append((x, y)))

    point = joiner.click_layout(123, "connect")

    assert point == (2519, 1302)
    assert clicks == [point]


def test_manual_layout_uses_native_pixels_without_rescaling(monkeypatch):
    clicks = []
    cfg = {
        "navigation_mode": "manual",
        "calibration_space": "physical_v2",
        "click_points": {
            "servers_tab": [480, 110],
            "direct_connect": [1660, 410],
            "ip_field": [1900, 1050],
            "connect_button": [2020, 1190],
        },
    }
    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner.winput, "get_window_rect", lambda _hwnd: (0, 0, 3840, 2160))
    monkeypatch.setattr(joiner.winput, "focus_window", lambda _hwnd: True)
    monkeypatch.setattr(joiner.winput, "mouse_click", lambda x, y: clicks.append((x, y)))

    point = joiner.click_layout(123, "connect")

    assert point == (2020, 1190)
    assert clicks == [(2020, 1190)]


def test_full_run_reopens_direct_connect_without_reclicking_servers(monkeypatch):
    """A rejected Direct Connect returns to Servers before the next try."""
    events = []
    cfg = {
        "navigation_mode": "automatic",
        "click_points": {},
        "attempt_timeout_s": 1,
        "retry_interval_s": 0,
        "max_unclear": 3,
        "max_attempts": 5,
        "max_minutes": 5,
    }

    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner.resolver, "resolve", lambda _name: ("Canada #2", "1.2.3.4", 7778))
    monkeypatch.setattr(joiner.logwatch, "LogWatcher", FakeWatcher)
    monkeypatch.setattr(joiner.winput, "find_game_window", lambda _title: 123)
    monkeypatch.setattr(joiner.winput, "get_window_rect", lambda _hwnd: (0, 0, 1000, 1000))
    monkeypatch.setattr(joiner.winput, "focus_window", lambda _hwnd: True)
    monkeypatch.setattr(joiner.winput, "mouse_click", lambda x, y: events.append(("click", x, y)))
    monkeypatch.setattr(joiner.winput, "replace_text", lambda _hwnd, text: events.append(("text", text)))
    monkeypatch.setattr(joiner.winput, "post_key_tap", lambda _hwnd, key: events.append(("key", key)))
    monkeypatch.setattr(joiner.notify, "notify", lambda _title, message: events.append(("notify", message)))
    monkeypatch.setattr(joiner.os, "startfile", lambda uri: events.append(("launch", uri)))
    monkeypatch.setattr(joiner.time, "sleep", lambda _seconds: None)

    result = joiner.run("Canada #2")

    assert result == "success"
    assert events == [
        ("click", 120, 50),
        ("click", 490, 180),
        ("click", 590, 510),
        ("text", "1.2.3.4:7778"),
        ("click", 630, 580),
        ("click", 490, 180),
        ("click", 590, 510),
        ("text", "1.2.3.4:7778"),
        ("click", 630, 580),
        ("notify", "Joined Canada #2!"),
    ]


def test_stop_during_retry_delay_prevents_another_click(monkeypatch):
    events = []
    cfg = {
        "navigation_mode": "automatic",
        "click_points": {},
        "attempt_timeout_s": 1,
        "retry_interval_s": 6,
        "max_unclear": 3,
        "max_attempts": 5,
        "max_minutes": 5,
    }

    class RejectingWatcher(FakeWatcher):
        def wait_for_outcome(self, _timeout, stop_event=None):
            return "rejected"

    class StopDuringDelay:
        def __init__(self):
            self.stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, _timeout):
            self.stopped = True
            return True

    stop = StopDuringDelay()
    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner.resolver, "resolve", lambda _name: ("Canada #2", "1.2.3.4", 7778))
    monkeypatch.setattr(joiner.logwatch, "LogWatcher", RejectingWatcher)
    monkeypatch.setattr(joiner.winput, "find_game_window", lambda _title: 123)
    monkeypatch.setattr(joiner.winput, "get_window_rect", lambda _hwnd: (0, 0, 1000, 1000))
    monkeypatch.setattr(joiner.winput, "focus_window", lambda _hwnd: True)
    monkeypatch.setattr(joiner.winput, "mouse_click", lambda x, y: events.append(("click", x, y)))
    monkeypatch.setattr(joiner.winput, "replace_text", lambda _hwnd, text: events.append(("text", text)))
    monkeypatch.setattr(joiner.winput, "post_key_tap", lambda _hwnd, key: events.append(("key", key)))
    monkeypatch.setattr(joiner.notify, "notify", lambda *_args: None)

    assert joiner.run("Canada #2", stop_event=stop) == "stopped"
    assert events.count(("click", 630, 580)) == 1

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


def test_cold_automatic_connection_launches_game_with_connect_argument(monkeypatch):
    launches = []
    cfg = {"navigation_mode": "automatic", "attempt_timeout_s": 1}
    watcher = FakeWatcher()
    monkeypatch.setattr(joiner, "launch_game_connected", lambda ip, port: launches.append((ip, port)))
    monkeypatch.setattr(joiner.winput, "post_click", lambda *_args: (_ for _ in ()).throw(AssertionError("must not click")))
    monkeypatch.setattr(joiner.winput, "replace_text", lambda *_args: (_ for _ in ()).throw(AssertionError("must not type")))
    monkeypatch.setattr(joiner.winput, "mouse_click", lambda *_args: (_ for _ in ()).throw(AssertionError("must not move the cursor")))

    result = joiner.connect_once(None, cfg, watcher, "1.2.3.4", 7778, launch_direct=True)

    assert result == "rejected"
    assert launches == [("1.2.3.4", 7778)]


def test_automatic_run_lets_connect_argument_launch_game(monkeypatch):
    cfg = {
        "navigation_mode": "automatic",
        "attempt_timeout_s": 1,
        "retry_interval_s": 0,
        "max_unclear": 3,
        "max_attempts": 1,
        "max_minutes": 1,
        "click_points": {},
    }
    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner.resolver, "resolve", lambda _name: ("Canada #3", "1.2.3.4", 7778))
    monkeypatch.setattr(joiner.logwatch, "LogWatcher", FakeWatcher)
    monkeypatch.setattr(joiner.winput, "find_game_window", lambda _title: None)
    monkeypatch.setattr(joiner, "ensure_game_running", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not launch separately")))
    calls = []
    monkeypatch.setattr(joiner, "connect_once", lambda *args, **kwargs: calls.append((args, kwargs)) or "success")
    monkeypatch.setattr(joiner.notify, "notify", lambda *_args: None)

    assert joiner.run("Canada #3") == "success"
    assert calls[0][0][0] is None
    assert calls[0][1]["launch_direct"] is True


def test_find_game_executable_reads_secondary_steam_library(tmp_path):
    root = tmp_path / "Steam"
    library = tmp_path / "Games"
    (root / "steamapps").mkdir(parents=True)
    (library / "steamapps" / "common" / "SCP Secret Laboratory").mkdir(parents=True)
    (root / "steamapps" / "libraryfolders.vdf").write_text(
        f'"libraryfolders" {{ "1" {{ "path" "{str(library).replace(chr(92), chr(92) * 2)}" }} }}',
        encoding="utf-8",
    )
    (library / "steamapps" / "appmanifest_700330.acf").write_text(
        '"AppState" { "installdir" "SCP Secret Laboratory" }',
        encoding="utf-8",
    )
    executable = library / "steamapps" / "common" / "SCP Secret Laboratory" / "SCPSL.exe"
    executable.write_bytes(b"")

    assert joiner.find_game_executable(str(root)) == str(executable)


def test_automatic_layout_scales_to_offset_4k_window(monkeypatch):
    clicks = []
    cfg = {"navigation_mode": "automatic", "click_points": {}}
    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner.winput, "get_window_rect", lambda _hwnd: (100, 50, 3940, 2210))
    monkeypatch.setattr(joiner.winput, "focus_window", lambda _hwnd: (_ for _ in ()).throw(AssertionError("must not steal focus")))
    monkeypatch.setattr(joiner.winput, "mouse_click", lambda *_args: (_ for _ in ()).throw(AssertionError("must not move the cursor")))
    monkeypatch.setattr(joiner.winput, "post_click", lambda hwnd, x, y: clicks.append((hwnd, x, y)))

    point = joiner.click_layout(123, "connect")

    assert point == (2135, 1238)
    assert clicks == [(123, *point)]


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
    monkeypatch.setattr(joiner.winput, "focus_window", lambda _hwnd: (_ for _ in ()).throw(AssertionError("must not steal focus")))
    monkeypatch.setattr(joiner.winput, "mouse_click", lambda *_args: (_ for _ in ()).throw(AssertionError("must not move the cursor")))
    monkeypatch.setattr(joiner.winput, "post_click", lambda hwnd, x, y: clicks.append((hwnd, x, y)))

    point = joiner.click_layout(123, "connect")

    assert point == (2020, 1190)
    assert clicks == [(123, 2020, 1190)]


def test_full_run_retries_with_background_window_messages(monkeypatch):
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
    monkeypatch.setattr(joiner.winput, "focus_window", lambda _hwnd: (_ for _ in ()).throw(AssertionError("must not steal focus")))
    monkeypatch.setattr(joiner.winput, "mouse_click", lambda *_args: (_ for _ in ()).throw(AssertionError("must not move the cursor")))
    monkeypatch.setattr(joiner.winput, "post_click", lambda _hwnd, x, y: events.append(("click", x, y)))
    monkeypatch.setattr(joiner.winput, "replace_text", lambda _hwnd, text: events.append(("text", text)))
    monkeypatch.setattr(joiner.winput, "post_key_tap", lambda _hwnd, key: events.append(("key", key)))
    monkeypatch.setattr(joiner.winput, "foreground_key_tap", lambda *_args: None)
    monkeypatch.setattr(joiner.notify, "notify", lambda _title, message: events.append(("notify", message)))
    monkeypatch.setattr(joiner.time, "sleep", lambda _seconds: None)

    result = joiner.run("Canada #2")

    assert result == "success"
    assert events == [
        ("click", 120, 50),
        ("click", 410, 190),
        ("click", 500, 490),
        ("text", "1.2.3.4:7778"),
        ("click", 530, 550),
        ("key", joiner.winput.VK_RETURN),
        ("key", joiner.winput.VK_ESCAPE),
        ("click", 120, 50),
        ("click", 410, 190),
        ("click", 500, 490),
        ("text", "1.2.3.4:7778"),
        ("click", 530, 550),
        ("key", joiner.winput.VK_RETURN),
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
    monkeypatch.setattr(joiner.winput, "focus_window", lambda _hwnd: (_ for _ in ()).throw(AssertionError("must not steal focus")))
    monkeypatch.setattr(joiner.winput, "mouse_click", lambda *_args: (_ for _ in ()).throw(AssertionError("must not move the cursor")))
    monkeypatch.setattr(joiner.winput, "post_click", lambda _hwnd, x, y: events.append(("click", x, y)))
    monkeypatch.setattr(joiner.winput, "replace_text", lambda _hwnd, text: events.append(("text", text)))
    monkeypatch.setattr(joiner.winput, "post_key_tap", lambda _hwnd, key: events.append(("key", key)))
    monkeypatch.setattr(joiner.winput, "foreground_key_tap", lambda *_args: None)
    monkeypatch.setattr(joiner.notify, "notify", lambda *_args: None)

    assert joiner.run("Canada #2", stop_event=stop) == "stopped"
    assert events.count(("click", 530, 550)) == 1


def test_rejected_server_reports_reason_and_two_second_retry(monkeypatch):
    statuses = []
    sleeps = []
    cfg = {
        "navigation_mode": "automatic",
        "click_points": {},
        "attempt_timeout_s": 20,
        "retry_interval_s": 2,
        "max_unclear": 3,
        "max_attempts": 5,
        "max_minutes": 5,
    }
    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner.resolver, "resolve", lambda _name: ("Canada #3", "1.2.3.4", 7779))
    monkeypatch.setattr(joiner.logwatch, "LogWatcher", FakeWatcher)
    monkeypatch.setattr(joiner.winput, "find_game_window", lambda _title: 123)
    monkeypatch.setattr(joiner.winput, "get_window_rect", lambda _hwnd: (0, 0, 1000, 1000))
    monkeypatch.setattr(joiner.winput, "focus_window", lambda _hwnd: (_ for _ in ()).throw(AssertionError("must not steal focus")))
    monkeypatch.setattr(joiner.winput, "mouse_click", lambda *_args: (_ for _ in ()).throw(AssertionError("must not move the cursor")))
    monkeypatch.setattr(joiner.winput, "post_click", lambda *_args: None)
    monkeypatch.setattr(joiner.winput, "replace_text", lambda *_args: None)
    monkeypatch.setattr(joiner.winput, "post_key_tap", lambda *_args: None)
    monkeypatch.setattr(joiner.winput, "foreground_key_tap", lambda *_args: None)
    monkeypatch.setattr(joiner.notify, "notify", lambda *_args: None)
    monkeypatch.setattr(joiner.time, "sleep", lambda seconds: sleeps.append(seconds))

    assert joiner.run("Canada #3", on_status=statuses.append) == "success"
    assert 2 in sleeps
    assert "Server full or connection rejected. Retrying in 2 seconds..." in statuses


def test_zero_attempts_and_runtime_run_until_stopped(monkeypatch):
    attempts = []
    cfg = {
        "navigation_mode": "automatic",
        "click_points": {},
        "attempt_timeout_s": 20,
        "retry_interval_s": 0,
        "max_unclear": 3,
        "max_attempts": 0,
        "max_minutes": 0,
    }

    class StopAfterTwoRetries:
        def __init__(self):
            self.waits = 0
            self.stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, _timeout):
            self.waits += 1
            self.stopped = self.waits >= 2
            return self.stopped

    stop = StopAfterTwoRetries()
    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner.resolver, "resolve", lambda _name: ("Canada #3", "1.2.3.4", 7779))
    monkeypatch.setattr(joiner.logwatch, "LogWatcher", FakeWatcher)
    monkeypatch.setattr(joiner.winput, "find_game_window", lambda _title: 123)
    monkeypatch.setattr(joiner, "ensure_game_running", lambda *_args, **_kwargs: 123)
    monkeypatch.setattr(joiner, "connect_once", lambda *_args, **_kwargs: attempts.append("attempt") or "rejected")
    monkeypatch.setattr(joiner.notify, "notify", lambda *_args: None)

    assert joiner.run("Canada #3", stop_event=stop) == "stopped"
    assert attempts == ["attempt", "attempt"]

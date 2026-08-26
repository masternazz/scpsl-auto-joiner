import os
import sys
import threading
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import joiner


class FakeWatcher:
    def __init__(self):
        self.outcomes = iter(("rejected_or_unknown", "success"))

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

    assert result == "rejected_or_unknown"
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


def test_warm_run_never_launches_a_second_game_process(monkeypatch):
    cfg = {
        "connection_method": "automatic",
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
    monkeypatch.setattr(joiner.winput, "find_game_window", lambda _title: 123)
    monkeypatch.setattr(joiner, "ensure_game_running", lambda *_args, **_kwargs: 123)
    monkeypatch.setattr(joiner, "launch_game_connected", lambda *_args: (_ for _ in ()).throw(AssertionError("must not launch")))
    calls = []
    monkeypatch.setattr(joiner, "connect_once", lambda *args, **kwargs: calls.append(kwargs) or "success")
    monkeypatch.setattr(joiner.notify, "notify", lambda *_args: None)

    assert joiner.run("Canada #3") == "success"
    assert calls == [{"open_servers": True, "launch_direct": False, "stop_event": None}]


def test_run_rejects_a_concurrent_call_without_starting_a_second_attempt(monkeypatch):
    cfg = {"max_attempts": 1, "max_minutes": 1}
    first_call_started = threading.Event()
    release_first_call = threading.Event()
    calls = []

    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner.winput, "set_dpi_awareness", lambda: None)
    monkeypatch.setattr(joiner.notify, "notify", lambda *_args: None)

    def resolve(_name):
        calls.append("resolve")
        if len(calls) == 1:
            first_call_started.set()
            release_first_call.wait(timeout=2)
        return None

    monkeypatch.setattr(joiner.resolver, "resolve", resolve)
    worker = threading.Thread(target=joiner.run, args=("Canada #3",))
    worker.start()
    assert first_call_started.wait(timeout=2)

    assert joiner.run("Canada #3") == "already_running"
    release_first_call.set()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert calls == ["resolve"]


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
        ("click", 440, 193),
        ("click", 500, 490),
        ("text", "1.2.3.4:7778"),
        ("click", 530, 550),
        ("key", joiner.winput.VK_RETURN),
        ("key", joiner.winput.VK_ESCAPE),
        ("click", 440, 193),
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
            return "rejected_or_unknown"

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
    assert "Server rejected/full-or-unknown. Retrying in 2 seconds..." in statuses


def test_disconnected_outcome_retries_without_claiming_server_is_full(monkeypatch):
    statuses = []
    cfg = {
        "navigation_mode": "automatic",
        "click_points": {},
        "attempt_timeout_s": 20,
        "retry_interval_s": 0,
        "max_unclear": 1,
        "max_attempts": 2,
        "max_minutes": 5,
    }

    class DisconnectedWatcher(FakeWatcher):
        def __init__(self):
            self.outcomes = iter(("disconnected", "success"))

    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner.resolver, "resolve", lambda _name: ("Canada #4", "1.2.3.4", 7780))
    monkeypatch.setattr(joiner.logwatch, "LogWatcher", DisconnectedWatcher)
    monkeypatch.setattr(joiner.winput, "find_game_window", lambda _title: 123)
    monkeypatch.setattr(joiner.winput, "get_window_rect", lambda _hwnd: (0, 0, 1000, 1000))
    monkeypatch.setattr(joiner.winput, "focus_window", lambda _hwnd: (_ for _ in ()).throw(AssertionError("must not steal focus")))
    monkeypatch.setattr(joiner.winput, "mouse_click", lambda *_args: (_ for _ in ()).throw(AssertionError("must not move the cursor")))
    monkeypatch.setattr(joiner.winput, "post_click", lambda *_args: None)
    monkeypatch.setattr(joiner.winput, "replace_text", lambda *_args: None)
    monkeypatch.setattr(joiner.winput, "post_key_tap", lambda *_args: None)
    monkeypatch.setattr(joiner.winput, "foreground_key_tap", lambda *_args: None)
    monkeypatch.setattr(joiner.notify, "notify", lambda *_args: None)

    assert joiner.run("Canada #4", on_status=statuses.append) == "success"
    assert "Server rejected/full-or-unknown. Retrying in 0 seconds..." in statuses


def test_connection_start_failure_is_retried_instead_of_ending_the_run(monkeypatch):
    attempts = []
    statuses = []
    cfg = {
        "connection_method": "automatic",
        "navigation_mode": "automatic",
        "click_points": {},
        "attempt_timeout_s": 1,
        "retry_interval_s": 0,
        "max_unclear": 3,
        "max_attempts": 2,
        "max_minutes": 1,
    }
    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner.resolver, "resolve", lambda _name: ("Test", "1.2.3.4", 7778))
    monkeypatch.setattr(joiner.logwatch, "LogWatcher", FakeWatcher)
    monkeypatch.setattr(joiner.winput, "find_game_window", lambda _title: 123)
    monkeypatch.setattr(joiner.winput, "post_key_tap", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(joiner.notify, "notify", lambda *_args: None)

    def attempt(*_args, **_kwargs):
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            raise joiner.JoinError("background click was not observed")
        return "success"

    monkeypatch.setattr(joiner, "connect_once", attempt)

    assert joiner.run("Test", on_status=statuses.append) == "success"
    assert attempts == [1, 2]
    assert any("retry" in status.lower() for status in statuses)


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


def _configure_group_run(monkeypatch, targets, outcomes, *, max_attempts=0, max_unclear=1):
    """Replace only the external single-attempt boundary for group tests."""
    calls = []
    cfg = {
        "navigation_mode": "automatic",
        "attempt_timeout_s": 1,
        "retry_interval_s": 0,
        "max_unclear": max_unclear,
        "max_attempts": max_attempts,
        "max_minutes": 0,
    }
    group = {"id": "group-1", "name": "Raid Night", "server_ids": [item["id"] for item in targets]}
    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner, "resolve_target", lambda target_type, target_id: list(targets), raising=False)
    monkeypatch.setattr(joiner, "server_store", SimpleNamespace(load_store=lambda: {"groups": [group]}), raising=False)
    monkeypatch.setattr(joiner.winput, "set_dpi_awareness", lambda: None)
    monkeypatch.setattr(joiner.winput, "find_game_window", lambda _title: 123)
    monkeypatch.setattr(joiner.logwatch, "LogWatcher", FakeWatcher)
    monkeypatch.setattr(joiner.transport, "choose_method", lambda *_args, **_kwargs: "background")
    monkeypatch.setattr(joiner, "dismiss_connection_overlay", lambda _hwnd: None)
    monkeypatch.setattr(joiner.notify, "notify", lambda *_args: None)

    def attempt(_hwnd, _cfg, _watcher, ip, _port, **_kwargs):
        calls.append(ip)
        return next(outcomes)

    monkeypatch.setattr(joiner, "connect_once", attempt)
    return calls


def test_resolve_target_keeps_group_server_order_and_progress_is_immutable(monkeypatch):
    first = {"id": "one", "name": "First", "ip": "1.1.1.1", "port": 7777}
    second = {"id": "two", "name": "Second", "ip": "2.2.2.2", "port": 7778}
    monkeypatch.setattr(
        joiner, "server_store",
        SimpleNamespace(load_store=lambda: {
            "servers": [first, second],
            "groups": [{"id": "group-1", "name": "Ordered", "server_ids": [second["id"], first["id"]]}],
        }),
        raising=False,
    )

    assert [item["id"] for item in joiner.resolve_target("group", "group-1")] == ["two", "one"]
    assert joiner.resolve_target("server", "one") == [first]
    progress = joiner.GroupProgress("group-1", "one", 0, 2, 1, "connecting")
    with pytest.raises(FrozenInstanceError):
        progress.attempt = 2


def test_run_group_stops_after_one_server_succeeds(monkeypatch):
    targets = [{"id": "one", "name": "Alpha", "ip": "1.1.1.1", "port": 7777}]
    calls = _configure_group_run(monkeypatch, targets, iter(("success",)))
    statuses = []

    assert joiner.run_group("group-1", on_status=statuses.append) == "success"
    assert calls == ["1.1.1.1"]
    assert any("Raid Night: server 1 of 1 (Alpha), attempt 1" in item for item in statuses)


def test_run_group_advances_after_rejection_in_saved_order(monkeypatch):
    targets = [
        {"id": "one", "name": "Alpha", "ip": "1.1.1.1", "port": 7777},
        {"id": "two", "name": "Bravo", "ip": "2.2.2.2", "port": 7778},
    ]
    calls = _configure_group_run(monkeypatch, targets, iter(("rejected", "success")))
    statuses = []

    assert joiner.run_group("group-1", on_status=statuses.append) == "success"
    assert calls == ["1.1.1.1", "2.2.2.2"]
    assert any("Raid Night: server 1 of 2 (Alpha), attempt 1: advancing after rejected." == item for item in statuses)


def test_run_group_advances_after_timeout_before_unclear_limit(monkeypatch):
    targets = [
        {"id": "one", "name": "Alpha", "ip": "1.1.1.1", "port": 7777},
        {"id": "two", "name": "Bravo", "ip": "2.2.2.2", "port": 7778},
    ]
    calls = _configure_group_run(monkeypatch, targets, iter(("timeout", "success")), max_unclear=2)

    assert joiner.run_group("group-1") == "success"
    assert calls == ["1.1.1.1", "2.2.2.2"]


def test_run_group_loops_to_first_server_after_final_rejection(monkeypatch):
    targets = [
        {"id": "one", "name": "Alpha", "ip": "1.1.1.1", "port": 7777},
        {"id": "two", "name": "Bravo", "ip": "2.2.2.2", "port": 7778},
    ]
    calls = _configure_group_run(monkeypatch, targets, iter(("rejected", "rejected", "success")))

    assert joiner.run_group("group-1") == "success"
    assert calls == ["1.1.1.1", "2.2.2.2", "1.1.1.1"]


def test_run_group_stops_after_final_server_when_group_loop_is_disabled(monkeypatch):
    targets = [
        {"id": "one", "name": "Alpha", "ip": "1.1.1.1", "port": 7777},
        {"id": "two", "name": "Bravo", "ip": "2.2.2.2", "port": 7778},
    ]
    calls = _configure_group_run(monkeypatch, targets, iter(("rejected", "rejected")))
    joiner.config_mod.load_config()["group_loop"] = False

    assert joiner.run_group("group-1") == "gave_up"
    assert calls == ["1.1.1.1", "2.2.2.2"]


def test_run_group_resets_unclear_counter_when_advancing(monkeypatch):
    targets = [
        {"id": "one", "name": "Alpha", "ip": "1.1.1.1", "port": 7777},
        {"id": "two", "name": "Bravo", "ip": "2.2.2.2", "port": 7778},
    ]
    calls = _configure_group_run(monkeypatch, targets, iter(("unclassified", "unclassified", "success")))

    assert joiner.run_group("group-1") == "success"
    assert calls == ["1.1.1.1", "2.2.2.2", "1.1.1.1"]


def test_run_group_enforces_global_attempt_limit_across_servers(monkeypatch):
    targets = [
        {"id": "one", "name": "Alpha", "ip": "1.1.1.1", "port": 7777},
        {"id": "two", "name": "Bravo", "ip": "2.2.2.2", "port": 7778},
    ]
    calls = _configure_group_run(monkeypatch, targets, iter(("rejected", "rejected", "success")), max_attempts=2)

    assert joiner.run_group("group-1") == "gave_up"
    assert calls == ["1.1.1.1", "2.2.2.2"]


def test_run_group_enforces_global_runtime_limit_across_servers(monkeypatch):
    targets = [
        {"id": "one", "name": "Alpha", "ip": "1.1.1.1", "port": 7777},
        {"id": "two", "name": "Bravo", "ip": "2.2.2.2", "port": 7778},
    ]
    calls = _configure_group_run(monkeypatch, targets, iter(("rejected",)))
    joiner.config_mod.load_config()["max_minutes"] = 1
    times = iter((0, 0, 60))
    monkeypatch.setattr(joiner.time, "monotonic", lambda: next(times))

    assert joiner.run_group("group-1") == "gave_up"
    assert calls == ["1.1.1.1"]


def test_run_group_stops_during_advance_delay(monkeypatch):
    class StopDuringDelay:
        def __init__(self):
            self.stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, _timeout):
            self.stopped = True
            return True

    targets = [
        {"id": "one", "name": "Alpha", "ip": "1.1.1.1", "port": 7777},
        {"id": "two", "name": "Bravo", "ip": "2.2.2.2", "port": 7778},
    ]
    calls = _configure_group_run(monkeypatch, targets, iter(("rejected",)))
    joiner.config_mod.load_config()["retry_interval_s"] = 5
    stop = StopDuringDelay()

    assert joiner.run_group("group-1", stop_event=stop) == "stopped"
    assert calls == ["1.1.1.1"]


@pytest.mark.parametrize(
    ("groups", "expected"),
    [([], "not_found"), ([{"id": "group-1", "name": "Empty", "server_ids": []}], "empty_group")],
)
def test_run_group_rejects_missing_or_empty_group_without_starting_game(monkeypatch, groups, expected):
    monkeypatch.setattr(joiner, "resolve_target", lambda *_args: [], raising=False)
    monkeypatch.setattr(joiner, "server_store", SimpleNamespace(load_store=lambda: {"groups": groups}), raising=False)
    monkeypatch.setattr(joiner.winput, "set_dpi_awareness", lambda: (_ for _ in ()).throw(AssertionError("must not start")))
    monkeypatch.setattr(joiner.notify, "notify", lambda *_args: None)

    assert joiner.run_group("group-1") == expected


def test_automatic_direct_connect_ratio_targets_direct_connect_not_the_left_rent_area(monkeypatch):
    monkeypatch.setattr(joiner.winput, "get_window_rect", lambda _hwnd: (0, 0, 2048, 1152))

    assert joiner.LAYOUT_POINTS["direct_connect"] == (0.44, 0.193)
    assert joiner.layout_point(123, "direct_connect") == (901, 222)
    rent_area_point = (int(2048 * 0.41), int(1152 * 0.19))
    assert joiner.layout_point(123, "direct_connect") != rent_area_point


def test_automatic_warm_retries_use_background_navigation_without_steam_dialog(monkeypatch):
    events = []
    cfg = {
        "connection_method": "automatic",
        "navigation_mode": "automatic",
        "click_points": {},
        "attempt_timeout_s": 1,
        "retry_interval_s": 0,
        "max_unclear": 3,
        "max_attempts": 2,
        "max_minutes": 5,
    }

    class BackgroundWatcher(FakeWatcher):
        def __init__(self):
            self.outcomes = iter(("rejected_or_unknown", "success"))

        def wait_for_marker(self, marker, _timeout, stop_event=None):
            assert marker == joiner.logwatch.CONNECTING_MARK
            return True

    monkeypatch.setattr(joiner.config_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(joiner.resolver, "resolve", lambda _name: ("Canada #2", "1.2.3.4", 7778))
    monkeypatch.setattr(joiner.logwatch, "LogWatcher", BackgroundWatcher)
    monkeypatch.setattr(joiner.winput, "find_game_window", lambda _title: 123)
    monkeypatch.setattr(joiner.winput, "get_window_rect", lambda _hwnd: (0, 0, 1000, 1000))
    monkeypatch.setattr(joiner.winput, "post_click", lambda _hwnd, x, y: events.append(("click", x, y)))
    monkeypatch.setattr(joiner.winput, "replace_text", lambda _hwnd, text: events.append(("text", text)))
    monkeypatch.setattr(joiner.winput, "post_key_tap", lambda _hwnd, key: events.append(("key", key)))
    monkeypatch.setattr(joiner.winput, "foreground_click", lambda *_args: (_ for _ in ()).throw(AssertionError("must not use foreground click")))
    monkeypatch.setattr(joiner.winput, "foreground_replace_text", lambda *_args: (_ for _ in ()).throw(AssertionError("must not use foreground text")))
    monkeypatch.setattr(joiner.winput, "foreground_key_tap", lambda *_args: (_ for _ in ()).throw(AssertionError("must not use foreground key")))
    monkeypatch.setattr(joiner.notify, "notify", lambda *_args: None)
    monkeypatch.setattr(joiner.time, "sleep", lambda _seconds: None)

    assert joiner.run("Canada #2") == "success"
    assert events == [
        ("click", 120, 50),
        ("click", 440, 193),
        ("click", 500, 490),
        ("text", "1.2.3.4:7778"),
        ("click", 530, 550),
        ("key", joiner.winput.VK_RETURN),
        ("key", joiner.winput.VK_ESCAPE),
        ("click", 440, 193),
        ("click", 500, 490),
        ("text", "1.2.3.4:7778"),
        ("click", 530, 550),
        ("key", joiner.winput.VK_RETURN),
    ]


def test_run_group_opens_servers_only_for_its_first_warm_attempt(monkeypatch):
    targets = [
        {"id": "one", "name": "Alpha", "ip": "1.1.1.1", "port": 7777},
        {"id": "two", "name": "Bravo", "ip": "2.2.2.2", "port": 7778},
    ]
    calls = []
    _configure_group_run(monkeypatch, targets, iter(("rejected", "success")))

    def attempt(_hwnd, _cfg, _watcher, _ip, _port, **kwargs):
        calls.append(kwargs["open_servers"])
        return "rejected" if len(calls) == 1 else "success"

    monkeypatch.setattr(joiner, "connect_once", attempt)

    assert joiner.run_group("group-1") == "success"
    assert calls == [True, False]

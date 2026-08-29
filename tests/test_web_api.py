import json

import config
import server_store
from web_api import WebApi


def make_api(tmp_path, monkeypatch):
    store_path = tmp_path / "servers.json"
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(server_store, "STORE_PATH", str(store_path))
    monkeypatch.setattr(config, "CONFIG_PATH", str(config_path))
    return WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")


def test_bridge_exposes_structured_app_state_and_server_operations(tmp_path, monkeypatch):
    api = make_api(tmp_path, monkeypatch)
    saved = api.save_server("Private", "127.0.0.1", 7777)

    assert saved["ok"] is True
    assert saved["server"]["name"] == "Private"
    state = api.get_app_state()
    assert state["ok"] is True
    assert state["servers"][0]["ip"] == "127.0.0.1"
    assert "settings" in state and "calibration" in state
    assert state["settings"]["mute_game_audio"] is False

    renamed = api.rename_server(saved["server"]["id"], "Home")
    assert renamed["server"]["name"] == "Home"
    assert api.delete_server(saved["server"]["id"])["deleted"] is True


def test_bridge_group_and_settings_persist(tmp_path, monkeypatch):
    api = make_api(tmp_path, monkeypatch)
    first = api.save_server("One", "127.0.0.1", 7777)["server"]
    second = api.save_server("Two", "127.0.0.1", 7778)["server"]
    group = api.save_group("Queue", [first["id"], second["id"]])["group"]

    assert api.get_groups()["groups"][0]["name"] == "Queue"
    assert api.save_setting("max_minutes", 0)["settings"]["max_minutes"] == 0
    assert api.save_setting("mute_game_audio", True)["settings"]["mute_game_audio"] is True
    assert api.delete_group(group["id"])["deleted"] is True


def test_custom_theme_is_scoped_and_rejects_active_content(tmp_path, monkeypatch):
    api = make_api(tmp_path, monkeypatch)
    good = api.save_custom_theme("field.css", ".app-shell { --accent: #b186ff; }")
    assert good["ok"] is True
    assert ".app-shell" in good["css"]
    assert api.reset_theme()["theme"]["preset"] == "violet"

    bad = api.save_custom_theme("bad.css", "@import url('https://evil.test/x.css'); body { background: url(x); }")
    assert bad["ok"] is False
    assert "external" in bad["error"].lower() or "import" in bad["error"].lower()


def test_structured_events_are_not_javascript_fragments(tmp_path, monkeypatch):
    api = make_api(tmp_path, monkeypatch)
    events = []
    api.set_event_sink(events.append)
    api.emit("log_line", {"message": "hello", "attempt": 1})
    assert events == [{"event": "log_line", "data": {"message": "hello", "attempt": 1}}]


def test_bridge_returns_validation_errors_instead_of_raising(tmp_path, monkeypatch):
    api = make_api(tmp_path, monkeypatch)
    assert api.save_server("", "127.0.0.1", 7777)["ok"] is False
    assert api.save_server("Bad port", "127.0.0.1", 99999)["ok"] is False
    assert api.rename_server("missing", "Name")["ok"] is False
    assert api.refresh_server_status("missing")["ok"] is False
    assert api.save_group("Empty", ["missing"])["ok"] is False
    assert api.save_setting("attempt_timeout_s", "not-a-number")["ok"] is False
    assert api.save_setting("attempt_timeout_s", 0)["ok"] is False
    assert api.save_setting("connection_method", "unsafe")["ok"] is False

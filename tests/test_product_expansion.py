import json
import zipfile
import datetime as dt


def test_server_store_migrates_private_organization(tmp_path):
    import server_store
    path = tmp_path / "servers.json"
    path.write_text(json.dumps({"version": 2, "servers": [{"id": "s1", "name": "Private", "ip": "127.0.0.1", "port": 7777}], "groups": []}), encoding="utf-8")
    store = server_store.load_store(path)
    server = store["servers"][0]
    assert store["version"] >= 3
    assert server["tags"] == [] and server["notes"] == ""
    assert store["collections"] == []


def test_history_heatmap_needs_samples_then_reports_hour(tmp_path):
    from history import ServerHistory
    history = ServerHistory(tmp_path / "history.sqlite3")
    now = dt.datetime.now(dt.timezone.utc)
    for day in range(8):
        history.record("s1", True, 10 + day, 20, 30, observed_at=(now - dt.timedelta(days=day)).replace(hour=18, minute=0, second=0, microsecond=0).isoformat())
    heatmap = history.heatmap("s1")
    assert heatmap["ready"] is True
    assert any(cell["samples"] for cell in heatmap["cells"])


def test_safe_backup_excludes_credentials_and_restores_preview(tmp_path, monkeypatch):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    server = api.save_server("Private", "127.0.0.1", 7777)["server"]
    api.save_server_profile(server["id"], {"companion_token": "secret", "tags": ["friends"], "notes": "private note"})
    made = api.create_backup()
    assert made["ok"] is True
    with zipfile.ZipFile(made["path"]) as archive:
        payload = archive.read("backup.json").decode("utf-8")
    assert "secret" not in payload and "companion_token" not in payload
    preview = api.preview_backup(made["path"])
    assert preview["ok"] is True and preview["summary"]["servers"] == 1


def test_safe_backup_round_trip_restores_theme_and_never_restores_secret(tmp_path):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    saved = api.save_server("Before", "127.0.0.1", 7777)["server"]
    api.save_server_profile(saved["id"], {"companion_token": "never-export", "tags": ["private"]})
    api.theme_manager.set_preset("amber")
    backup = api.create_backup()["path"]
    api.delete_server(saved["id"])
    api.theme_manager.set_preset("slate")
    result = api.restore_backup(backup)
    assert result["ok"] is True
    restored = api.get_servers()["servers"][0]
    assert restored["name"] == "Before"
    assert restored.get("companion_token") in {None, ""}
    assert api.theme_manager.load()["preset"] == "amber"


def test_support_bundle_redacts_log_endpoints_and_tokens(tmp_path):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    logs = tmp_path / "logs"; logs.mkdir()
    (logs / "recent.log").write_text("Connecting 10.2.3.4:7777 bearer abc123 host.example.net:8888", encoding="utf-8")
    bundle = api.create_support_bundle()
    with zipfile.ZipFile(bundle["path"]) as archive:
        text = archive.read("logs/recent.log").decode("utf-8")
    assert "10.2.3.4" not in text and "abc123" not in text and "example.net" not in text


def test_setup_check_and_support_bundle_are_sanitized(tmp_path, monkeypatch):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    checks = api.run_setup_check()
    assert checks["ok"] is True and {item["id"] for item in checks["checks"]} >= {"game", "log", "audio", "calibration", "notifications", "discord"}
    api.save_server("Private", "127.0.0.1", 7777)
    bundle = api.create_support_bundle()
    assert bundle["ok"] is True
    with zipfile.ZipFile(bundle["path"]) as archive:
        text = archive.read("report.json").decode("utf-8")
    assert "127.0.0.1" not in text and "discord_application_id" not in text


def test_decision_log_explains_query_failure_and_user_stop(tmp_path):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    api._record_decision("query_failure", {"server_id": "s1"})
    api.stop_watch()
    reasons = [item["code"] for item in api.get_join_explanations()["items"]]
    assert "query_failure" in reasons and "user_stop" in reasons


def test_recovery_assistant_requires_explicit_retry_target(tmp_path, monkeypatch):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    server = api.save_server("Private", "127.0.0.1", 7777)["server"]
    api._record_decision("timeout")
    assert {item["id"] for item in api.get_recovery_actions()["actions"]} >= {"diagnostics", "retry"}
    received = []
    monkeypatch.setattr("web_api.joiner.run", lambda target, **_: received.append(target) or "stopped")
    assert api.recover_connection(server["id"], action="retry")["ok"] is True
    api._join_thread.join(timeout=1)
    assert received == ["Private"]


def test_watch_alert_action_rejects_stale_server_and_accepts_matching_slot(tmp_path):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    api._pending_watch_alert = {"server_id": "active", "action": None}
    assert api.handle_watch_alert_action("join", "old")["ok"] is False
    result = api.handle_watch_alert_action("mute_join", "active")
    assert result["ok"] is True
    assert api._pending_watch_alert["action"] == "mute_join"
    assert api._watch_alert.is_set()


def test_server_organization_is_private_but_persisted_and_searchable(tmp_path):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    server = api.save_server("Private", "127.0.0.1", 7777)["server"]
    saved = api.save_server_profile(server["id"], {
        "tags": ["friends", "low ping"], "notes": "weekday group",
        "collections": ["Favorites"],
        "notification_profile": {"enabled": True, "sound": True, "quiet": False, "actionable": True},
    })["server"]
    assert saved["notification_profile"]["actionable"] is True
    assert api.get_servers("weekday")["servers"][0]["id"] == server["id"]


def test_server_collections_are_created_and_assigned_locally(tmp_path):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    server = api.save_server("Private", "127.0.0.1", 7777)["server"]
    assert api.save_collection("Weekend") == {"ok": True, "collections": ["Weekend"]}
    saved = api.save_server_profile(server["id"], {"collections": ["Weekend"]})["server"]
    assert saved["collections"] == ["Weekend"]
    api.save_server_profile(server["id"], {"collections": ["Weekdays", "Weekend"]})
    assert api.get_collections()["collections"] == ["Weekdays", "Weekend"]
    assert api.get_servers("weekend")["servers"][0]["id"] == server["id"]


def test_portable_share_link_registration_is_explicit(tmp_path):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    result = api.register_destination_protocol()
    assert result["ok"] is False
    assert "packaged Windows app" in result["error"]


def test_webview_bridge_exposes_product_expansion_actions():
    from app_web import Bridge
    assert "register_destination_protocol" in Bridge._COMMANDS
    assert "get_companion_dashboard" in Bridge._COMMANDS

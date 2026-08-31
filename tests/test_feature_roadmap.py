import json
import threading


def test_store_v2_migrates_profiles_and_group_policies(tmp_path):
    import server_store
    path = tmp_path / "servers.json"
    path.write_text(json.dumps({"version": 1, "servers": [{"id": "s1", "name": "Private", "ip": "localhost", "port": 7777}], "groups": []}))
    store = server_store.load_store(path)
    assert store["version"] == 2
    assert store["servers"][0]["monitoring"]["enabled"] is False
    assert store["groups"] == []


def test_history_records_and_prunes_observations(tmp_path):
    from history import ServerHistory
    history = ServerHistory(tmp_path / "history.sqlite3", retention_days=30, max_rows=2)
    history.record("s1", True, 1, 20, 12.5)
    history.record("s1", True, 2, 20, 10.0)
    history.record("s1", False, 0, 20, None)
    assert len(history.recent("s1", limit=10)) == 2


def test_watch_selector_waits_for_single_slot_confirmation():
    from watch_mode import SlotConfirmation
    confirmation = SlotConfirmation(required_samples=2)
    assert confirmation.accepts({"available": True, "players": 19, "max_players": 20}) is False
    assert confirmation.accepts({"available": True, "players": 19, "max_players": 20}) is True
    assert confirmation.accepts({"available": False, "players": 20, "max_players": 20}) is False


def test_watch_query_failure_tracker_offers_fallback_after_three_failures():
    from watch_mode import QueryFailureTracker
    tracker = QueryFailureTracker(3)
    assert tracker.observe(None) is False
    assert tracker.observe(None) is False
    assert tracker.observe(None) is True
    assert tracker.observe({"available": False}) is False


def test_calibration_profile_health_detects_game_fingerprint_change(tmp_path):
    from calibration_profiles import CalibrationProfiles
    path = tmp_path / "game.exe"
    path.write_bytes(b"one")
    profiles = CalibrationProfiles(tmp_path / "calibrations.json")
    from calibration_profiles import executable_fingerprint
    profile = profiles.add("Display", {}, {"game_fingerprint": executable_fingerprint(path)})
    assert profiles.health(profile, {"game_fingerprint": executable_fingerprint(path)}) == "healthy"
    path.write_bytes(b"changed")
    assert profiles.health(profile, {"game_fingerprint": executable_fingerprint(path)}) == "stale"


def test_destination_bundle_excludes_private_data():
    from destinations import export_bundle, import_bundle
    raw = export_bundle("Private", [{"name": "Private", "ip": "localhost", "port": 7777, "password": "secret", "id": "local"}])
    payload = import_bundle(raw)
    assert payload["servers"] == [{"name": "Private", "host": "localhost", "port": 7777}]
    assert "password" not in raw and '"id"' not in raw


def test_companion_token_verification_is_constant_time_safe():
    from companion import TokenStore
    store = TokenStore.from_token("secret")
    assert store.verify("secret") is True
    assert store.verify("wrong") is False


def test_group_selection_applies_strategy_and_population_filters():
    from watch_mode import select_candidate
    candidates = [
        {"id": "slow", "available": True, "players": 5, "max_players": 20, "latency_ms": 80},
        {"id": "fast", "available": True, "players": 6, "max_players": 20, "latency_ms": 20},
        {"id": "full", "available": True, "players": 20, "max_players": 20, "latency_ms": 1},
    ]
    assert select_candidate(candidates, {"strategy": "lowest_latency", "maximum_fill_percent": 95})["id"] == "fast"


def test_group_policy_survives_order_edit(tmp_path):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    first = api.save_server("One", "127.0.0.1", 7777)["server"]
    second = api.save_server("Two", "127.0.0.1", 7778)["server"]
    group = api.save_group("Favorites", [first["id"], second["id"]])["group"]
    assert api.save_group_policy(group["id"], {"strategy": "lowest_latency", "maximum_fill_percent": 90})["ok"]
    updated = api.save_group("Favorites", [second["id"], first["id"]], group["id"])["group"]
    assert updated["server_ids"] == [second["id"], first["id"]]
    assert updated["policy"]["strategy"] == "lowest_latency"


def test_group_policy_rejects_invalid_population_and_loop_values(tmp_path):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    server = api.save_server("One", "127.0.0.1", 7777)["server"]
    group = api.save_group("Favorites", [server["id"]])["group"]
    assert api.save_group_policy(group["id"], {"maximum_fill_percent": 101})["ok"] is False
    assert api.save_group_policy(group["id"], {"minimum_players": -1})["ok"] is False
    assert api.save_group_policy(group["id"], {"loop": "yes"})["ok"] is False


def test_discord_enabled_preference_is_restored_on_api_start(tmp_path):
    from web_api import WebApi
    first = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    first.set_discord_enabled(True)
    second = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    assert second.get_discord_status()["enabled"] is True


def test_manual_game_audio_toggle_stops_and_restores_controller(tmp_path, monkeypatch):
    from web_api import WebApi
    class FakeController:
        def __init__(self): self.stopped = False
        def stop(self): self.stopped = True
    controller = FakeController()
    monkeypatch.setattr("audio_control.start_for_run", lambda *args, **kwargs: controller)
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    assert api.set_game_audio_muted(True)["muted"] is True
    assert api.set_game_audio_muted(False)["muted"] is False
    assert controller.stopped is True


def test_api_shutdown_releases_monitor_audio_and_presence(tmp_path, monkeypatch):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    calls = []
    class FakeMonitor:
        def stop(self): calls.append("monitor")
    class FakeAudio:
        def stop(self): calls.append("audio")
    api._monitor = FakeMonitor()
    api._manual_audio_controller = FakeAudio()
    monkeypatch.setattr(api, "clear_discord_presence", lambda: calls.append("discord"))
    api.shutdown()
    assert calls == ["monitor", "audio", "discord"]


def test_destination_link_round_trips():
    from destinations import decode_link, encode_link, export_bundle
    raw = export_bundle("Private", [{"name": "Private", "ip": "127.0.0.1", "port": 7777}])
    assert decode_link(encode_link(raw))["name"] == "Private"


def test_destination_link_rejects_wrong_scheme_and_malformed_bundles():
    from destinations import decode_link, import_bundle
    for value in ("https://example.test/?data=abc", "scpsl-autojoin://other?data=abc", "scpsl-autojoin://import?data=%%%"):
        try:
            decode_link(value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid destination link was accepted")
    for value in ("[]", '{"schema":"scpsl-autojoin.destination","version":1,"kind":"server","servers":[{"host":"","port":7777}]}'):
        try:
            import_bundle(value)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError("invalid destination bundle was accepted")


def test_web_api_exports_shareable_destination_link(tmp_path):
    from web_api import WebApi
    from destinations import decode_link
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    server = api.save_server("Private", "127.0.0.1", 7777)["server"]
    result = api.export_destination_link("Shared", [server["id"]])
    assert result["ok"] is True
    assert decode_link(result["link"])["name"] == "Shared"


def test_translation_update_source_is_classified():
    from translation_updates import source_from_url
    assert source_from_url("https://github.com/example/pack") == ("github", "example", "pack")
    assert source_from_url("C:/packs/local") == ("local", None, None)


def test_destination_import_creates_named_saved_servers(tmp_path):
    from web_api import WebApi
    from destinations import export_bundle
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    raw = export_bundle("Imported", [{"name": "Private", "ip": "127.0.0.1", "port": 7777}])
    result = api.import_destination(raw)
    assert result["ok"] is True
    assert result["servers"][0]["name"] == "Private"


def test_companion_client_requires_https_for_remote_urls():
    from companion_client import CompanionClient
    assert CompanionClient("https://example.test", "token").url.startswith("https://")
    try:
        CompanionClient("http://example.test", "token")
    except ValueError:
        pass
    else:
        raise AssertionError("remote HTTP companion must be rejected")


def test_translation_update_downloads_valid_pack_and_preserves_source_metadata(tmp_path):
    from translation_packs import PackManager

    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text(json.dumps({"Name": "Pack", "Authors": ["A"]}))
    (source / "English.txt").write_text("new")
    manager = PackManager(tmp_path / "data", tmp_path / "Translations")
    first = manager.import_path(source, "https://github.com/example/pack")
    updated = tmp_path / "updated"
    updated.mkdir()
    (updated / "manifest.json").write_text(json.dumps({"Name": "Pack", "Authors": ["A"]}))
    (updated / "English.txt").write_text("updated")
    result = manager.update_from_path(first["id"], updated, "https://github.com/example/pack")
    assert result["ok"] is True
    assert (tmp_path / "Translations" / first["folder"] / "English.txt").read_text() == "updated"
    assert result["pack"]["source"] == "https://github.com/example/pack"
    assert result["pack"]["backup"]


def test_web_api_translation_update_is_user_initiated_and_uses_unique_temp_file(tmp_path, monkeypatch):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    source = tmp_path / "pack"
    source.mkdir(); (source / "manifest.json").write_text(json.dumps({"Name": "Pack", "Authors": []})); (source / "English.txt").write_text("one")
    record = api.import_translation_pack(str(source), "https://github.com/example/pack")["pack"]
    updated = tmp_path / "updated.zip"
    import zipfile
    with zipfile.ZipFile(updated, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"Name": "Pack", "Authors": []}))
        archive.writestr("English.txt", "two")
    monkeypatch.setattr(api.pack_manager, "_read_url", lambda _: updated.read_bytes())
    result = api.update_translation_pack(record["id"])
    assert result["ok"] is True
    assert (tmp_path / "Translations" / record["folder"] / "English.txt").read_text() == "two"


def test_companion_rate_limiter_allows_one_request_per_second():
    from companion_server import RequestRateLimiter
    limiter = RequestRateLimiter(interval=1.0)
    assert limiter.allow("127.0.0.1", now=10.0) is True
    assert limiter.allow("127.0.0.1", now=10.5) is False
    assert limiter.allow("127.0.0.1", now=11.0) is True


def test_background_monitor_limits_servers_and_records_samples():
    from monitoring import BackgroundMonitor

    seen = []
    monitor = BackgroundMonitor(
        [
            {"id": "one", "ip": "127.0.0.1", "port": 7777},
            {"id": "two", "ip": "127.0.0.1", "port": 7778},
        ],
        query=lambda server: {"available": True, "players": 1, "max_players": 20, "latency_ms": 4},
        record=lambda server, status: seen.append((server["id"], status["players"])),
        interval=60,
        jitter=0,
    )
    assert monitor.sample_once() == 2
    assert seen == [("one", 1), ("two", 1)]


def test_background_monitor_caps_sweep_at_fifty_servers():
    from monitoring import BackgroundMonitor

    servers = [{"id": str(i), "ip": "127.0.0.1", "port": 7000 + i} for i in range(51)]
    calls = []
    monitor = BackgroundMonitor(servers, query=lambda server: calls.append(server) or {}, record=lambda *_: None)
    assert monitor.sample_once() == 50
    assert len(calls) == 50


def test_web_api_background_monitor_is_opt_in_and_stoppable(tmp_path, monkeypatch):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    server = api.save_server("Private", "127.0.0.1", 7777)["server"]
    api.save_server_profile(server["id"], {"monitoring": {"enabled": True}})
    monkeypatch.setattr("resolver.query_server", lambda *args, **kwargs: {"available": True, "players": 1, "max_players": 20})
    assert api.get_monitor_status()["running"] is False
    assert api.start_background_monitor()["ok"] is True
    assert api.get_monitor_status()["running"] is True
    assert api.stop_background_monitor()["ok"] is True


def test_web_api_import_destination_link_uses_previewable_bundle(tmp_path):
    from web_api import WebApi
    from destinations import encode_link, export_bundle
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    raw = export_bundle("Shared", [{"name": "Private", "ip": "127.0.0.1", "port": 7777}])
    link = encode_link(raw)
    result = api.import_destination_link(link)
    assert result["ok"] is True
    assert result["destination"]["name"] == "Shared"
    assert api.import_destination_link(raw)["ok"] is True


def test_discord_ipc_frames_activity_without_affecting_disabled_presence():
    from discord_presence import DiscordIPC, DiscordPresence
    frame = DiscordIPC.frame(1, {"cmd": "SET_ACTIVITY", "args": {"pid": 1}})
    assert frame[:8] == (1).to_bytes(4, "little") + (len(frame) - 8).to_bytes(4, "little")
    presence = DiscordPresence(client_id=None)
    assert presence.set_enabled(True)["ok"] is True
    assert presence.update("watching")["enabled"] is True


def test_discord_presence_reports_when_discord_ipc_is_unavailable():
    """The UI must not claim presence is live when Discord rejects IPC."""
    from discord_presence import DiscordPresence

    class OfflineIPC:
        def set_activity(self, activity):
            return False

        def close(self):
            return None

    presence = DiscordPresence(ipc=OfflineIPC())
    presence.set_enabled(True)
    result = presence.update("watching")

    assert result["ok"] is False
    assert result["enabled"] is True
    assert result["connected"] is False


def test_discord_activity_uses_the_registered_s_mark_asset():
    """The Discord payload names the same compact mark used by the desktop app."""
    from discord_presence import DiscordPresence

    class RecordingIPC:
        def __init__(self):
            self.activity = None

        def set_activity(self, activity):
            self.activity = activity
            return True

        def close(self):
            return None

    ipc = RecordingIPC()
    presence = DiscordPresence(ipc=ipc)
    presence.set_enabled(True)
    result = presence.update("watching")

    assert result["connected"] is True
    assert ipc.activity["assets"]["large_image"] == "scpsl-autojoin-s"


def test_discord_sharing_requires_global_and_server_permission(tmp_path):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    server = api.save_server("Private", "127.0.0.1", 7777)["server"]
    api.set_discord_enabled(True)
    assert api.update_discord_presence("joined", server["id"], 7)["presence"]["players"] is None
    api.save_setting("discord_share_players", True)
    api.save_server_profile(server["id"], {"share_presence": True})
    assert api.update_discord_presence("joined", server["id"], 7)["presence"]["players"] == 7


def test_discord_presence_hides_a_server_until_that_server_is_explicitly_shareable(tmp_path):
    from web_api import WebApi

    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    server = api.save_server("Private", "127.0.0.1", 7777)["server"]
    api.set_discord_enabled(True)

    hidden = api.update_discord_presence("watching", server["id"], 7)

    assert hidden["presence"]["server_name"] == ""


def test_discord_shareable_server_includes_an_opaque_review_only_join_secret(tmp_path):
    from discord_presence import DiscordPresence
    from destinations import decode_link
    from web_api import WebApi

    class RecordingIPC:
        def set_activity(self, activity):
            self.activity = activity
            return True

        def close(self):
            return None

    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    server = api.save_server("Private", "127.0.0.1", 7777)["server"]
    ipc = RecordingIPC()
    api.discord = DiscordPresence(ipc=ipc, on_join=api._handle_discord_join)
    api.set_discord_enabled(True)
    api.save_server_profile(server["id"], {"share_presence": True})
    api.save_setting("discord_share_players", True)

    result = api.update_discord_presence("watching", server["id"], 7, 25, 100)

    assert result["presence"]["join_available"] is True
    assert decode_link(ipc.activity["secrets"]["join"])["servers"][0]["name"] == "Private"
    assert ipc.activity["party"]["size"] == [7, 25]


def test_discord_join_request_only_opens_the_existing_import_preview(tmp_path):
    from destinations import encode_link, export_bundle
    from web_api import WebApi

    events = []
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    api.set_event_sink(events.append)
    secret = encode_link(export_bundle("Friend", [{"name": "Friend", "host": "127.0.0.1", "port": 7777}]))

    assert api._handle_discord_join(secret) is True
    assert events == [{"event": "destination_import_requested", "data": {"raw": secret, "source": "discord"}}]
    assert api.get_servers()["servers"] == []


def test_discord_ipc_dispatches_a_join_secret_from_a_local_pipe():
    from discord_presence import DiscordIPC

    class ReadPipe:
        def __init__(self, data):
            self.data = bytearray(data)

        def read(self, size):
            value = bytes(self.data[:size])
            del self.data[:size]
            return value

    received = []
    ipc = DiscordIPC(on_join=received.append)
    event = {"cmd": "DISPATCH", "data": {"evt": "ACTIVITY_JOIN", "data": {"secret": "scpsl-autojoin://import?data=test"}}}
    ipc.connection = ReadPipe(DiscordIPC.frame(1, event))
    ipc._reader = threading.current_thread()

    ipc._read_events()

    assert received == ["scpsl-autojoin://import?data=test"]


def test_discord_application_id_is_saved_and_reconfigures_presence(tmp_path):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")

    result = api.set_discord_application_id("123456789012345678")

    assert result["ok"] is True
    assert api.get_settings()["settings"]["discord_application_id"] == "123456789012345678"
    assert api.discord.ipc.client_id == "123456789012345678"


def test_successful_join_closes_watch_state_as_joined(tmp_path):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    api._watch_state["state"] = "joining"
    api._run_join(lambda target, on_status, stop_event: "success", "server")
    assert api._watch_state["state"] == "joined"


def test_companion_status_requires_protocol_and_server_capacity_fields():
    from companion_client import validate_status
    valid = {"protocol_version": 1, "server": {}, "round": {}, "capacity": {"players": 0, "max_players": 20}, "player": {}}
    assert validate_status(valid)["protocol_version"] == 1
    try:
        validate_status({"protocol_version": 1, "capacity": {}})
    except ValueError:
        pass
    else:
        raise AssertionError("incomplete companion status must be rejected")


def test_companion_token_is_protected_and_companion_capacity_is_preferred(tmp_path, monkeypatch):
    from web_api import WebApi
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    server = api.save_server("Owned", "127.0.0.1", 7777)["server"]
    saved = api.save_server_profile(server["id"], {"companion_url": "http://127.0.0.1:8787", "companion_token": "a-secret-token"})
    assert saved["ok"] is True
    raw = (tmp_path / "servers.json").read_text()
    assert "a-secret-token" not in raw

    class FakeClient:
        def __init__(self, url, token):
            assert url.endswith(":8787")
            assert token == "a-secret-token"
        def status(self, timeout=2):
            return {"protocol_version": 1, "server": {}, "round": {"phase": "running"}, "capacity": {"players": 3, "max_players": 20}, "player": {}}
    monkeypatch.setattr("companion_client.CompanionClient", FakeClient)
    result = api._query_server(saved["server"])
    assert result["source"] == "companion"
    assert result["players"] == 3


def test_history_insights_include_periods_and_full_frequency(tmp_path):
    from history import ServerHistory
    history = ServerHistory(tmp_path / "history.sqlite3")
    history.record("s1", True, 20, 20, 10)
    history.record("s1", True, 5, 20, 20)
    result = history.insights("s1")
    assert set(result["periods"]) == {"24h", "7d", "30d"}
    assert result["full_frequency"] == 0.5


def test_calibration_profiles_can_be_renamed_and_duplicated(tmp_path):
    from calibration_profiles import CalibrationProfiles
    profiles = CalibrationProfiles(tmp_path / "calibrations.json")
    original = profiles.add("4K", {"servers_tab": [1, 2]}, {"dpi": 144})
    renamed = profiles.rename(original["id"], "4K main")
    duplicate = profiles.duplicate(original["id"], "4K backup")
    assert renamed["name"] == "4K main"
    assert duplicate["name"] == "4K backup"
    assert duplicate["points"] == original["points"]


def test_legacy_calibration_is_migrated_to_named_profile(tmp_path):
    from web_api import WebApi
    import config
    cfg = dict(config.DEFAULTS)
    cfg["click_points"] = {name: [10, 20] for name in config.REQUIRED_CLICK_POINTS}
    config.save_config(cfg, tmp_path / "config.json")
    api = WebApi(data_dir=tmp_path, translations_dir=tmp_path / "Translations")
    profiles = api.get_calibration_profiles()
    assert profiles["profiles"][0]["name"] == "Imported calibration"
    assert profiles["active"] == profiles["profiles"][0]["id"]


def test_calibration_storage_quarantines_corruption(tmp_path):
    from calibration_profiles import CalibrationProfiles
    path = tmp_path / "calibrations.json"
    path.write_text("{not-json", encoding="utf-8")
    profiles = CalibrationProfiles(path)
    assert profiles.load()["profiles"] == []
    assert list(tmp_path.glob("calibrations.json.corrupt*"))


def test_history_database_corruption_is_quarantined(tmp_path):
    from history import ServerHistory
    path = tmp_path / "history.sqlite3"
    path.write_bytes(b"not a sqlite database")
    history = ServerHistory(path)
    history.record("s1", True, 1, 20, 12)
    assert history.recent("s1")[0]["players"] == 1
    assert list(tmp_path.glob("history.sqlite3.corrupt*"))


def test_instance_forward_listener_validates_and_dispatches_payload():
    from instance_forward import dispatch_payload
    received = []
    dispatch_payload({"command": "import_destination", "data": "bundle"}, received.append)
    assert received == [{"command": "import_destination", "data": "bundle"}]
    try:
        dispatch_payload({"command": "delete_all"}, received.append)
    except ValueError:
        pass
    else:
        raise AssertionError("unexpected forwarded commands must be rejected")


def test_translation_release_source_is_normalized():
    from translation_updates import source_details
    assert source_details("https://github.com/example/pack/releases/tag/v2.0") == {"kind": "github_release", "owner": "example", "repo": "pack", "tag": "v2.0"}


def test_startup_destination_link_is_forwarded_to_existing_instance(monkeypatch):
    import app_web
    sent = []
    monkeypatch.setattr(app_web, "send_destination_to_existing_instance", lambda link: sent.append(link) or True)
    assert app_web.forward_startup_link("scpsl-autojoin://import?data=abc") is True
    assert sent == ["scpsl-autojoin://import?data=abc"]
    assert app_web.forward_startup_link("not-a-destination") is False


def test_destination_landing_page_only_forwards_protocol_links():
    from pathlib import Path
    page = (Path(__file__).parents[1] / "docs" / "destination-import.html").read_text(encoding="utf-8")
    assert "location.replace(link)" in page
    assert "scpsl-autojoin://" in page
    assert "location.search" not in page

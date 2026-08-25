import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server_store


def test_missing_store_has_versioned_shape(tmp_path):
    path = str(tmp_path / "servers.json")
    assert server_store.load_store(path) == {"version": 1, "servers": [], "groups": []}


def test_legacy_servers_migrate_with_stable_ids(tmp_path):
    path = str(tmp_path / "servers.json")
    with open(path, "w", encoding="utf-8") as stream:
        json.dump({"Canada 2": {"ip": "1.2.3.4", "port": 7777}}, stream)

    first = server_store.load_store(path)
    second = server_store.load_store(path)
    assert first["servers"] == second["servers"]
    assert first["servers"][0]["name"] == "Canada 2"
    assert first["servers"][0]["ip"] == "1.2.3.4"
    assert first["servers"][0]["port"] == 7777
    assert json.load(open(path, encoding="utf-8"))["version"] == 1


def test_server_and_group_crud_preserves_order_and_cleans_membership(tmp_path):
    path = str(tmp_path / "servers.json")
    first = server_store.upsert_server("One", "one.example", 7777, path)
    second = server_store.upsert_server("Two", "2.3.4.5", 7778, path)
    group = server_store.create_group("Ordered", [second["id"], first["id"]], path)
    assert group["server_ids"] == [second["id"], first["id"]]
    updated = server_store.update_group(group["id"], [first["id"]], path)
    assert updated["server_ids"] == [first["id"]]
    assert server_store.delete_server(first["id"], path) is True
    assert server_store.load_store(path)["groups"][0]["server_ids"] == []


def test_group_rejects_duplicate_server_ids(tmp_path):
    path = str(tmp_path / "servers.json")
    server = server_store.upsert_server("One", "1.2.3.4", 7777, path)
    with pytest.raises(ValueError, match="duplicate"):
        server_store.create_group("Bad", [server["id"], server["id"]], path)


def test_group_delete_and_endpoint_validation(tmp_path):
    path = str(tmp_path / "servers.json")
    with pytest.raises(ValueError):
        server_store.upsert_server("Bad", "not a host", 7777, path)
    server = server_store.upsert_server("One", "1.2.3.4", 7777, path)
    group = server_store.create_group("Group", [server["id"]], path)
    assert server_store.delete_group(group["id"], path) is True
    assert server_store.delete_group(group["id"], path) is False


def test_save_store_writes_via_replace(tmp_path, monkeypatch):
    path = str(tmp_path / "servers.json")
    calls = []
    original = os.replace
    monkeypatch.setattr(os, "replace", lambda source, target: calls.append((source, target)) or original(source, target))
    server_store.save_store({"version": 1, "servers": [], "groups": []}, path)
    assert calls and calls[0][1] == path
    assert not os.path.exists(calls[0][0])


def test_search_servers_matches_name_and_endpoint(tmp_path):
    path = str(tmp_path / "servers.json")
    server_store.upsert_server("Alpha", "10.0.0.1", 7777, path)
    server_store.upsert_server("Bravo", "bravo.example", 8888, path)
    assert [item["name"] for item in server_store.search_servers("bravo", path)] == ["Bravo"]
    assert [item["name"] for item in server_store.search_servers("10.0.0.1", path)] == ["Alpha"]


def test_load_rejects_invalid_version_one_server_record(tmp_path):
    path = str(tmp_path / "servers.json")
    with open(path, "w", encoding="utf-8") as stream:
        json.dump({"version": 1, "servers": [{"id": "x", "name": "Bad", "ip": "bad host", "port": 7777}], "groups": []}, stream)
    with pytest.raises(ValueError, match="endpoint"):
        server_store.load_store(path)


def test_save_rejects_invalid_version_one_server_record(tmp_path):
    path = str(tmp_path / "servers.json")
    with pytest.raises(ValueError, match="port"):
        server_store.save_store({"version": 1, "servers": [{"id": "x", "name": "Bad", "ip": "1.2.3.4", "port": 0}], "groups": []}, path)

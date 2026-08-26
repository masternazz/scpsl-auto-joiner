"""Versioned local storage for saved SCP:SL servers and ordered groups."""
import json
import os
import re
import socket
import tempfile
import uuid

from app_paths import app_dir

STORE_PATH = os.path.join(app_dir(), "servers.json")
STORE_VERSION = 1
_MIGRATION_NAMESPACE = uuid.UUID("f2d40e6e-7f8d-4e5d-a6e6-6a2c4d1de5b5")
_HOST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,253}[A-Za-z0-9])?$")


def _path(path):
    return path or STORE_PATH


def _empty_store():
    return {"version": STORE_VERSION, "servers": [], "groups": []}


def _validate_endpoint(ip, port):
    if not isinstance(ip, str) or not ip.strip() or any(char in ip for char in "\r\n\x00"):
        raise ValueError("invalid endpoint")
    ip = ip.strip()
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise ValueError("invalid port") from None
    if isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError("invalid port")
    try:
        socket.getaddrinfo(ip, port, type=socket.SOCK_DGRAM)
    except socket.gaierror:
        # Permit syntactically valid saved hostnames even when offline.
        if not _HOST_RE.fullmatch(ip) or any(len(part) > 63 for part in ip.split(".")):
            raise ValueError("invalid endpoint") from None
    return ip, port


def _migrate(data):
    if isinstance(data, dict) and data.get("version") == STORE_VERSION:
        store = {
            "version": STORE_VERSION,
            "servers": list(data.get("servers", [])),
            "groups": list(data.get("groups", [])),
        }
        for index, server in enumerate(store["servers"]):
            store["servers"][index] = _validate_server_record(server)
        available = {server["id"] for server in store["servers"]}
        for index, group in enumerate(store["groups"]):
            store["groups"][index] = _validate_group_record(group, available)
        return store
    if not isinstance(data, dict):
        raise ValueError("store must be an object")
    servers = []
    for name, entry in data.items():
        ip, port = _validate_endpoint(entry.get("ip"), entry.get("port"))
        server_id = str(uuid.uuid5(_MIGRATION_NAMESPACE, "%s\0%s\0%s" % (name, ip, port)))
        servers.append({"id": server_id, "name": str(name), "ip": ip, "port": port})
    return {"version": STORE_VERSION, "servers": servers, "groups": []}


def _validate_server_record(server):
    if not isinstance(server, dict):
        raise ValueError("invalid server record")
    if not isinstance(server.get("id"), str) or not server["id"].strip():
        raise ValueError("invalid server ID")
    if not isinstance(server.get("name"), str) or not server["name"].strip():
        raise ValueError("invalid server name")
    ip, port = _validate_endpoint(server.get("ip"), server.get("port"))
    normalized = dict(server)
    normalized.update({"id": server["id"].strip(), "name": server["name"].strip(), "ip": ip, "port": port})
    return normalized


def _validate_group_record(group, available):
    if not isinstance(group, dict):
        raise ValueError("invalid group record")
    if not isinstance(group.get("id"), str) or not group["id"].strip():
        raise ValueError("invalid group ID")
    if not isinstance(group.get("name"), str) or not group["name"].strip():
        raise ValueError("invalid group name")
    server_ids = group.get("server_ids")
    if not isinstance(server_ids, list) or not all(isinstance(item, str) and item for item in server_ids):
        raise ValueError("invalid group server IDs")
    if len(server_ids) != len(set(server_ids)):
        raise ValueError("duplicate server IDs")
    if any(item not in available for item in server_ids):
        raise ValueError("unknown server ID")
    normalized = dict(group)
    normalized.update({"id": group["id"].strip(), "name": group["name"].strip(), "server_ids": list(server_ids)})
    return normalized


def load_store(path=None):
    path = _path(path)
    if not os.path.exists(path):
        return _empty_store()
    with open(path, encoding="utf-8") as stream:
        original = json.load(stream)
    store = _migrate(original)
    if not (isinstance(original, dict) and original.get("version") == STORE_VERSION):
        save_store(store, path)
    return store


def save_store(store, path=None):
    path = _path(path)
    normalized = _migrate(store)
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".servers-", suffix=".tmp", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(normalized, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def upsert_server(name, ip, port, path=None):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("invalid server name")
    ip, port = _validate_endpoint(ip, port)
    store = load_store(path)
    for server in store["servers"]:
        if server["name"] == name:
            server.update({"ip": ip, "port": port})
            save_store(store, path)
            return dict(server)
    server = {"id": str(uuid.uuid4()), "name": name.strip(), "ip": ip, "port": port}
    store["servers"].append(server)
    save_store(store, path)
    return dict(server)


def update_server(server_id, name, ip, port, path=None):
    """Update a saved server without changing its group membership ID."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("invalid server name")
    ip, port = _validate_endpoint(ip, port)
    store = load_store(path)
    name = name.strip()
    if any(server["id"] != server_id and server["name"] == name for server in store["servers"]):
        raise ValueError("duplicate server name")
    for server in store["servers"]:
        if server["id"] == server_id:
            server.update({"name": name, "ip": ip, "port": port})
            save_store(store, path)
            return dict(server)
    raise KeyError(server_id)


def delete_server(server_id, path=None):
    store = load_store(path)
    before = len(store["servers"])
    store["servers"] = [server for server in store["servers"] if server["id"] != server_id]
    if len(store["servers"]) == before:
        return False
    for group in store["groups"]:
        group["server_ids"] = [item for item in group["server_ids"] if item != server_id]
    save_store(store, path)
    return True


def _group(name, server_ids, store, group_id=None):
    available = {server["id"] for server in store["servers"]}
    return _validate_group_record(
        {"id": group_id or str(uuid.uuid4()), "name": name, "server_ids": list(server_ids)},
        available,
    )


def create_group(name, server_ids, path=None):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("invalid group name")
    store = load_store(path)
    group = _group(name, server_ids, store)
    store["groups"].append(group)
    save_store(store, path)
    return dict(group)


def update_group(group_id, server_ids, path=None, name=None):
    store = load_store(path)
    for index, group in enumerate(store["groups"]):
        if group["id"] == group_id:
            updated = _group(group["name"] if name is None else name, server_ids, store, group_id)
            store["groups"][index] = updated
            save_store(store, path)
            return dict(updated)
    raise KeyError(group_id)


def delete_group(group_id, path=None):
    store = load_store(path)
    groups = [group for group in store["groups"] if group["id"] != group_id]
    if len(groups) == len(store["groups"]):
        return False
    store["groups"] = groups
    save_store(store, path)
    return True


def search_servers(query, path=None):
    query = str(query or "").casefold()
    return [dict(server) for server in load_store(path)["servers"]
            if not query or query in " ".join(str(server.get(key, "")) for key in ("name", "ip", "port")).casefold()]

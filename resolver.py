"""Resolves a typed server name to (name, ip, port) via a local servers.json
— NOT api.scpslgame.com (Cloudflare-gated, needs a Northwood-issued key; see
the design spec). servers.json is populated by the "remember a server" flow
in gui.py, not hand-edited."""
import difflib
import json
import os

from app_paths import app_dir

SERVERS_PATH = os.path.join(app_dir(), "servers.json")


def load_servers(path=None):
    path = path or SERVERS_PATH
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_servers(servers, path=None):
    path = path or SERVERS_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(servers, f, indent=2)


def remember_server(name, ip, port, path=None):
    path = path or SERVERS_PATH
    servers = load_servers(path)
    servers[name] = {"ip": ip, "port": int(port)}
    save_servers(servers, path)


def resolve(query, path=None):
    """Return (name, ip, port) for the closest saved server name, or None if
    servers.json is empty or nothing is close enough."""
    path = path or SERVERS_PATH
    servers = load_servers(path)
    if not servers:
        return None
    matches = difflib.get_close_matches(query, servers.keys(), n=1, cutoff=0.3)
    if not matches:
        return None
    name = matches[0]
    entry = servers[name]
    return name, entry["ip"], entry["port"]

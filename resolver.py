"""Resolves a typed server name to (name, ip, port) via a local servers.json
— NOT api.scpslgame.com (Cloudflare-gated, needs a Northwood-issued key; see
the design spec). servers.json is populated by the "remember a server" flow
in gui.py, not hand-edited."""
import difflib
import json
import os
import re
import socket

from app_paths import app_dir

A2S_INFO_QUERY = b"\xff\xff\xff\xffTSource Engine Query\x00"
RICH_TEXT_TAG_RE = re.compile(r"<[^>]{1,100}>")

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


def _parse_a2s_info(packet):
    """Return the server name from a single-packet A2S_INFO response."""
    if len(packet) < 7 or packet[:5] != b"\xff\xff\xff\xffI":
        return None
    name = packet[6:].split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()
    name = " ".join(RICH_TEXT_TAG_RE.sub("", name).split())
    return name or None


def query_server_name(ip, port, timeout=1.5):
    """Ask the game server for its public Steam-query name."""
    address = (str(ip), int(port))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(A2S_INFO_QUERY, address)
        packet, _ = sock.recvfrom(4096)
        if packet[:5] == b"\xff\xff\xff\xffA" and len(packet) >= 9:
            sock.sendto(A2S_INFO_QUERY + packet[5:9], address)
            packet, _ = sock.recvfrom(4096)
        return _parse_a2s_info(packet)
    except (OSError, ValueError):
        return None
    finally:
        sock.close()


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

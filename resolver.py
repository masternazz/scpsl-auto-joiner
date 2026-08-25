"""Resolves a typed server name to (name, ip, port) via a local servers.json
— NOT api.scpslgame.com (Cloudflare-gated, needs a Northwood-issued key; see
the design spec). servers.json is populated by the "remember a server" flow
in gui.py, not hand-edited."""
import difflib
import os
import re
import socket
import time

from app_paths import app_dir
import server_store

A2S_INFO_QUERY = b"\xff\xff\xff\xffTSource Engine Query\x00"
RICH_TEXT_TAG_RE = re.compile(r"<[^>]{1,100}>")

SERVERS_PATH = os.path.join(app_dir(), "servers.json")


def load_servers(path=None):
    path = path or SERVERS_PATH
    if not os.path.exists(path):
        return {}
    data = server_store.load_store(path)
    return {server["name"]: {"ip": server["ip"], "port": server["port"]} for server in data["servers"]}


def save_servers(servers, path=None):
    path = path or SERVERS_PATH
    server_store.save_store(servers, path)


def remember_server(name, ip, port, path=None):
    server_store.upsert_server(name, ip, port, path or SERVERS_PATH)


def forget_server(name, path=None):
    path = path or SERVERS_PATH
    store = server_store.load_store(path)
    server = next((item for item in store["servers"] if item["name"] == name), None)
    if server is None:
        return False
    return server_store.delete_server(server["id"], path)


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


def _parse_a2s_info_details(packet):
    if len(packet) < 6 or packet[:5] != b"\xff\xff\xff\xffI":
        return None
    offset = 6
    fields = []
    for _ in range(4):
        end = packet.find(b"\x00", offset)
        if end < 0:
            return None
        fields.append(packet[offset:end].decode("utf-8", errors="replace"))
        offset = end + 1
    if len(packet) < offset + 9:
        return None
    server_id = int.from_bytes(packet[offset:offset + 2], "little")
    players, max_players, bots = packet[offset + 2:offset + 5]
    server_type, environment, visibility, vac = packet[offset + 5:offset + 9]
    offset += 9
    result = {"name": " ".join(RICH_TEXT_TAG_RE.sub("", fields[0]).split()), "map": fields[1],
              "folder": fields[2], "game": fields[3], "id": server_id, "players": players,
              "max_players": max_players, "bots": bots, "server_type": chr(server_type),
              "environment": chr(environment), "password": bool(visibility), "vac": bool(vac)}
    if len(packet) > offset:
        edf = packet[offset]
        offset += 1
        result["edf"] = edf
        if edf & 0x80 and len(packet) >= offset + 2:
            result["port"] = int.from_bytes(packet[offset:offset + 2], "little")
    return result


def query_server(ip, port, timeout=1.5, path=None):
    try:
        address = (str(ip), int(port))
        saved = server_store.load_store(path or SERVERS_PATH)["servers"]
        if not any(server["ip"] == address[0] and server["port"] == address[1] for server in saved):
            return None
        started = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(A2S_INFO_QUERY, address)
        packet, _ = sock.recvfrom(4096)
        if packet[:5] == b"\xff\xff\xff\xffA" and len(packet) >= 9:
            sock.sendto(A2S_INFO_QUERY + packet[5:9], address)
            packet, _ = sock.recvfrom(4096)
        result = _parse_a2s_info_details(packet)
        if result is None:
            return None
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        result["available"] = True
        return result
    except (OSError, ValueError):
        return None
    finally:
        if "sock" in locals():
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

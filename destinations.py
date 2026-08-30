"""Validated, privacy-preserving server destination bundles."""
import base64
import json
from urllib.parse import parse_qs, urlparse

SCHEMA = "scpsl-autojoin.destination"


def export_bundle(name, servers):
    safe = [{"name": str(s["name"]), "host": str(s.get("host", s.get("ip", ""))), "port": int(s["port"])} for s in servers]
    if not 1 <= len(safe) <= 20:
        raise ValueError("bundle must contain 1 to 20 servers")
    payload = {"schema": SCHEMA, "version": 1, "kind": "server", "name": str(name), "servers": safe, "order": list(range(len(safe)))}
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    if len(raw.encode("utf-8")) > 8192:
        raise ValueError("bundle is too large")
    return raw


def import_bundle(raw):
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("destination bundle must be an object")
    if payload.get("schema") != SCHEMA or payload.get("version") != 1 or payload.get("kind") != "server":
        raise ValueError("unsupported destination bundle")
    servers = payload.get("servers")
    if not isinstance(servers, list) or not 1 <= len(servers) <= 20:
        raise ValueError("invalid destination servers")
    clean = []
    for server in servers:
        if not isinstance(server, dict):
            raise ValueError("invalid destination server")
        host = str(server.get("host", "")).strip()
        try:
            port = int(server.get("port"))
        except (TypeError, ValueError):
            raise ValueError("invalid destination endpoint") from None
        if isinstance(server.get("port"), bool) or not host or any(char in host for char in "\r\n\x00\\") or not 1 <= port <= 65535:
            raise ValueError("invalid destination endpoint")
        clean.append({"name": str(server.get("name") or host), "host": host, "port": port})
    return {"schema": SCHEMA, "version": 1, "kind": "server", "name": str(payload.get("name") or "Imported destination"), "servers": clean, "order": list(range(len(clean)))}


def encode_link(raw):
    return "scpsl-autojoin://import?data=" + base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_link(link):
    parsed = urlparse(str(link).strip())
    if parsed.scheme.lower() != "scpsl-autojoin" or parsed.netloc.lower() != "import":
        raise ValueError("unsupported destination link")
    values = parse_qs(parsed.query, keep_blank_values=False).get("data", [])
    if len(values) != 1 or len(values[0]) > 12000:
        raise ValueError("invalid destination link payload")
    try:
        raw = base64.urlsafe_b64decode(values[0] + "=" * (-len(values[0]) % 4)).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid destination link encoding") from exc
    return import_bundle(raw)

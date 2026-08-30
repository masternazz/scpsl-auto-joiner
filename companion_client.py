"""Read-only client for the optional owned-server LabAPI companion."""
import json
import urllib.request
from urllib.parse import urlparse


def validate_status(payload):
    if not isinstance(payload, dict) or payload.get("protocol_version") != 1:
        raise ValueError("unsupported companion response")
    required = ("server", "round", "capacity", "player")
    if any(key not in payload or not isinstance(payload[key], dict) for key in required):
        raise ValueError("incomplete companion response")
    capacity = payload["capacity"]
    if not isinstance(capacity.get("players"), int) or not isinstance(capacity.get("max_players"), int):
        raise ValueError("invalid companion capacity")
    return payload


class CompanionClient:
    def __init__(self, url, token, opener=urllib.request.urlopen):
        parsed = urlparse(str(url).rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("companion URL must be an HTTP(S) URL")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("remote companion connections require HTTPS")
        self.url = str(url).rstrip("/")
        self.token = str(token)
        self.opener = opener

    def status(self, timeout=2):
        request = urllib.request.Request(self.url + "/v1/status", headers={"Authorization": "Bearer " + self.token, "Accept": "application/json"})
        with self.opener(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return validate_status(payload)

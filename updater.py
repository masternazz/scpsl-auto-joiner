"""Small, non-blocking GitHub release check for the desktop app."""
import json
import re
from urllib.parse import urlparse
import urllib.request

CURRENT_VERSION = "0.2.0"
RELEASES_API = "https://api.github.com/repos/masternazz/scpsl-auto-joiner/releases/latest"
RELEASES_PAGE = "https://github.com/masternazz/scpsl-auto-joiner/releases"


def _version(value):
    match = re.search(r"(?:^|/)v?(\d+)\.(\d+)\.(\d+)", str(value))
    return tuple(int(part) for part in match.groups()) if match else None


def _release_url(value):
    parsed = urlparse(str(value))
    if parsed.scheme == "https" and parsed.netloc == "github.com" and parsed.path.startswith("/masternazz/scpsl-auto-joiner/releases"):
        return str(value)
    return RELEASES_PAGE


def check_for_update(timeout=3):
    request = urllib.request.Request(
        RELEASES_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "SCP-SL-Auto-Joiner"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        release = json.load(response)
    latest = _version(release.get("tag_name", ""))
    current = _version(CURRENT_VERSION)
    if not latest or not current or latest <= current:
        return None
    return {
        "version": release["tag_name"].lstrip("v"),
        "url": _release_url(release.get("html_url", RELEASES_PAGE)),
    }

"""Small, non-blocking GitHub release check for the desktop app."""
import json
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
import urllib.request

CURRENT_VERSION = "0.3.24"
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
    assets = {asset.get("name"): asset for asset in release.get("assets", [])}
    version = release["tag_name"].lstrip("v")
    installer = assets.get(f"SCP-SL-Auto-Joiner-v{version}-win-x64-setup.exe")
    portable = assets.get(f"SCP-SL-Auto-Joiner-v{version}-win-x64-portable.zip")
    return {
        "version": version,
        "url": _release_url(release.get("html_url", RELEASES_PAGE)),
        "installer_url": installer.get("browser_download_url") if installer else None,
        "installer_digest": installer.get("digest") if installer else None,
        "portable_url": portable.get("browser_download_url") if portable else None,
        "portable_digest": portable.get("digest") if portable else None,
    }


def _download(url, digest, suffix):
    parsed = urlparse(str(url))
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise ValueError("Update download was not hosted on GitHub over HTTPS.")
    expected = str(digest or "")
    if not expected.startswith("sha256:"):
        raise ValueError("GitHub did not provide a SHA-256 checksum for the update.")
    path = os.path.join(tempfile.gettempdir(), f"scpsl-autojoin-update{suffix}")
    request = urllib.request.Request(url, headers={"User-Agent": "SCP-SL-Auto-Joiner"})
    digest_hash = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=30) as response, open(path, "wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            digest_hash.update(chunk)
            output.write(chunk)
    if f"sha256:{digest_hash.hexdigest()}" != expected.lower():
        os.remove(path)
        raise ValueError("The downloaded update failed its SHA-256 checksum.")
    return path


def _installed_mode():
    return os.path.exists(os.path.join(os.path.dirname(sys.executable), ".installed"))


def install_update(release):
    if _installed_mode():
        installer = _download(release["installer_url"], release["installer_digest"], ".exe")
        subprocess.Popen([installer, "/VERYSILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"])
        return
    helper = os.path.join(os.path.dirname(sys.executable), "SCP-SL-Auto-Joiner-Updater.exe")
    if not os.path.exists(helper):
        raise FileNotFoundError("The portable updater helper is missing from this folder.")
    archive = _download(release["portable_url"], release["portable_digest"], ".zip")
    subprocess.Popen([
        helper,
        "--pid", str(os.getpid()),
        "--archive", archive,
        "--target", os.path.dirname(sys.executable),
        "--executable", sys.executable,
    ], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

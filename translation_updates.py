"""User-initiated translation update metadata helpers."""
import urllib.request
import json
from urllib.parse import urlparse


def github_revision(owner, repo, ref="HEAD", opener=urllib.request.urlopen):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{ref}"
    with opener(url, timeout=10) as response:
        import json
        data = json.loads(response.read().decode("utf-8"))
    return data.get("sha")


def source_details(value):
    """Return normalized update metadata for repository/release URLs."""
    parsed = urlparse(str(value))
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        return {"kind": "local", "owner": None, "repo": None, "tag": None}
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 5 and parts[2].lower() == "releases" and parts[3].lower() == "tag":
        return {"kind": "github_release", "owner": parts[0], "repo": parts[1].removesuffix(".git"), "tag": "/".join(parts[4:])}
    if len(parts) >= 2:
        return {"kind": "github", "owner": parts[0], "repo": parts[1].removesuffix(".git"), "tag": None}
    return {"kind": "local", "owner": None, "repo": None, "tag": None}


def github_release(owner, repo, tag=None, opener=urllib.request.urlopen):
    endpoint = f"https://api.github.com/repos/{owner}/{repo}/releases/" + (f"tags/{tag}" if tag else "latest")
    request = urllib.request.Request(endpoint, headers={"User-Agent": "SCP-SL-Auto-Joiner", "Accept": "application/vnd.github+json"})
    with opener(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("GitHub returned an invalid release response")
    assets = [item for item in payload.get("assets", []) if isinstance(item, dict) and str(item.get("browser_download_url", "")).lower().endswith(".zip")]
    return {"tag": payload.get("tag_name"), "published_at": payload.get("published_at"), "asset_url": assets[0].get("browser_download_url") if assets else None, "zipball_url": payload.get("zipball_url")}


def source_from_url(value):
    details = source_details(value)
    return details["kind"], details["owner"], details["repo"]

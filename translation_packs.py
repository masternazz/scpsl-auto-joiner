"""Import and manage SCP:SL translation packs without executing their contents."""
import json
import os
import re
import shutil
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
import zipfile


class PackError(ValueError):
    pass


def _quarantine(path):
    backup = path + ".corrupt"
    index = 1
    while os.path.exists(backup):
        backup = f"{path}.corrupt.{index}"
        index += 1
    os.replace(path, backup)
    return backup


class PackManager:
    def __init__(self, data_dir, translations_dir):
        self.data_dir = os.path.abspath(os.fspath(data_dir))
        self.translations_dir = os.path.abspath(os.fspath(translations_dir))
        self.store_path = os.path.join(self.data_dir, "translation-packs.json")
        self.backup_dir = os.path.join(self.data_dir, "translation-backups")

    def folder_path(self, folder):
        """Resolve a managed folder without allowing traversal outside Translations."""
        root = os.path.abspath(self.translations_dir)
        candidate = os.path.abspath(os.path.join(root, os.fspath(folder)))
        if os.path.commonpath((root, candidate)) != root or candidate == root:
            raise PackError("pack folder resolves outside the Translations directory")
        return candidate

    def load(self):
        if not os.path.isfile(self.store_path):
            return {"version": 1, "packs": [], "active_pack": None}
        try:
            with open(self.store_path, encoding="utf-8") as stream:
                data = json.load(stream)
            if not isinstance(data, dict):
                raise ValueError("pack storage must be an object")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
            _quarantine(self.store_path)
            data = {"version": 1, "packs": [], "active_pack": None}
            self._save(data)
        except OSError as exc:
            raise PackError(f"Could not read pack storage: {exc}") from exc
        return {"version": 1, "packs": list(data.get("packs", [])), "active_pack": data.get("active_pack")}

    def _save(self, data):
        os.makedirs(self.data_dir, exist_ok=True)
        temporary = self.store_path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
        os.replace(temporary, self.store_path)

    @staticmethod
    def _manifest(root):
        candidates = [root]
        candidates.extend(path for path in os.scandir(root) if path.is_dir())
        for candidate in candidates:
            manifest_path = os.path.join(candidate.path if hasattr(candidate, "path") else candidate, "manifest.json")
            if not os.path.isfile(manifest_path):
                continue
            try:
                with open(manifest_path, encoding="utf-8-sig") as stream:
                    manifest = json.load(stream)
            except (OSError, ValueError) as exc:
                raise PackError(f"Malformed manifest.json: {exc}") from exc
            name = manifest.get("Name")
            authors = manifest.get("Authors", [])
            if not isinstance(name, str) or not name.strip():
                raise PackError("manifest.json has no pack name")
            if not isinstance(authors, list):
                authors = [str(authors)]
            txt_files = [path for path in os.listdir(candidate.path if hasattr(candidate, "path") else candidate) if path.lower().endswith(".txt")]
            if not txt_files:
                raise PackError("pack contains no translation files")
            return candidate.path if hasattr(candidate, "path") else candidate, manifest, txt_files
        raise PackError("could not find manifest.json")

    @staticmethod
    def _folder_name(name):
        value = re.sub(r"[^A-Za-z0-9._ -]+", "", name).strip(" .")
        return value[:80] or "Custom-Translation"

    def import_path(self, source, source_url=""):
        source = os.path.abspath(os.fspath(source))
        if not os.path.isdir(source) and not zipfile.is_zipfile(source):
            raise PackError("choose a translation folder or ZIP file")
        staging = tempfile.mkdtemp(prefix="translation-pack-")
        try:
            if os.path.isdir(source):
                root = os.path.join(staging, os.path.basename(source.rstrip(os.sep)))
                shutil.copytree(source, root)
            else:
                root = staging
                with zipfile.ZipFile(source) as archive:
                    for member in archive.infolist():
                        target = os.path.abspath(os.path.join(staging, member.filename))
                        if os.path.commonpath((staging, target)) != staging:
                            raise PackError("ZIP contains an invalid path")
                        archive.extract(member, staging)
            pack_root, manifest, _ = self._manifest(root)
            name = manifest["Name"].strip()
            data = self.load()
            folder = self._folder_name(os.path.basename(pack_root))
            old = next((pack for pack in data["packs"] if pack.get("name") == name or pack.get("folder") == folder), None)
            if old:
                folder = old["folder"]
            elif os.path.exists(os.path.join(self.translations_dir, folder)):
                base = folder
                index = 1
                while os.path.exists(os.path.join(self.translations_dir, folder)):
                    folder = f"{base}-custom" if index == 1 else f"{base}-custom-{index}"
                    index += 1
            target = self.folder_path(folder)
            backup = None
            if os.path.isdir(target):
                os.makedirs(self.backup_dir, exist_ok=True)
                backup = os.path.join(self.backup_dir, f"{folder}-{uuid.uuid4().hex[:8]}")
                shutil.move(target, backup)
            os.makedirs(self.translations_dir, exist_ok=True)
            shutil.copytree(pack_root, target)
            record = {
                "id": old["id"] if old else uuid.uuid4().hex,
                "name": name,
                "authors": [str(author) for author in manifest.get("Authors", [])],
                "folder": folder,
                "source": source_url or (old.get("source", "") if old else ""),
                "backup": backup,
                "source_type": self._source_type(source_url or (old.get("source", "") if old else "")),
                "revision": old.get("revision") if old else None,
                "last_checked": None,
            }
            data["packs"] = [pack for pack in data["packs"] if pack.get("id") != record["id"]]
            data["packs"].append(record)
            self._save(data)
            return record
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def update_from_path(self, pack_id, source, source_url=""):
        """Replace an installed pack from a validated local staging source.

        The caller is responsible for obtaining user confirmation.  Importing
        through the normal path creates a dated backup before replacement and
        retains the installed pack id, so an update cannot silently create a
        second copy of the same pack.
        """
        data = self.load()
        current = next((item for item in data["packs"] if item.get("id") == str(pack_id)), None)
        if not current:
            raise PackError("pack is not installed")
        record = self.import_path(source, source_url or current.get("source", ""))
        if record["id"] != current["id"]:
            raise PackError("updated pack identity did not match the installed pack")
        record["source_type"] = current.get("source_type") or ("github" if "github.com/" in record["source"] else "local")
        record["last_checked"] = time.time()
        data = self.load()
        for item in data["packs"]:
            if item.get("id") == record["id"]:
                item.update(record)
        self._save(data)
        return {"ok": True, "pack": record}

    @staticmethod
    def _source_type(source_url):
        value = str(source_url or "").lower()
        if "github.com/" not in value:
            return "local"
        return "github_release" if "/releases/" in value else "github"

    def activate(self, pack_id):
        data = self.load()
        if not any(pack.get("id") == pack_id for pack in data["packs"]):
            raise PackError("pack is not installed")
        data["active_pack"] = pack_id
        self._save(data)
        return data

    def deactivate(self):
        data = self.load(); data["active_pack"] = None; self._save(data); return data

    def restore(self, pack_id):
        data = self.load()
        pack = next((item for item in data["packs"] if item.get("id") == pack_id), None)
        if not pack or not pack.get("backup") or not os.path.isdir(pack["backup"]):
            return False
        target = self.folder_path(pack["folder"])
        if os.path.isdir(target):
            shutil.rmtree(target)
        shutil.move(pack["backup"], target)
        pack["backup"] = None
        self._save(data)
        return True

    def delete(self, pack_id):
        data = self.load(); pack = next((item for item in data["packs"] if item.get("id") == pack_id), None)
        if not pack:
            return False
        target = self.folder_path(pack["folder"])
        if os.path.isdir(target): shutil.rmtree(target)
        data["packs"] = [item for item in data["packs"] if item.get("id") != pack_id]
        if data.get("active_pack") == pack_id: data["active_pack"] = None
        self._save(data); return True

    def _read_url(self, url):
        request = urllib.request.Request(url, headers={"User-Agent": "SCP-SL-Auto-Joiner"})
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read()

    def search_github(self, query):
        url = "https://api.github.com/search/repositories?per_page=20&q=" + urllib.parse.quote(query + " SCP SL translation")
        payload = json.loads(self._read_url(url).decode("utf-8"))
        return [{key: item.get(key) for key in ("full_name", "html_url", "description", "updated_at", "stargazers_count")} for item in payload.get("items", [])]

    @staticmethod
    def resolve_link(url):
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc.lower() == "github.com":
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2:
                return f"https://api.github.com/repos/{parts[0]}/{parts[1]}/zipball"
        if parsed.path.lower().endswith(".zip"):
            return url
        raise PackError("link must be a GitHub repository or ZIP download")

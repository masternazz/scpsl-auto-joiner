"""Named calibration profiles with conservative health checks."""
import json
import os
import tempfile
import uuid


def executable_fingerprint(path):
    """Stable local fingerprint used to detect game updates, not identification."""
    if not path or not os.path.isfile(path):
        return None
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return {"name": os.path.basename(path), "size": int(stat.st_size), "modified_ns": int(stat.st_mtime_ns)}


class CalibrationProfiles:
    def __init__(self, path):
        self.path = str(path)

    def load(self):
        if not os.path.isfile(self.path):
            return {"version": 1, "profiles": [], "active": None}
        try:
            with open(self.path, encoding="utf-8") as stream:
                data = json.load(stream)
            if not isinstance(data, dict) or not isinstance(data.get("profiles", []), list):
                raise ValueError("calibration storage must be an object with profiles")
            return {"version": 1, "profiles": list(data.get("profiles", [])), "active": data.get("active")}
        except (OSError, ValueError, TypeError):
            backup = self.path + ".corrupt"
            index = 1
            while os.path.exists(backup):
                backup = f"{self.path}.corrupt.{index}"; index += 1
            try: os.replace(self.path, backup)
            except OSError: pass
            return {"version": 1, "profiles": [], "active": None}

    def save(self, data):
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".calibrations-", suffix=".tmp", dir=directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

    def add(self, name, points, metadata):
        data = self.load()
        profile = {"id": str(uuid.uuid4()), "name": str(name).strip() or "Calibration", "points": points, "metadata": metadata}
        data["profiles"].append(profile); data["active"] = profile["id"]; self.save(data)
        return profile

    def rename(self, profile_id, name):
        data = self.load()
        for profile in data["profiles"]:
            if profile.get("id") == str(profile_id):
                profile["name"] = str(name).strip() or "Calibration"
                self.save(data)
                return profile
        raise KeyError(profile_id)

    def duplicate(self, profile_id, name):
        data = self.load()
        source = next((item for item in data["profiles"] if item.get("id") == str(profile_id)), None)
        if not source:
            raise KeyError(profile_id)
        return self.add(name, source.get("points", {}), dict(source.get("metadata") or {}))

    def health(self, profile, current_metadata):
        if not profile:
            return "missing"
        expected = profile.get("metadata") or {}
        keys = ("game_version", "game_fingerprint", "client_size", "dpi", "window_mode", "monitor")
        return "healthy" if all(not expected.get(k) or expected.get(k) == current_metadata.get(k) for k in keys) else "stale"

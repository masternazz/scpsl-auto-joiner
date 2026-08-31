"""Optional Discord Rich Presence IPC adapter."""
import json
import os
import struct
import hashlib
import threading


class DiscordIPC:
    @staticmethod
    def frame(opcode, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return struct.pack("<II", int(opcode), len(body)) + body

    @staticmethod
    def pipe_path(index=0):
        return rf"\\.\pipe\discord-ipc-{int(index)}"

    def __init__(self, client_id=None, opener=open, on_join=None):
        self.client_id = client_id or os.environ.get("SCP_SL_DISCORD_CLIENT_ID")
        self.opener = opener
        self.on_join = on_join
        self.connection = None
        self._reader = None
        self._closed = threading.Event()
        self._write_lock = threading.Lock()

    def connect(self):
        if not self.client_id or os.name != "nt":
            return False
        for index in range(10):
            try:
                self.connection = self.opener(self.pipe_path(index), "r+b", buffering=0)
                self.connection.write(self.frame(0, {"v": 1, "client_id": self.client_id}))
                self._closed.clear()
                self._reader = threading.Thread(target=self._read_events, name="discord-ipc", daemon=True)
                self._reader.start()
                return True
            except (OSError, ValueError):
                self.connection = None
        return False

    def set_activity(self, activity):
        if not self.connection and not self.connect():
            return False
        try:
            with self._write_lock:
                self.connection.write(self.frame(1, {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid(), "activity": activity}, "nonce": "scpsl-autojoin"}))
            return True
        except OSError:
            self.close()
            return False

    def close(self):
        self._closed.set()
        if self.connection:
            try:
                self.connection.close()
            except OSError:
                pass
        self.connection = None

    def _read_exact(self, size):
        chunks = []
        left = size
        while left and not self._closed.is_set():
            chunk = self.connection.read(left)
            if not chunk:
                return None
            chunks.append(chunk)
            left -= len(chunk)
        return b"".join(chunks) if left == 0 else None

    def _read_events(self):
        """Receive local Discord dispatches without blocking the desktop UI."""
        try:
            while self.connection and not self._closed.is_set():
                header = self._read_exact(8)
                if not header:
                    break
                _, length = struct.unpack("<II", header)
                if length > 65536:
                    break
                body = self._read_exact(length)
                if not body:
                    break
                message = json.loads(body.decode("utf-8"))
                data = message.get("data") or {}
                if message.get("cmd") == "DISPATCH" and data.get("evt") == "ACTIVITY_JOIN":
                    secret = (data.get("data") or {}).get("secret")
                    if secret and self.on_join:
                        self.on_join(str(secret))
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            pass
        finally:
            if threading.current_thread() is self._reader:
                self.connection = None


class DiscordPresence:
    def __init__(self, client_id=None, ipc=None, on_join=None):
        self.enabled = False
        self.current = None
        self.ipc = ipc or DiscordIPC(client_id, on_join=on_join)
        self.connected = False
        self.last_error = None

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled:
            self.clear()
        return {"ok": True, "enabled": self.enabled}

    def update(self, state, server_name=None, players=None, started_at=None, share=False,
               share_server=None, join_secret=None, max_players=None):
        if not self.enabled:
            return {"ok": True, "enabled": False, "connected": False}
        share_server = bool(share if share_server is None else share_server)
        labels = {
            "idle": "Ready to join", "watching": "Watching for a slot",
            "slot_candidate": "Slot found", "connecting": "Connecting",
            "joined": "Playing SCP:SL", "paused": "Watch paused",
        }
        self.current = {
            "state": str(state),
            "server_name": str(server_name or "") if share_server else "",
            "players": players if share else None,
            "started_at": started_at,
            "share_server": share_server,
            "join_available": bool(join_secret and share_server),
        }
        activity = {
            "details": labels.get(str(state), str(state).replace("_", " ").title()),
            "state": self.current["server_name"] or "SCP:SL Auto-Joiner",
            # Upload the app's S mark to the Discord Developer Portal with
            # this key. Discord ignores an unavailable asset without exposing
            # a local image path or endpoint.
            "assets": {"large_image": "scpsl-autojoin-s", "large_text": "SCP:SL Auto-Joiner"},
        }
        if self.current["players"] is not None:
            activity["state"] += f" · {self.current['players']} players"
        if started_at:
            activity["timestamps"] = {"start": int(started_at)}
        if join_secret and share_server:
            activity["secrets"] = {"join": str(join_secret)}
            activity["party"] = {"id": hashlib.sha256(str(join_secret).encode()).hexdigest()[:24]}
            if max_players is not None and players is not None:
                activity["party"]["size"] = [max(0, int(players)), max(1, int(max_players))]
        self.connected = bool(self.ipc.set_activity(activity))
        self.last_error = None if self.connected else "Discord is unavailable. The app will keep working normally."
        return {"ok": self.connected, "enabled": True, "connected": self.connected,
                "presence": dict(self.current), "error": self.last_error}

    def clear(self):
        self.current = None
        self.connected = False
        self.last_error = None
        self.ipc.close()
        return {"ok": True}

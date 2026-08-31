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
        self._connector = None
        self._writer = None
        self._pending_activity = None
        self._activity_ready = threading.Event()
        self._closed = threading.Event()
        self._write_lock = threading.Lock()

    def connect(self):
        if not self.client_id or os.name != "nt":
            return False
        if self.connection:
            return True
        if self._connector and self._connector.is_alive():
            return False
        self._closed.clear()
        self._connector = threading.Thread(target=self._connect_in_background, name="discord-ipc-connect", daemon=True)
        self._connector.start()
        return False

    def _connect_in_background(self):
        """Open Discord IPC away from the desktop/UI thread.

        Windows named-pipe opens can wait when Discord is starting or has an
        unavailable pipe instance.  The application must remain responsive in
        that case, so the first presence update is retained and sent only when
        the pipe becomes available.
        """
        for index in range(10):
            if self._closed.is_set():
                return
            try:
                connection = self.opener(self.pipe_path(index), "r+b", buffering=0)
                connection.write(self.frame(0, {"v": 1, "client_id": self.client_id}))
                self.connection = connection
                self._reader = threading.Thread(target=self._read_events, name="discord-ipc", daemon=True)
                self._reader.start()
                self._start_writer()
                return
            except (OSError, ValueError):
                self.connection = None

    def _write_activity(self, activity):
        try:
            with self._write_lock:
                connection = self.connection
                if not connection:
                    return False
                connection.write(self.frame(1, {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid(), "activity": activity}, "nonce": "scpsl-autojoin"}))
            return True
        except (AttributeError, OSError):
            self.close()
            return False

    def _start_writer(self):
        if not self.connection or (self._writer and self._writer.is_alive()):
            return
        self._writer = threading.Thread(target=self._write_pending_activities, name="discord-ipc-write", daemon=True)
        self._writer.start()

    def _write_pending_activities(self):
        """Send the most recent activity without ever blocking a caller."""
        while self.connection and not self._closed.is_set():
            self._activity_ready.wait()
            self._activity_ready.clear()
            activity = self._pending_activity
            if activity is None:
                continue
            if not self._write_activity(activity):
                return

    def set_activity(self, activity):
        self._pending_activity = activity
        self._activity_ready.set()
        if not self.connection:
            self.connect()
            return False
        self._start_writer()
        return True

    def close(self):
        self._closed.set()
        self._pending_activity = None
        self._activity_ready.set()
        connection = self.connection
        self.connection = None
        if connection:
            # Closing a Windows named pipe may wait behind an in-flight write.
            # Detach first, then let a daemon clean it up so stopping presence
            # cannot delay the app's UI, shutdown, or next configuration.
            threading.Thread(target=self._close_connection, args=(connection,), name="discord-ipc-close", daemon=True).start()

    @staticmethod
    def _close_connection(connection):
        try:
            connection.close()
        except OSError:
            pass

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

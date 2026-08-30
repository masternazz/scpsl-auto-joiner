"""Optional Discord Rich Presence IPC adapter."""
import json
import os
import struct


class DiscordIPC:
    @staticmethod
    def frame(opcode, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return struct.pack("<II", int(opcode), len(body)) + body

    @staticmethod
    def pipe_path(index=0):
        return rf"\\.\pipe\discord-ipc-{int(index)}"

    def __init__(self, client_id=None, opener=open):
        self.client_id = client_id or os.environ.get("SCP_SL_DISCORD_CLIENT_ID")
        self.opener = opener
        self.connection = None

    def connect(self):
        if not self.client_id or os.name != "nt":
            return False
        for index in range(10):
            try:
                self.connection = self.opener(self.pipe_path(index), "r+b", buffering=0)
                self.connection.write(self.frame(0, {"v": 1, "client_id": self.client_id}))
                return True
            except (OSError, ValueError):
                self.connection = None
        return False

    def set_activity(self, activity):
        if not self.connection and not self.connect():
            return False
        try:
            self.connection.write(self.frame(1, {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid(), "activity": activity}, "nonce": "scpsl-autojoin"}))
            return True
        except OSError:
            self.close()
            return False

    def close(self):
        if self.connection:
            try:
                self.connection.close()
            except OSError:
                pass
        self.connection = None


class DiscordPresence:
    def __init__(self, client_id=None, ipc=None):
        self.enabled = False
        self.current = None
        self.ipc = ipc or DiscordIPC(client_id)

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not self.enabled:
            self.clear()
        return {"ok": True, "enabled": self.enabled}

    def update(self, state, server_name=None, players=None, started_at=None, share=False):
        if not self.enabled:
            return {"ok": True, "enabled": False}
        self.current = {"state": str(state), "server_name": str(server_name or ""), "players": players if share else None, "started_at": started_at}
        activity = {"details": self.current["state"], "state": self.current["server_name"] or "SCP:SL Auto-Joiner"}
        if self.current["players"] is not None:
            activity["state"] += f" · {self.current['players']} players"
        self.ipc.set_activity(activity)
        return {"ok": True, "enabled": True, "presence": dict(self.current)}

    def clear(self):
        self.current = None
        self.ipc.close()
        return {"ok": True}

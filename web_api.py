"""pywebview-facing application API.

All methods return JSON-serializable dictionaries. The browser never receives
Python objects or executable callback strings.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import webbrowser
import zipfile
from concurrent.futures import ThreadPoolExecutor

import config
import audio_control
import joiner
import logwatch
import resolver
import server_store
import winput
from history import ServerHistory
from watch_mode import QueryFailureTracker, SlotConfirmation, eligible, select_candidate
from destinations import decode_link, encode_link, export_bundle, import_bundle
from calibration_profiles import CalibrationProfiles, executable_fingerprint
from discord_presence import DiscordPresence
from app_paths import app_dir
from theme_manager import ThemeManager
from translation_packs import PackError, PackManager
from monitoring import BackgroundMonitor
import secret_store
import notify
from version import APP_VERSION


def _translation_dir():
    executable = joiner.find_game_executable()
    if executable:
        return os.path.abspath(os.path.join(os.path.dirname(executable), "Translations"))
    return os.path.abspath(os.path.join(app_dir(), "Translations"))


class WebApi:
    def __init__(self, data_dir=None, translations_dir=None):
        self.data_dir = os.path.abspath(os.fspath(data_dir or app_dir()))
        self.config_path = os.path.join(self.data_dir, "config.json")
        self.store_path = os.path.join(self.data_dir, "servers.json")
        self.translations_dir = os.path.abspath(os.fspath(translations_dir or _translation_dir()))
        self.pack_manager = PackManager(self.data_dir, self.translations_dir)
        self.theme_manager = ThemeManager(self.data_dir)
        self.history = ServerHistory(os.path.join(self.data_dir, "history.sqlite3"))
        self.calibration_profiles = CalibrationProfiles(os.path.join(self.data_dir, "calibrations.json"))
        self._migrate_legacy_calibration()
        # Restore only the local preference. Discord IPC remains lazy and is
        # still harmless when Discord is not installed or running.
        discord_config = self._load_config()
        self.discord = DiscordPresence(
            client_id=discord_config.get("discord_application_id") or None,
            on_join=self._handle_discord_join,
        )
        self.discord.set_enabled(bool(discord_config.get("discord_enabled", False)))
        self._sink = None
        self._join_thread = None
        self._join_stop = threading.Event()
        self._remember_thread = None
        self._remember_stop = threading.Event()
        self._watch_thread = None
        self._watch_stop = threading.Event()
        self._watch_pause = threading.Event()
        self._watch_alert = threading.Event()
        self._pending_watch_alert = None
        self._monitor = None
        self._manual_audio_controller = None
        self._last_join_result = None
        self._watch_state = {"state": "idle", "server_id": None, "attempt": 0, "last_status": None}
        self._decisions = []

    _DECISION_TEXT = {
        "full": ("Server full", "Keep watching or retry after capacity changes."),
        "single_slot": ("One slot detected", "Waiting for the required second query sample."),
        "query_failure": ("Server query failed", "Keep watching, refresh manually, or use Immediate Auto-Join."),
        "filter_mismatch": ("Group filter excluded this server", "Adjust the group population or fill limits."),
        "gui_recovery": ("Game UI needs recovery", "Bring SCP:SL to its menu, then choose Retry safely."),
        "timeout": ("Connection timed out", "Check SCP:SL and use Diagnostics before retrying."),
        "stale_calibration": ("Calibration may be stale", "Select or recalibrate the matching display profile."),
        "user_stop": ("Stopped by you", "No further input or queries will be sent."),
        "slot_confirmed": ("Slot confirmed", "Starting the selected connection flow."),
        "joined": ("Joined", "The connection was confirmed by SCP:SL."),
    }

    def _record_decision(self, code, evidence=None):
        title, next_action = self._DECISION_TEXT.get(str(code), ("Connection state changed", "Review Live Activity and Diagnostics."))
        item = {"code": str(code), "title": title, "next_action": next_action,
                "evidence": dict(evidence or {}), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self._decisions = (self._decisions + [item])[-100:]
        self.emit("join_decision", item)
        return item

    def get_join_explanations(self):
        return {"ok": True, "items": list(reversed(self._decisions))}

    def get_recovery_actions(self):
        latest = self._decisions[-1] if self._decisions else None
        code = latest.get("code") if latest else ""
        actions = [{"id": "diagnostics", "label": "Open Diagnostics", "safe": True}]
        if code in {"full", "query_failure", "single_slot"}:
            actions.insert(0, {"id": "watch", "label": "Keep watching", "safe": True})
        if code in {"gui_recovery", "timeout", "stale_calibration"}:
            actions.append({"id": "retry", "label": "Retry safely", "safe": False})
        return {"ok": True, "decision": latest, "actions": actions}

    def recover_connection(self, target, target_type="server", action="diagnostics"):
        if action == "diagnostics":
            return {"ok": True, "next": "diagnostics"}
        if action == "watch":
            return self.start_watch(target, target_type)
        if action == "retry":
            # Explicit UI request only; recovery never injects input by itself.
            return self.start_join(target, target_type, "immediate")
        return {"ok": False, "error": "unsupported recovery action"}

    def _migrate_legacy_calibration(self):
        """Preserve pre-profile calibration as an explicit named profile."""
        data = self.calibration_profiles.load()
        if data.get("profiles"):
            return
        cfg = self._load_config()
        points = cfg.get("click_points") or {}
        if not all(tuple(points.get(name, (0, 0))) != (0, 0) for name in config.REQUIRED_CLICK_POINTS):
            return
        metadata = dict(cfg.get("calibration_metadata") or {})
        metadata.setdefault("migration", "Imported calibration")
        self.calibration_profiles.add("Imported calibration", points, metadata)

    def _load_config(self):
        return config.load_config(self.config_path)

    def _save_config(self, values):
        config.save_config(values, self.config_path)

    def _load_store(self):
        return server_store.load_store(self.store_path)

    def _storage_state(self):
        """Describe local data without changing it.

        Older releases used a flat ``{name: {ip, port}}`` server file.  The
        store loader already upgrades that format safely; the Web UI needs a
        visible indication that it found that existing data rather than
        appearing to start from an empty installation.
        """
        migrated = False
        try:
            with open(self.store_path, encoding="utf-8") as stream:
                raw_store = json.load(stream)
            migrated = isinstance(raw_store, dict) and "servers" not in raw_store
        except (OSError, ValueError, TypeError):
            pass
        return {
            "migrated": migrated,
            "paths": {
                "root": self.data_dir,
                "servers": self.store_path,
                "config": self.config_path,
                "translations": self.translations_dir,
            },
        }

    def set_event_sink(self, sink):
        self._sink = sink

    def emit(self, event, data=None):
        if self._sink:
            self._sink({"event": event, "data": data or {}})

    def _handle_discord_join(self, secret):
        """Turn a Discord Join request into a normal, review-first import.

        A join secret is never trusted as a command to save or join a server.
        It must be one of our small destination links and the frontend still
        requires the user to preview and explicitly import it.
        """
        try:
            decode_link(secret)
        except (TypeError, ValueError):
            self.emit("toast_requested", {"message": "Ignored an invalid Discord destination request."})
            return False
        self.emit("destination_import_requested", {"raw": str(secret), "source": "discord"})
        return True

    @staticmethod
    def _discord_join_secret(server):
        """Create an opaque, single-server destination link for Discord IPC."""
        try:
            raw = export_bundle(str(server["name"]), [server])
            return encode_link(raw)
        except (KeyError, TypeError, ValueError):
            return None

    def _state(self):
        storage = self._storage_state()
        cfg = self._load_config()
        store = self._load_store()
        return {
            "servers": store["servers"], "groups": store["groups"],
            "settings": cfg, "calibration": self.get_calibration_state()["calibration"],
            "calibration_profiles": self.get_calibration_profiles(),
            "theme": self.theme_manager.load(), "packs": self.pack_manager.load(),
            "join": self.get_join_status()["join"], "decisions": self.get_join_explanations()["items"],
            "storage": storage,
        }

    def get_app_state(self):
        return {"ok": True, "version": APP_VERSION, **self._state()}

    def get_servers(self, query=""):
        return {"ok": True, "servers": server_store.search_servers(query, self.store_path)}

    def save_server_profile(self, server_id, profile):
        store = self._load_store()
        for server in store["servers"]:
            if server["id"] == str(server_id):
                server.update({"monitoring": dict(profile.get("monitoring") or server.get("monitoring") or {}), "join_profile": dict(profile.get("join_profile") or server.get("join_profile") or {}), "share_presence": bool(profile.get("share_presence", server.get("share_presence", False))), "companion_url": profile.get("companion_url", server.get("companion_url")), "tags": sorted({str(tag).strip() for tag in profile.get("tags", server.get("tags", [])) if str(tag).strip()}, key=str.casefold), "notes": str(profile.get("notes", server.get("notes", "")) or "").strip()[:4000], "collections": sorted({str(item).strip() for item in profile.get("collections", server.get("collections", [])) if str(item).strip()}, key=str.casefold), "notification_profile": dict(profile.get("notification_profile") or server.get("notification_profile") or {})})
                if "companion_token" in profile:
                    token = str(profile.get("companion_token") or "")
                    server["companion_token"] = secret_store.protect(token) if token else None
                store["collections"] = sorted(
                    {str(name).strip() for name in store.get("collections", []) + server["collections"] if str(name).strip()},
                    key=str.casefold,
                )
                server_store.save_store(store, self.store_path)
                return {"ok": True, "server": server}
        return {"ok": False, "error": "saved server was not found"}

    def save_collection(self, name):
        name = str(name or "").strip()
        if not name or len(name) > 80:
            return {"ok": False, "error": "collection name must be 1 to 80 characters"}
        store = self._load_store()
        store["collections"] = sorted(set(store.get("collections", [])) | {name}, key=str.casefold)
        server_store.save_store(store, self.store_path)
        return {"ok": True, "collections": store["collections"]}

    def get_collections(self):
        return {"ok": True, "collections": self._load_store().get("collections", [])}

    def register_destination_protocol(self):
        """Register the per-user URI handler for a portable Windows build.

        Installed copies are registered by Inno Setup.  This explicit action
        lets a portable user opt in without writing machine-wide registry keys.
        """
        if os.name != "nt" or not getattr(sys, "frozen", False):
            return {"ok": False, "error": "Protocol registration is available from the packaged Windows app."}
        try:
            import winreg
            command = f'"{sys.executable}" "%1"'
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\scpsl-autojoin") as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "URL:SCP:SL Auto-Joiner Destination")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\scpsl-autojoin\shell\open\command") as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, command)
            return {"ok": True}
        except OSError as exc:
            return {"ok": False, "error": f"Could not register destination links: {exc}"}

    def save_server(self, name, ip, port):
        try:
            return {"ok": True, "server": server_store.upsert_server(str(name), str(ip), int(port), self.store_path)}
        except (TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def remember_server(self, name, ip, port):
        """Save an endpoint detected by the Player.log watcher."""
        return self.save_server(name, ip, port)

    def start_remember(self):
        """Watch the client log for the next connection and report its endpoint.

        The watcher is asynchronous so the WebView remains responsive while
        the user joins normally in SCP:SL.
        """
        if self._remember_thread and self._remember_thread.is_alive():
            return {"ok": False, "error": "already watching for a connection"}
        self._remember_stop.clear()
        self._remember_thread = threading.Thread(target=self._remember_worker, daemon=True)
        self._remember_thread.start()
        self.emit("status_changed", {"message": "Watching Player.log for your next SCP:SL connection..."})
        return {"ok": True}

    def _remember_worker(self):
        watcher = None
        try:
            watcher = logwatch.LogWatcher()
            match = watcher.wait_for_regex(
                logwatch.CONNECTING_IP_RE, 120, stop_event=self._remember_stop
            )
            if not match:
                if not self._remember_stop.is_set():
                    self.emit("status_changed", {"message": "Timed out waiting for a connection attempt."})
                return
            ip, port = match.group(1), int(match.group(2))
            name = resolver.query_server_name(ip, port) or ""
            self.emit("server_detected", {"ip": ip, "port": port, "name": name})
        except Exception as exc:
            self.emit("status_changed", {"message": f"Could not read the SCP:SL log: {exc}"})
        finally:
            if watcher:
                watcher.close()

    def stop_remember(self):
        self._remember_stop.set()
        return {"ok": True}

    def rename_server(self, server_id, name):
        try:
            store = self._load_store(); item = next(s for s in store["servers"] if s["id"] == server_id)
            return {"ok": True, "server": server_store.update_server(server_id, name, item["ip"], item["port"], self.store_path)}
        except (KeyError, TypeError, ValueError, StopIteration) as exc:
            return {"ok": False, "error": str(exc) or "saved server was not found"}

    def delete_server(self, server_id):
        return {"ok": True, "deleted": server_store.delete_server(str(server_id), self.store_path)}

    def refresh_server_status(self, server_id):
        try:
            store = self._load_store(); item = next(s for s in store["servers"] if s["id"] == server_id)
        except StopIteration:
            return {"ok": False, "error": "saved server was not found"}
        result = resolver.query_server(item["ip"], item["port"], path=self.store_path)
        return {"ok": True, "server": item, "status": result or {"available": False}}

    def get_groups(self):
        return {"ok": True, "groups": self._load_store()["groups"]}

    def save_group(self, name, server_ids, group_id=None):
        try:
            group = (server_store.update_group(group_id, list(server_ids), self.store_path, name=str(name))
                     if group_id else server_store.create_group(str(name), list(server_ids), self.store_path))
            return {"ok": True, "group": group}
        except (KeyError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def save_group_policy(self, group_id, policy):
        store = self._load_store()
        for group in store["groups"]:
            if group["id"] == str(group_id):
                candidate = dict(group.get("policy") or {})
                candidate.update(dict(policy or {}))
                try:
                    normalized = server_store._validate_group_record({**group, "policy": candidate}, {s["id"] for s in store["servers"]})
                except (TypeError, ValueError) as exc:
                    return {"ok": False, "error": str(exc)}
                candidate = normalized["policy"]
                group["policy"] = candidate; server_store.save_store(store, self.store_path)
                return {"ok": True, "group": group}
        return {"ok": False, "error": "retry group was not found"}

    def delete_group(self, group_id):
        return {"ok": True, "deleted": server_store.delete_group(str(group_id), self.store_path)}

    def start_join(self, target, target_type="server", start_mode="immediate"):
        if start_mode == "watch":
            return self.start_watch(target, target_type)
        if self._join_thread and self._join_thread.is_alive():
            return {"ok": False, "error": "auto-join is already running"}
        self._join_stop.clear()
        profile_data = self.get_calibration_profiles()
        active = next((p for p in profile_data.get("profiles", []) if p.get("id") == profile_data.get("active")), None)
        if active and active.get("health") == "stale":
            self._record_decision("stale_calibration", {"profile_id": active.get("id")})
            self.emit("status_changed", {"message": "Calibration profile is stale for the current game/display; recalibration is recommended."})
        if target_type == "server":
            self.update_discord_presence("connecting", str(target), started_at=time.time())
        runner = joiner.run_group if target_type == "group" else joiner.run
        runner_target = target
        if target_type == "server":
            server = next((item for item in self._load_store()["servers"] if item["id"] == str(target)), None)
            if server:
                runner_target = server["name"]
        self._join_thread = threading.Thread(target=self._run_join, args=(runner, runner_target), daemon=True)
        self._join_thread.start()
        return {"ok": True}

    def start_watch(self, target, target_type="server"):
        if self._watch_thread and self._watch_thread.is_alive():
            return {"ok": False, "error": "watch mode is already running"}
        self._watch_stop.clear(); self._watch_pause.clear(); self._watch_alert.clear(); self._pending_watch_alert = None
        store = self._load_store()
        selected = next((item for item in store["servers"] if item["id"] == str(target)), None) if target_type == "server" else next((item for item in store["groups"] if item["id"] == str(target)), None)
        self._watch_state = {"state": "querying", "server_id": str(target) if target_type == "server" else None, "server_name": selected.get("name") if selected else None, "attempt": 0, "last_status": None, "target_type": target_type, "started_at": time.time()}
        if target_type == "server":
            self.update_discord_presence("watching", str(target), started_at=self._watch_state["started_at"])
        self._watch_thread = threading.Thread(target=self._watch_worker, args=(str(target), target_type), daemon=True)
        self._watch_thread.start()
        self.emit("watch_status_changed", dict(self._watch_state))
        return {"ok": True, "watch": dict(self._watch_state)}

    def _watch_worker(self, target, target_type):
        try:
            store = self._load_store()
            candidates = ([s for s in store["servers"] if s["id"] == target] if target_type == "server" else [])
            if target_type == "group":
                group = next((g for g in store["groups"] if g["id"] == target), None)
                candidates = [s for s in store["servers"] if group and s["id"] in group["server_ids"]]
            group_policy = {}
            if target_type == "group":
                group_policy = next((g.get("policy") or {} for g in store["groups"] if g["id"] == target), {})
            confirmations = {s["id"]: SlotConfirmation(2) for s in candidates}
            query_failures = {s["id"]: QueryFailureTracker(3) for s in candidates}
            while not self._watch_stop.is_set() and candidates:
                if self._watch_pause.is_set():
                    self._watch_state["state"] = "paused"; self.emit("watch_status_changed", dict(self._watch_state)); time.sleep(.25); continue
                self._watch_state["state"] = "querying"
                statuses = []
                # Query group members concurrently, but cap fan-out so a
                # large saved group cannot flood the network or the server
                # query layer. Dict insertion order preserves manual order.
                with ThreadPoolExecutor(max_workers=min(5, len(candidates)), thread_name_prefix="watch-query") as executor:
                    futures = {server["id"]: executor.submit(self._query_server, server) for server in candidates}
                    for server in candidates:
                        if self._watch_stop.is_set(): break
                        try:
                            raw_status = futures[server["id"]].result()
                        except Exception:
                            raw_status = None
                        if query_failures[server["id"]].observe(raw_status) and not self._watch_state.get("fallback_available"):
                            self._record_decision("query_failure", {"server_id": server["id"], "failures": 3})
                            self._watch_state["fallback_available"] = True
                            self.emit("watch_fallback_available", {"server_id": server["id"], "message": "Server queries are failing. Normal Auto-Join is available as a fallback."})
                            self.emit("toast_requested", {"message": "Watch Mode is still monitoring; normal Auto-Join is available if needed."})
                        status = raw_status or {"available": False}
                        self._watch_state["last_status"] = status; self.history.record(server["id"], status.get("available", False), status.get("players"), status.get("max_players"), status.get("latency_ms"))
                        self.emit("server_sampled", {"server_id": server["id"], "status": status})
                        if target_type == "server":
                            self.update_discord_presence(
                                "slot_candidate" if status.get("available") else "watching",
                                server["id"], status.get("players"), status.get("max_players"),
                                self._watch_state.get("started_at"),
                            )
                        statuses.append({**status, "id": server["id"], "server": server})
                if target_type == "group":
                    chosen = select_candidate(statuses, group_policy)
                    if chosen and not confirmations[chosen["id"]].accepts(chosen):
                        self._record_decision("single_slot", {"server_id": chosen["id"]})
                        chosen = None
                else:
                    # A polling cycle contributes at most one confirmation
                    # sample.  Do not call accepts() again after selecting it.
                    chosen = next((s for s in statuses if eligible(s) and confirmations[s["id"]].accepts(s)), None)
                if chosen:
                    server = chosen["server"]
                    if server:
                        self._record_decision("slot_confirmed", {"server_id": server["id"]})
                        profile = server.get("notification_profile") or {}
                        cfg = self._load_config()
                        enabled = profile.get("enabled")
                        action_alert = bool(profile.get("actionable") or cfg.get("slot_alert_actions")) and enabled is not False and bool(cfg.get("notifications_enabled", True))
                        alert_sent = False
                        if enabled is not False and cfg.get("notifications_enabled", True):
                            alert_sent = notify.slot_available(server["name"], server["id"], chosen.get("players"), chosen.get("max_players"), bool((profile.get("sound") or cfg.get("notification_sound")) and not (profile.get("quiet") or cfg.get("quiet_notifications"))), action_alert)
                        if action_alert and alert_sent:
                            # An actionable notification is opt-in. Until the
                            # user chooses, Watch Mode only keeps checking and
                            # never sends game input on its own.
                            self._pending_watch_alert = {"server_id": server["id"], "action": None}
                            self._watch_alert.clear()
                            self._watch_state["state"] = "slot_candidate"
                            self.emit("watch_status_changed", dict(self._watch_state))
                            while not self._watch_stop.is_set() and not self._watch_alert.wait(.25):
                                pass
                            action = (self._pending_watch_alert or {}).get("action")
                            self._pending_watch_alert = None
                            if self._watch_stop.is_set():
                                return
                            if action == "keep":
                                self._watch_state["state"] = "querying"
                                self.emit("watch_status_changed", dict(self._watch_state))
                                continue
                            if action == "mute_join":
                                self.set_game_audio_muted(True)
                            if action != "join" and action != "mute_join":
                                continue
                        self._watch_state["state"] = "joining"; self.emit("watch_status_changed", dict(self._watch_state))
                        self._last_join_result = None
                        self.start_join(server["id"], "server", "immediate")
                        # Keep Watch Mode alive around a failed/full join.  A
                        # slot can disappear between the two query samples and
                        # the actual GUI connection attempt; that is a normal
                        # race, not a reason to terminate monitoring.
                        while (self._join_thread and self._join_thread.is_alive()
                               and not self._watch_stop.is_set()):
                            time.sleep(.1)
                        if self._last_join_result == "success":
                            return
                        if not self._watch_stop.is_set():
                            self._watch_state["state"] = "querying"
                            self._watch_state["last_status"] = {"available": False, "reason": "join_failed"}
                            self.emit("watch_status_changed", dict(self._watch_state))
                            time.sleep(1)
                            continue
                        return
                self.emit("watch_status_changed", dict(self._watch_state)); time.sleep(2)
        finally:
            if self._watch_state.get("state") not in {"joining", "joined"}:
                self._watch_state["state"] = "stopped" if self._watch_stop.is_set() else "failed"
            self.emit("watch_status_changed", dict(self._watch_state))

    def pause_watch(self):
        self._watch_pause.set()
        if self._watch_state.get("server_id"):
            self.update_discord_presence("paused", self._watch_state["server_id"], started_at=self._watch_state.get("started_at"))
        return {"ok": True}

    def resume_watch(self):
        self._watch_pause.clear()
        if self._watch_state.get("server_id"):
            self.update_discord_presence("watching", self._watch_state["server_id"], started_at=self._watch_state.get("started_at"))
        return {"ok": True}

    def stop_watch(self):
        self._watch_stop.set(); self._watch_pause.clear(); self._watch_alert.set(); self._pending_watch_alert = None; self._record_decision("user_stop"); self.set_game_audio_muted(False); self.clear_discord_presence(); return {"ok": True}

    def handle_watch_alert_action(self, action, server_id):
        """Accept only a same-user toast action for the currently confirmed slot."""
        if action not in {"join", "keep", "mute_join"}:
            return {"ok": False, "error": "unsupported slot-alert action"}
        pending = self._pending_watch_alert or {}
        if str(pending.get("server_id")) != str(server_id):
            return {"ok": False, "error": "that slot alert is no longer active"}
        pending["action"] = action
        self._pending_watch_alert = pending
        self._watch_alert.set()
        self.emit("toast_requested", {"message": "Slot alert action received."})
        return {"ok": True}

    def set_game_audio_muted(self, muted):
        """Toggle a tray/manual mute and always restore the prior session state."""
        if muted:
            if self._manual_audio_controller is None:
                self._manual_audio_controller = audio_control.start_for_run(True, lambda message: self.emit("log_line", {"message": message}))
            return {"ok": True, "muted": bool(self._manual_audio_controller)}
        if self._manual_audio_controller is not None:
            self._manual_audio_controller.stop()
            self._manual_audio_controller = None
        return {"ok": True, "muted": False}

    def get_watch_status(self):
        return {"ok": True, "watch": dict(self._watch_state)}

    def get_server_history(self, server_id, limit=100):
        return {"ok": True, "samples": self.history.recent(str(server_id), int(limit))}

    def get_server_insights(self, server_id):
        return {"ok": True, "insights": self.history.insights(str(server_id))}

    def get_server_heatmap(self, server_id):
        return {"ok": True, "heatmap": self.history.heatmap(str(server_id))}

    def calibration_target_map(self):
        calibration = self.get_calibration_state()["calibration"]
        points = calibration.get("points") or {}
        rect = calibration.get("metadata", {}).get("live_client_rect")
        targets = []
        for name in config.REQUIRED_CLICK_POINTS:
            point = points.get(name, [0, 0])
            relative = None
            if rect and point and len(point) == 2 and rect[2] > rect[0] and rect[3] > rect[1]:
                relative = [round((point[0] - rect[0]) / (rect[2] - rect[0]), 4), round((point[1] - rect[1]) / (rect[3] - rect[1]), 4)]
            targets.append({"id": name, "point": point, "relative": relative, "captured": tuple(point) != (0, 0)})
        return {"ok": True, "targets": targets, "client_rect": rect, "metadata": calibration.get("metadata", {})}

    def run_setup_check(self, server_id=None):
        game = joiner.find_game_executable()
        try:
            watcher = logwatch.LogWatcher(); log_ready = bool(getattr(watcher, "path", None)); watcher.close()
        except Exception:
            log_ready = False
        try:
            audio_ready = bool(audio_control.GameAudioMute().available)
        except Exception:
            audio_ready = False
        profile_data = self.get_calibration_profiles()
        active = next((item for item in profile_data.get("profiles", []) if item.get("id") == profile_data.get("active")), None)
        health = active.get("health") if active else "automatic"
        discord_state = self.get_discord_status()
        query_check = {"id": "query", "label": "A2S server query", "ok": None, "detail": "Choose a saved server to run a voluntary query check."}
        if server_id:
            server = next((item for item in self._load_store()["servers"] if item["id"] == str(server_id)), None)
            if not server:
                query_check = {"id": "query", "label": "A2S server query", "ok": False, "detail": "The selected saved server no longer exists."}
            else:
                status = resolver.query_server(server["ip"], server["port"], path=self.store_path)
                query_check = {"id": "query", "label": "A2S server query", "ok": bool(status), "detail": "Selected server responded to an A2S query." if status else "No A2S response from the selected server; Watch Mode can keep trying."}
        checks = [
            {"id": "game", "label": "SCP:SL installation", "ok": bool(game), "detail": "Game executable detected." if game else "SCP:SL executable was not found."},
            {"id": "log", "label": "Player.log", "ok": log_ready, "detail": "Local connection log is readable." if log_ready else "Player.log is not available yet."},
            {"id": "audio", "label": "Game audio control", "ok": audio_ready, "detail": "Game audio can be muted during a run." if audio_ready else "Audio control is unavailable; joining still works."},
            {"id": "calibration", "label": "Calibration", "ok": health != "stale", "detail": f"Profile health: {health}."},
            {"id": "notifications", "label": "Notifications", "ok": bool(self._load_config().get("notifications_enabled", True)), "detail": "Notifications are enabled." if self._load_config().get("notifications_enabled", True) else "Notifications are disabled in Settings."},
            {"id": "discord", "label": "Discord", "ok": not self._load_config().get("discord_enabled") or bool(discord_state.get("connected")), "detail": "Optional Discord integration is ready." if discord_state.get("connected") else "Discord is optional and can remain unavailable."},
            query_check,
        ]
        self.emit("setup_check_completed", {"checks": checks})
        return {"ok": True, "checks": checks}

    @staticmethod
    def _safe_config_for_export(cfg):
        clean = dict(cfg or {})
        for key in ("discord_application_id", "discord_enabled", "discord_share_players"):
            clean.pop(key, None)
        return clean

    @staticmethod
    def _safe_store_for_export(store):
        clean = json.loads(json.dumps(store))
        for server in clean.get("servers", []):
            server.pop("companion_token", None)
        return clean

    def _backup_payload(self):
        return {"schema": "scpsl-autojoin.backup", "version": 1, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "config": self._safe_config_for_export(self._load_config()), "servers": self._safe_store_for_export(self._load_store()),
                "theme": self.theme_manager.load(), "packs": self.pack_manager.load(), "calibrations": self.calibration_profiles.load(),
                "history_summary": {server["id"]: self.history.insights(server["id"]) for server in self._load_store()["servers"]}}

    def create_backup(self):
        stamp = time.strftime('%Y%m%d-%H%M%S')
        # A restore creates its own safety backup immediately after a manual
        # backup can be made, so second-resolution names are not sufficient.
        path = os.path.join(self.data_dir, f"scpsl-autojoin-backup-{stamp}-{time.time_ns() % 1_000_000_000:09d}.zip")
        with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("backup.json", json.dumps(self._backup_payload(), indent=2))
        return {"ok": True, "path": path}

    def preview_backup(self, path):
        try:
            with zipfile.ZipFile(os.fspath(path)) as archive:
                payload = json.loads(archive.read("backup.json").decode("utf-8"))
            if payload.get("schema") != "scpsl-autojoin.backup" or payload.get("version") != 1:
                raise ValueError("unsupported backup")
            servers = payload.get("servers", {}).get("servers", [])
            return {"ok": True, "summary": {"servers": len(servers), "groups": len(payload.get("servers", {}).get("groups", [])), "profiles": len(payload.get("calibrations", {}).get("profiles", [])), "created_at": payload.get("created_at")}, "backup": payload}
        except (OSError, KeyError, TypeError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
            return {"ok": False, "error": f"Could not read backup: {exc}"}

    def restore_backup(self, path):
        preview = self.preview_backup(path)
        if not preview.get("ok"):
            return preview
        safety = self.create_backup()
        payload = preview["backup"]
        current = {
            "config": self._load_config(), "servers": self._load_store(),
            "calibrations": self.calibration_profiles.load(), "theme": self.theme_manager.load(),
            "packs": self.pack_manager.load(),
        }
        try:
            server_store.save_store(payload["servers"], self.store_path)
            self._save_config({**config.DEFAULTS, **payload.get("config", {})})
            self.calibration_profiles.save(payload.get("calibrations", {"profiles": [], "active": None}))
            self.theme_manager.save(payload.get("theme", {"preset": "violet", "custom": None}))
            # Pack files are never copied from a backup. This restores only
            # metadata for packs already present in the local game folder.
            self.pack_manager._save(payload.get("packs", {"version": 1, "packs": [], "active_pack": None}))
            return {"ok": True, "safety_backup": safety["path"], **self._state()}
        except (OSError, TypeError, ValueError, KeyError) as exc:
            try:
                server_store.save_store(current["servers"], self.store_path)
                self._save_config(current["config"])
                self.calibration_profiles.save(current["calibrations"])
                self.theme_manager.save(current["theme"])
                self.pack_manager._save(current["packs"])
                rollback = "The pre-restore state was restored."
            except (OSError, TypeError, ValueError):
                rollback = f"Use the safety backup at {safety.get('path', 'the backup location')} to roll back."
            return {"ok": False, "error": f"Restore failed. {rollback} ({exc})"}

    def _monitor_query(self, server):
        return self._query_server(server)

    @staticmethod
    def _companion_token(server):
        encrypted = server.get("companion_token")
        if not encrypted:
            return ""
        try:
            return secret_store.unprotect(encrypted)
        except (RuntimeError, OSError, ValueError):
            return ""

    def _query_server(self, server):
        url = server.get("companion_url")
        token = self._companion_token(server)
        if url and token:
            try:
                from companion_client import CompanionClient
                companion = CompanionClient(url, token).status(timeout=2)
                capacity = companion["capacity"]
                return {"available": True, "players": capacity["players"], "max_players": capacity["max_players"], "latency_ms": None, "source": "companion", "round": companion.get("round", {}), "player": companion.get("player", {})}
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        return resolver.query_server(server["ip"], server["port"], path=self.store_path) or {"available": False}

    def _record_monitor_sample(self, server, status):
        self.history.record(server["id"], status.get("available", False), status.get("players"), status.get("max_players"), status.get("latency_ms"))
        self.emit("server_sampled", {"server_id": server["id"], "status": status, "source": "background"})

    def start_background_monitor(self):
        if self._monitor and self._monitor.running:
            return {"ok": False, "error": "background monitoring is already running"}
        servers = [server for server in self._load_store()["servers"] if (server.get("monitoring") or {}).get("enabled")]
        if not servers:
            return {"ok": False, "error": "enable monitoring on at least one saved server first"}
        self._monitor = BackgroundMonitor(servers, self._monitor_query, self._record_monitor_sample)
        self._monitor.start()
        self.emit("monitor_status_changed", {"running": True, "servers": len(self._monitor.servers)})
        return {"ok": True, "monitor": self.get_monitor_status()}

    def stop_background_monitor(self):
        if self._monitor:
            self._monitor.stop()
        self.emit("monitor_status_changed", {"running": False, "servers": 0})
        return {"ok": True, "monitor": self.get_monitor_status()}

    def get_monitor_status(self):
        return {"running": bool(self._monitor and self._monitor.running), "servers": len(self._monitor.servers) if self._monitor else 0}

    def get_calibration_profiles(self):
        data = self.calibration_profiles.load()
        current = self._calibration_runtime_metadata()
        for profile in data.get("profiles", []):
            profile["health"] = self.calibration_profiles.health(profile, current)
        return {"ok": True, **data, "current_metadata": current}

    def save_calibration_profile(self, name, points, metadata):
        return {"ok": True, "profile": self.calibration_profiles.add(name, points, metadata), **self.calibration_profiles.load()}

    def set_active_calibration_profile(self, profile_id):
        data = self.calibration_profiles.load(); data["active"] = str(profile_id); self.calibration_profiles.save(data); return {"ok": True, **data}

    def delete_calibration_profile(self, profile_id):
        data = self.calibration_profiles.load(); data["profiles"] = [p for p in data["profiles"] if p.get("id") != str(profile_id)]; data["active"] = data["active"] if any(p.get("id") == data["active"] for p in data["profiles"]) else None; self.calibration_profiles.save(data); return {"ok": True, **data}

    def rename_calibration_profile(self, profile_id, name):
        try:
            self.calibration_profiles.rename(profile_id, name)
            return {"ok": True, **self.calibration_profiles.load()}
        except (KeyError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def duplicate_calibration_profile(self, profile_id, name):
        try:
            profile = self.calibration_profiles.duplicate(profile_id, name)
            return {"ok": True, "profile": profile, **self.calibration_profiles.load()}
        except (KeyError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def set_discord_enabled(self, enabled):
        result = self.discord.set_enabled(enabled)
        cfg = self._load_config(); cfg["discord_enabled"] = bool(enabled); self._save_config(cfg)
        return result

    def get_discord_status(self):
        return {"ok": True, "enabled": self.discord.enabled, "connected": self.discord.connected,
                "configured": bool(self.discord.ipc.client_id), "presence": self.discord.current,
                "error": self.discord.last_error}

    def set_discord_application_id(self, application_id):
        """Store a public Discord application ID and rebuild the lazy IPC client."""
        value = str(application_id or "").strip()
        if value and not re.fullmatch(r"\d{17,20}", value):
            return {"ok": False, "error": "Discord Application ID must be a 17-20 digit value."}
        cfg = self._load_config()
        cfg["discord_application_id"] = value
        self._save_config(cfg)
        enabled = bool(cfg.get("discord_enabled", False))
        self.discord.clear()
        self.discord = DiscordPresence(client_id=value or None, on_join=self._handle_discord_join)
        self.discord.set_enabled(enabled)
        return {"ok": True, "configured": bool(value), "enabled": enabled}

    def clear_discord_presence(self):
        return self.discord.clear()

    def update_discord_presence(self, status, server_id=None, players=None, max_players=None,
                                started_at=None):
        """Update presence without ever exposing an endpoint."""
        cfg = self._load_config()
        if bool(cfg.get("discord_enabled")) != self.discord.enabled:
            self.discord.set_enabled(bool(cfg.get("discord_enabled")))
        server = next((item for item in self._load_store()["servers"] if item["id"] == str(server_id)), None)
        share_server = bool(server and server.get("share_presence"))
        share_players = bool(cfg.get("discord_share_players")) and share_server
        return self.discord.update(
            status,
            server_name=server.get("name") if share_server else None,
            players=players if share_players else None,
            max_players=max_players if share_players else None,
            started_at=started_at,
            share=share_players,
            share_server=share_server,
            join_secret=self._discord_join_secret(server) if share_server else None,
        )

    def get_companion_status(self, url, token):
        try:
            from companion_client import CompanionClient
            return {"ok": True, "status": CompanionClient(url, token).status()}
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc)}

    def get_companion_dashboard(self, server_id):
        server = next((item for item in self._load_store()["servers"] if item["id"] == str(server_id)), None)
        if not server:
            return {"ok": False, "error": "saved server was not found"}
        if not server.get("companion_url"):
            return {"ok": False, "error": "no owned-server companion is configured for this server"}
        try:
            from companion_client import CompanionClient
            status = CompanionClient(server["companion_url"], self._companion_token(server)).status(timeout=2)
            return {"ok": True, "server": {"id": server["id"], "name": server["name"]}, "status": status,
                    "connection": {"healthy": True, "source": "companion", "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}}
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": f"Companion unavailable: {exc}", "connection": {"healthy": False, "source": "a2s-fallback"}}

    def check_translation_updates(self):
        """Return update candidates without downloading or activating anything."""
        from translation_updates import source_details, github_revision, github_release
        results = []
        for pack in self.pack_manager.load().get("packs", []):
            details = source_details(pack.get("source", ""))
            if details["kind"] not in {"github", "github_release"}:
                continue
            try:
                if details["kind"] == "github_release":
                    release = github_release(details["owner"], details["repo"], details["tag"])
                    revision = release.get("tag")
                else:
                    release = None
                    revision = github_revision(details["owner"], details["repo"])
            except Exception as exc:
                results.append({"id": pack.get("id"), "error": str(exc)})
                continue
            if revision and revision != pack.get("revision"):
                item = {"id": pack.get("id"), "name": pack.get("name"), "revision": revision, "update_available": True}
                if release and release.get("asset_url"):
                    item["asset_url"] = release["asset_url"]
                results.append(item)
        return {"ok": True, "updates": results}

    def update_translation_pack(self, pack_id):
        """Download and replace one pack only after the user requests it."""
        pack = next((item for item in self.pack_manager.load().get("packs", []) if item.get("id") == str(pack_id)), None)
        if not pack:
            return {"ok": False, "error": "pack is not installed"}
        source = pack.get("source", "")
        try:
            from translation_updates import source_details, github_release
            details = source_details(source)
            revision = None
            if details["kind"] == "github_release":
                release = github_release(details["owner"], details["repo"], details["tag"])
                revision = release.get("tag")
                download_url = release.get("asset_url") or release.get("zipball_url")
                if not download_url:
                    raise PackError("GitHub release has no downloadable ZIP")
            else:
                # Repository revision is checked separately by the explicit
                # update-check action; keep the current value if the download
                # itself is being tested/offline.
                revision = pack.get("revision")
                download_url = self.pack_manager.resolve_link(source)
            payload = self.pack_manager._read_url(download_url)
            fd, temporary = tempfile.mkstemp(prefix="translation-update-", suffix=".zip", dir=self.data_dir)
            os.close(fd)
            try:
                with open(temporary, "wb") as stream:
                    stream.write(payload)
                result = self.pack_manager.update_from_path(str(pack_id), temporary, source)
            finally:
                try:
                    os.remove(temporary)
                except OSError:
                    pass
            result["pack"]["revision"] = revision
            result["pack"]["last_checked"] = time.time()
            data = self.pack_manager.load()
            for item in data.get("packs", []):
                if item.get("id") == str(pack_id):
                    item.update({"revision": revision, "last_checked": result["pack"]["last_checked"]})
            self.pack_manager._save(data)
            return {"ok": True, "pack": result["pack"], "packs": data}
        except (PackError, OSError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc), "packs": self.pack_manager.load()}

    def export_destination(self, name, server_ids):
        store = self._load_store(); servers = [s for s in store["servers"] if s["id"] in {str(i) for i in server_ids}]
        try: return {"ok": True, "bundle": export_bundle(name, servers)}
        except (KeyError, TypeError, ValueError) as exc: return {"ok": False, "error": str(exc)}

    def export_destination_link(self, name, server_ids):
        result = self.export_destination(name, server_ids)
        if not result.get("ok"):
            return result
        return {"ok": True, "bundle": result["bundle"], "link": encode_link(result["bundle"])}

    def preview_destination(self, raw):
        try: return {"ok": True, "destination": import_bundle(raw)}
        except (ValueError, TypeError, json.JSONDecodeError) as exc: return {"ok": False, "error": str(exc)}

    def import_destination(self, raw):
        try:
            destination = import_bundle(raw)
            imported = [server_store.upsert_server(item["name"], item["host"], item["port"], self.store_path) for item in destination["servers"]]
            self.emit("destination_received", {"name": destination["name"], "count": len(imported)})
            return {"ok": True, "destination": destination, "servers": imported}
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc)}

    def import_destination_link(self, link):
        try:
            value = str(link).strip()
            payload = decode_link(value) if value.lower().startswith("scpsl-autojoin://") else import_bundle(value)
            return self.import_destination(json.dumps(payload))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": str(exc)}

    def _run_join(self, runner, target):
        def status(message):
            self.emit("status_changed", {"message": str(message)})
            self.emit("log_line", {"message": str(message)})
        try:
            result = runner(target, on_status=status, stop_event=self._join_stop)
            self._last_join_result = result
            if result == "success" and self._watch_state.get("state") == "joining":
                self._watch_state["state"] = "joined"
                self.emit("watch_status_changed", dict(self._watch_state))
            self.update_discord_presence(
                "joined" if result == "success" else "idle",
                target if result == "success" and isinstance(target, str) else None,
                started_at=time.time() if result == "success" else None,
            )
            self.emit("join_succeeded" if result == "success" else "join_failed", {"result": result})
        except Exception as exc:
            self._last_join_result = "error"
            self.update_discord_presence("idle")
            self.emit("join_failed", {"result": "error", "message": str(exc)})

    def stop_join(self):
        self._join_stop.set(); self.clear_discord_presence(); return {"ok": True}

    def shutdown(self):
        """Release background resources when the desktop window closes."""
        self._join_stop.set()
        self._watch_stop.set()
        self._watch_pause.clear()
        if self._monitor:
            self._monitor.stop()
        self.set_game_audio_muted(False)
        self.clear_discord_presence()

    def get_join_status(self):
        running = bool(self._join_thread and self._join_thread.is_alive())
        return {"ok": True, "join": {"running": running}}

    def get_calibration_state(self):
        cfg = self._load_config()
        metadata = dict(cfg.get("calibration_metadata") or {})
        metadata.update(self._calibration_runtime_metadata())
        hwnd = winput.find_game_window(joiner.GAME_TITLE)
        if hwnd:
            rect = winput.get_client_rect(hwnd)
            metadata.update({"live_client_rect": list(rect) if rect else None, "live_dpi": winput.get_window_dpi(hwnd)})
        return {"ok": True, "calibration": {"calibrated": config.calibrated(cfg), "points": cfg.get("click_points", {}), "metadata": metadata}}

    def _calibration_runtime_metadata(self):
        executable = joiner.find_game_executable()
        metadata = {"game_fingerprint": executable_fingerprint(executable)}
        hwnd = winput.find_game_window(joiner.GAME_TITLE)
        if hwnd:
            rect = winput.get_client_rect(hwnd)
            metadata.update({"client_size": [rect[2] - rect[0], rect[3] - rect[1]] if rect else None, "dpi": winput.get_window_dpi(hwnd)})
        return metadata

    def capture_calibration_point(self, name):
        point = winput.get_cursor_pos()
        return {"ok": bool(point), "name": str(name), "point": list(point) if point else None}

    def save_calibration(self, points, metadata=None):
        cfg = self._load_config()
        cfg["click_points"].update({str(k): [int(v[0]), int(v[1])] for k, v in points.items()})
        cfg["calibration_metadata"] = dict(metadata or {})
        cfg["calibration_space"] = "physical_v2"; cfg["navigation_mode"] = "manual"
        self._save_config(cfg)
        self.emit("calibration_changed", self.get_calibration_state()["calibration"])
        return self.get_calibration_state()

    def run_input_diagnostic(self):
        hwnd = winput.find_game_window(joiner.GAME_TITLE)
        rect = winput.get_client_rect(hwnd) if hwnd else None
        return {"ok": True, "game_detected": bool(hwnd), "client_rect": list(rect) if rect else None, "dpi": winput.get_window_dpi(hwnd) if hwnd else None}

    def export_local_data(self):
        return self.create_backup()

    def reset_local_storage(self):
        removed = []
        for path in (self.config_path, self.store_path):
            if os.path.isfile(path):
                os.remove(path)
                removed.append(path)
        return {"ok": True, "removed": removed, **self._state()}

    def get_settings(self):
        return {"ok": True, "settings": self._load_config()}

    def save_setting(self, key, value):
        allowed = set(config.DEFAULTS) - {"click_points", "config_version"}
        if key not in allowed:
            return {"ok": False, "error": "setting is not editable"}
        numeric_limits = {
            "retry_interval_s": (0, 86400), "attempt_timeout_s": (1, 86400),
            "max_unclear": (0, 1000), "max_attempts": (0, 1000000),
            "max_minutes": (0, 525600), "browser_refresh_timeout_s": (1, 120),
        }
        if key in numeric_limits:
            try:
                value = int(value)
            except (TypeError, ValueError):
                return {"ok": False, "error": f"{key} must be a whole number"}
            low, high = numeric_limits[key]
            if not low <= value <= high:
                return {"ok": False, "error": f"{key} must be between {low} and {high}"}
        elif key in {"group_loop", "onboarding_complete", "notifications_enabled", "notification_sound", "quiet_notifications", "slot_alert_actions", "compact_mode", "high_contrast", "large_text", "mute_game_audio", "auto_update", "discord_enabled", "discord_share_players"}:
            if not isinstance(value, bool):
                return {"ok": False, "error": f"{key} must be true or false"}
        elif key == "navigation_mode" and value not in {"automatic", "manual"}:
            return {"ok": False, "error": "navigation_mode is invalid"}
        elif key == "connection_method" and value not in {"automatic", "foreground", "background", "direct"}:
            return {"ok": False, "error": "connection_method is invalid"}
        elif key == "motion_preset" and value not in {"expressive", "contained", "off"}:
            return {"ok": False, "error": "motion_preset is invalid"}
        elif key == "accent" and value not in {"violet", "amber", "slate", "cyan", "green", "red", "light", "light-warm", "light-slate", "custom"}:
            return {"ok": False, "error": "accent is invalid"}
        elif key == "custom_accent" and (not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value)):
            return {"ok": False, "error": "custom_accent must be a six-digit hex color"}
        cfg = self._load_config(); cfg[key] = value; self._save_config(cfg)
        return {"ok": True, "settings": cfg}

    def import_translation_pack(self, source, source_url=""):
        try:
            record = self.pack_manager.import_path(source, source_url)
            return {"ok": True, "pack": record, "packs": self.pack_manager.load()}
        except (PackError, OSError) as exc:
            return {"ok": False, "error": str(exc)}

    def search_translation_packs(self, query):
        try: return {"ok": True, "results": self.pack_manager.search_github(str(query))}
        except Exception as exc: return {"ok": False, "error": str(exc), "results": []}

    def install_translation_link(self, url):
        try:
            download_url = self.pack_manager.resolve_link(url)
            payload = self.pack_manager._read_url(download_url)
            temporary = os.path.join(self.data_dir, "translation-download.zip")
            with open(temporary, "wb") as stream:
                stream.write(payload)
            return self.import_translation_pack(temporary, str(url))
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def activate_translation_pack(self, pack_id):
        try:
            return {"ok": True, "packs": self.pack_manager.activate(str(pack_id))}
        except (PackError, OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "packs": self.pack_manager.load()}

    def deactivate_translation_pack(self):
        return {"ok": True, "packs": self.pack_manager.deactivate()}

    def restore_translation_backup(self, pack_id):
        try:
            restored = self.pack_manager.restore(str(pack_id))
            return {"ok": bool(restored), "restored": bool(restored),
                    "error": None if restored else "no backup exists for this pack",
                    "packs": self.pack_manager.load()}
        except (PackError, OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "packs": self.pack_manager.load()}

    def delete_translation_pack(self, pack_id):
        try:
            deleted = self.pack_manager.delete(str(pack_id))
            return {"ok": bool(deleted), "deleted": bool(deleted),
                    "error": None if deleted else "pack is not installed",
                    "packs": self.pack_manager.load()}
        except (PackError, OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "packs": self.pack_manager.load()}

    def open_translation_folder(self, pack_id=None):
        path = self.pack_manager.translations_dir
        if pack_id:
            pack = next((item for item in self.pack_manager.load()["packs"] if item.get("id") == pack_id), None)
            if not pack:
                return {"ok": False, "error": "pack is not installed"}
            try:
                path = self.pack_manager.folder_path(pack["folder"])
            except PackError as exc:
                return {"ok": False, "error": str(exc)}
        os.makedirs(path, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(path)
        else:
            webbrowser.open(path)
        return {"ok": True, "path": path}

    def save_custom_theme(self, filename, css):
        try:
            custom = self.theme_manager.save_custom(filename, css)
            return {"ok": True, "css": custom["compiled"], "theme": self.theme_manager.load()}
        except ValueError as exc: return {"ok": False, "error": str(exc)}

    def set_theme(self, preset):
        try:
            preset = str(preset)
            theme = self.theme_manager.set_preset(preset)
            cfg = self._load_config(); cfg["accent"] = preset; self._save_config(cfg)
            return {"ok": True, "theme": theme}
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "theme": self.theme_manager.load()}

    def reset_theme(self):
        return {"ok": True, "theme": self.theme_manager.reset()}

    def create_bug_report(self):
        path = os.path.join(self.data_dir, f"bug-report-{int(time.time())}.json")
        with open(path, "w", encoding="utf-8") as stream:
            json.dump({"created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "diagnostics": self.run_input_diagnostic(), "decisions": self.get_join_explanations()["items"]}, stream, indent=2)
        return {"ok": True, "path": path}

    def create_support_bundle(self):
        path = os.path.join(self.data_dir, f"support-bundle-{time.strftime('%Y%m%d-%H%M%S')}.zip")
        report = {"created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "version": APP_VERSION,
                  "diagnostics": self.run_input_diagnostic(), "setup": self.run_setup_check(),
                  "calibration": self.calibration_target_map(), "decisions": self.get_join_explanations()["items"],
                  "settings": self._safe_config_for_export(self._load_config())}
        # Avoid logging personal endpoints, notes, server history, tokens, or Discord values.
        def scrub_log(text):
            text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?\b", "[endpoint removed]", text)
            text = re.sub(r"\b[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?::\d{1,5})?\b", "[endpoint removed]", text, flags=re.I)
            text = re.sub(r"(?i)(bearer\s+|token[=:]\s*)[^\s,;]+", r"\1[removed]", text)
            return text
        with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("report.json", json.dumps(report, indent=2))
            log_dir = os.path.join(self.data_dir, "logs")
            if os.path.isdir(log_dir):
                for filename in sorted(os.listdir(log_dir))[-3:]:
                    source = os.path.join(log_dir, filename)
                    if os.path.isfile(source) and filename.lower().endswith((".log", ".txt")):
                        with open(source, "r", encoding="utf-8", errors="replace") as stream:
                            archive.writestr(os.path.join("logs", os.path.basename(source)), scrub_log(stream.read()))
        return {"ok": True, "path": path}

    def get_update_status(self):
        try:
            import updater
            return {"ok": True, "update": updater.check_for_update()}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "update": None}

    def install_update(self, release):
        try:
            import updater
            if not isinstance(release, dict) or not release.get("version"):
                return {"ok": False, "error": "No verified update was selected."}
            updater.install_update(release)
            return {"ok": True, "message": "Update verified. Restarting…"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def open_data_folder(self):
        os.startfile(self.data_dir) if hasattr(os, "startfile") else webbrowser.open(self.data_dir)
        return {"ok": True}

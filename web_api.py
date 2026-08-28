"""pywebview-facing application API.

All methods return JSON-serializable dictionaries. The browser never receives
Python objects or executable callback strings.
"""
import json
import os
import threading
import time
import webbrowser

import config
import joiner
import resolver
import server_store
import winput
from app_paths import app_dir
from theme_manager import ThemeManager
from translation_packs import PackError, PackManager

APP_VERSION = "0.3.6"


def _translation_dir():
    executable = joiner.find_game_executable()
    if executable:
        return os.path.abspath(os.path.join(os.path.dirname(executable), "Translations"))
    return os.path.abspath(os.path.join(app_dir(), "Translations"))


class WebApi:
    def __init__(self, data_dir=None, translations_dir=None):
        self.data_dir = os.path.abspath(os.fspath(data_dir or app_dir()))
        self.translations_dir = os.path.abspath(os.fspath(translations_dir or _translation_dir()))
        self.pack_manager = PackManager(self.data_dir, self.translations_dir)
        self.theme_manager = ThemeManager(self.data_dir)
        self._sink = None
        self._join_thread = None
        self._join_stop = threading.Event()

    def set_event_sink(self, sink):
        self._sink = sink

    def emit(self, event, data=None):
        if self._sink:
            self._sink({"event": event, "data": data or {}})

    def _state(self):
        cfg = config.load_config()
        store = server_store.load_store()
        return {
            "servers": store["servers"], "groups": store["groups"],
            "settings": cfg, "calibration": self.get_calibration_state()["calibration"],
            "theme": self.theme_manager.load(), "packs": self.pack_manager.load(),
            "join": self.get_join_status()["join"],
        }

    def get_app_state(self):
        return {"ok": True, "version": APP_VERSION, **self._state()}

    def get_servers(self, query=""):
        return {"ok": True, "servers": server_store.search_servers(query)}

    def save_server(self, name, ip, port):
        return {"ok": True, "server": server_store.upsert_server(str(name), str(ip), int(port))}

    def rename_server(self, server_id, name):
        store = server_store.load_store(); item = next(s for s in store["servers"] if s["id"] == server_id)
        return {"ok": True, "server": server_store.update_server(server_id, name, item["ip"], item["port"])}

    def delete_server(self, server_id):
        return {"ok": True, "deleted": server_store.delete_server(server_id)}

    def refresh_server_status(self, server_id):
        store = server_store.load_store(); item = next(s for s in store["servers"] if s["id"] == server_id)
        result = resolver.query_server(item["ip"], item["port"])
        return {"ok": True, "server": item, "status": result or {"available": False}}

    def get_groups(self):
        return {"ok": True, "groups": server_store.load_store()["groups"]}

    def save_group(self, name, server_ids, group_id=None):
        group = (server_store.update_group(group_id, list(server_ids), name=name)
                 if group_id else server_store.create_group(str(name), list(server_ids)))
        return {"ok": True, "group": group}

    def delete_group(self, group_id):
        return {"ok": True, "deleted": server_store.delete_group(group_id)}

    def start_join(self, target, target_type="server"):
        if self._join_thread and self._join_thread.is_alive():
            return {"ok": False, "error": "auto-join is already running"}
        self._join_stop.clear()
        runner = joiner.run_group if target_type == "group" else joiner.run
        self._join_thread = threading.Thread(target=self._run_join, args=(runner, target), daemon=True)
        self._join_thread.start()
        return {"ok": True}

    def _run_join(self, runner, target):
        def status(message):
            self.emit("status_changed", {"message": str(message)})
            self.emit("log_line", {"message": str(message)})
        try:
            result = runner(target, on_status=status, stop_event=self._join_stop)
            self.emit("join_succeeded" if result == "success" else "join_failed", {"result": result})
        except Exception as exc:
            self.emit("join_failed", {"result": "error", "message": str(exc)})

    def stop_join(self):
        self._join_stop.set(); return {"ok": True}

    def get_join_status(self):
        running = bool(self._join_thread and self._join_thread.is_alive())
        return {"ok": True, "join": {"running": running}}

    def get_calibration_state(self):
        cfg = config.load_config()
        metadata = dict(cfg.get("calibration_metadata") or {})
        hwnd = winput.find_game_window(joiner.GAME_TITLE)
        if hwnd:
            rect = winput.get_client_rect(hwnd)
            metadata.update({"live_client_rect": list(rect) if rect else None, "live_dpi": winput.get_window_dpi(hwnd)})
        return {"ok": True, "calibration": {"calibrated": config.calibrated(cfg), "points": cfg.get("click_points", {}), "metadata": metadata}}

    def capture_calibration_point(self, name):
        point = winput.get_cursor_pos()
        return {"ok": bool(point), "name": str(name), "point": list(point) if point else None}

    def save_calibration(self, points, metadata=None):
        cfg = config.load_config()
        cfg["click_points"].update({str(k): [int(v[0]), int(v[1])] for k, v in points.items()})
        cfg["calibration_metadata"] = dict(metadata or {})
        cfg["calibration_space"] = "physical_v2"; cfg["navigation_mode"] = "manual"
        config.save_config(cfg)
        self.emit("calibration_changed", self.get_calibration_state()["calibration"])
        return self.get_calibration_state()

    def run_input_diagnostic(self):
        hwnd = winput.find_game_window(joiner.GAME_TITLE)
        rect = winput.get_client_rect(hwnd) if hwnd else None
        return {"ok": True, "game_detected": bool(hwnd), "client_rect": list(rect) if rect else None, "dpi": winput.get_window_dpi(hwnd) if hwnd else None}

    def get_settings(self):
        return {"ok": True, "settings": config.load_config()}

    def save_setting(self, key, value):
        allowed = set(config.DEFAULTS) - {"click_points", "config_version"}
        if key not in allowed:
            return {"ok": False, "error": "setting is not editable"}
        cfg = config.load_config(); cfg[key] = value; config.save_config(cfg)
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
        return {"ok": True, "packs": self.pack_manager.activate(pack_id)}

    def deactivate_translation_pack(self):
        return {"ok": True, "packs": self.pack_manager.deactivate()}

    def restore_translation_backup(self, pack_id):
        return {"ok": True, "restored": self.pack_manager.restore(pack_id), "packs": self.pack_manager.load()}

    def delete_translation_pack(self, pack_id):
        return {"ok": True, "deleted": self.pack_manager.delete(pack_id), "packs": self.pack_manager.load()}

    def save_custom_theme(self, filename, css):
        try:
            custom = self.theme_manager.save_custom(filename, css)
            return {"ok": True, "css": custom["compiled"], "theme": self.theme_manager.load()}
        except ValueError as exc: return {"ok": False, "error": str(exc)}

    def set_theme(self, preset):
        return {"ok": True, "theme": self.theme_manager.set_preset(preset)}

    def reset_theme(self):
        return {"ok": True, "theme": self.theme_manager.reset()}

    def create_bug_report(self):
        path = os.path.join(self.data_dir, f"bug-report-{int(time.time())}.json")
        with open(path, "w", encoding="utf-8") as stream:
            json.dump({"created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "state": self._state()}, stream, indent=2)
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

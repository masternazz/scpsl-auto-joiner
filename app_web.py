"""WebView2 desktop shell for the SCP:SL Auto-Joiner UI."""
import json
import os
import sys
import threading
import traceback

import webview

import config
import joiner
import logwatch
import resolver
import winput
from app_paths import app_dir, resource_path

STARTUP_LOG = os.path.join(app_dir(), "startup-trace.log")


def startup_trace(message):
    try:
        with open(STARTUP_LOG, "a", encoding="utf-8") as log:
            log.write(f"{message}\n")
    except OSError:
        pass


def resource_dir():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


class Api:
    def __init__(self):
        self.window = None
        self.watcher = None
        self.remember_stop = threading.Event()
        self.join_stop = threading.Event()
        self.join_thread = None

    def get_state(self):
        startup_trace("get_state called")
        cfg = config.load_config()
        return {
            "calibrated": config.calibrated(cfg),
            "navigation_mode": cfg.get("navigation_mode", "automatic"),
            "servers": sorted(resolver.load_servers()),
            "points": cfg["click_points"],
        }

    def get_cursor(self):
        return winput.get_cursor_pos()

    def save_calibration(self, points):
        cfg = config.load_config()
        cfg["click_points"].update({k: [int(v[0]), int(v[1])] for k, v in points.items()})
        cfg["navigation_mode"] = "manual"
        config.save_config(cfg)
        return self.get_state()

    def save_server(self, name, ip, port):
        resolver.remember_server(str(name).strip(), str(ip), int(port))
        return self.get_state()

    def begin_remember(self):
        if self.watcher is not None:
            return False
        self.remember_stop.clear()
        self.watcher = logwatch.LogWatcher()

        def watch():
            try:
                match = self.watcher.wait_for_regex(logwatch.CONNECTING_IP_RE, 120)
                if self.remember_stop.is_set():
                    self.push("backendStatus", "Server detection stopped.", False)
                    return
                if match:
                    self.push("serverDetected", match.group(1), int(match.group(2)))
                else:
                    self.push("backendStatus", "Timed out waiting for a connection attempt.", False)
            except Exception as exc:
                self.push("backendStatus", f"Could not read Player.log: {exc}", False)
            finally:
                self.watcher.close()
                self.watcher = None

        threading.Thread(target=watch, daemon=True).start()
        return True

    def stop_remember(self):
        self.remember_stop.set()
        return True

    def start_join(self, name):
        if self.join_thread is not None and self.join_thread.is_alive():
            return False
        self.join_stop.clear()

        def run():
            try:
                result = joiner.run(name, on_status=lambda text: self.push("backendStatus", text, True), stop_event=self.join_stop)
                self.push("backendFinished", result, False)
            finally:
                self.join_thread = None

        self.join_thread = threading.Thread(target=run, daemon=True)
        self.join_thread.start()
        return True

    def stop_join(self):
        self.join_stop.set()
        return True

    def push(self, function, *args):
        if not self.window:
            return
        payload = ", ".join(json.dumps(arg) for arg in args)
        try:
            self.window.evaluate_js(f"window.{function}({payload})")
        except Exception:
            pass


def main():
    startup_trace("main entered")
    api = Api()
    page = os.path.join(resource_dir(), "webui", "index.html")
    startup_trace(f"page={page} exists={os.path.exists(page)}")
    window = webview.create_window("SCP:SL Auto-Joiner", page, js_api=api, width=1180, height=760, min_size=(980, 620))
    startup_trace("window created")
    api.window = window
    startup_trace("starting webview")
    try:
        webview.start(
            gui="edgechromium",
            debug=not getattr(sys, "frozen", False),
            http_server=True,
            private_mode=False,
            storage_path=os.path.join(app_dir(), "webview"),
        )
        startup_trace("webview stopped normally")
    except Exception:
        startup_trace("webview raised an exception")
        error_path = os.path.join(app_dir(), "startup-error.log")
        with open(error_path, "a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        import gui
        gui.main()


if __name__ == "__main__":
    main()

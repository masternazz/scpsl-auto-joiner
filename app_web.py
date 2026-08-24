"""WebView2 desktop shell for the SCP:SL Auto-Joiner UI."""
import json
import os
import sys
import threading

import webview

import config
import joiner
import logwatch
import resolver
import winput
from app_paths import resource_path


def resource_dir():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


class Api:
    def __init__(self):
        self.window = None
        self.watcher = None

    def get_state(self):
        cfg = config.load_config()
        return {
            "calibrated": config.calibrated(cfg),
            "servers": sorted(resolver.load_servers()),
            "points": cfg["click_points"],
        }

    def get_cursor(self):
        return winput.get_cursor_pos()

    def save_calibration(self, points):
        cfg = config.load_config()
        cfg["click_points"].update({k: [int(v[0]), int(v[1])] for k, v in points.items()})
        config.save_config(cfg)
        return self.get_state()

    def save_server(self, name, ip, port):
        resolver.remember_server(str(name).strip(), str(ip), int(port))
        return self.get_state()

    def begin_remember(self):
        if self.watcher is not None:
            return False
        self.watcher = logwatch.LogWatcher()

        def watch():
            try:
                match = self.watcher.wait_for_regex(logwatch.CONNECTING_IP_RE, 120)
                if match:
                    self.push("serverDetected", match.group(1), int(match.group(2)))
                else:
                    self.push("status", "Timed out waiting for a connection attempt.", False)
            except Exception as exc:
                self.push("status", f"Could not read Player.log: {exc}", False)
            finally:
                self.watcher.close()
                self.watcher = None

        threading.Thread(target=watch, daemon=True).start()
        return True

    def start_join(self, name):
        def run():
            result = joiner.run(name, on_status=lambda text: self.push("status", text, True))
            self.push("finished", result, False)

        threading.Thread(target=run, daemon=True).start()
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
    api = Api()
    page = os.path.join(resource_dir(), "webui", "index.html")
    window = webview.create_window("SCP:SL Auto-Joiner", page, js_api=api, width=1180, height=760, min_size=(980, 620))
    api.window = window
    webview.start(debug=not getattr(sys, "frozen", False))


if __name__ == "__main__":
    main()

"""Production WebView2 entry point for SCP:SL Auto-Joiner."""
import json
import os
import sys
import traceback

from app_paths import app_dir, resource_path
from web_api import WebApi

STARTUP_LOG = os.path.join(app_dir(), "startup-trace.log")


def startup_trace(message):
    os.makedirs(os.path.dirname(STARTUP_LOG), exist_ok=True)
    with open(STARTUP_LOG, "a", encoding="utf-8") as stream:
        stream.write(f"{message}\n")


class Bridge(WebApi):
    """WebView API adapter that sends one structured event envelope."""
    def __init__(self, window=None):
        super().__init__()
        self.window = window
        self.set_event_sink(self._send_event)

    def _send_event(self, event):
        if not self.window:
            return
        try:
            self.window.evaluate_js(f"window.__appEvent({json.dumps(event, ensure_ascii=False)})")
        except Exception:
            startup_trace("event delivery failed")

    def pick_translation_source(self, kind="file"):
        """Use pywebview's native picker; WebView2 does not expose local paths to JS."""
        if not self.window:
            return {"ok": False, "error": "The native file picker is unavailable."}
        try:
            import webview
            dialog = webview.FileDialog.FOLDER if kind == "folder" else webview.FileDialog.OPEN
            types = () if kind == "folder" else ("ZIP files (*.zip)",)
            paths = self.window.create_file_dialog(dialog, allow_multiple=False, file_types=types)
            return {"ok": bool(paths), "path": paths[0] if paths else None}
        except (AttributeError, OSError, TypeError) as exc:
            startup_trace(f"translation picker failed: {exc}")
            return {"ok": False, "error": f"Could not open the native picker: {exc}"}


def _show_startup_error(message):
    startup_trace(message)
    with open(os.path.join(app_dir(), "startup-error.log"), "a", encoding="utf-8") as stream:
        stream.write(message + "\n")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "SCP:SL Auto-Joiner could not start", 0x10)
    except Exception:
        pass


def main():
    if "--legacy-ui" in sys.argv:
        import gui
        return gui.main()
    startup_trace("webview main entered")
    try:
        import webview
    except Exception as exc:
        _show_startup_error(f"WebView2 shell is unavailable: {exc}\nInstall Microsoft Edge WebView2 Runtime or run with --legacy-ui.")
        return 1
    page = resource_path(os.path.join("webui", "index.html"))
    if not os.path.isfile(page):
        _show_startup_error(f"The WebView UI resource is missing:\n{page}")
        return 1
    bridge = Bridge()
    window = webview.create_window("SCP:SL // CONTAINMENT", page, js_api=bridge,
                                   width=1280, height=820, min_size=(960, 640), background_color="#0b090f")
    bridge.window = window
    try:
        webview.start(gui="edgechromium", debug=not getattr(sys, "frozen", False),
                      http_server=True, private_mode=False,
                      storage_path=os.path.join(app_dir(), "webview"))
        return 0
    except Exception:
        startup_trace(traceback.format_exc())
        _show_startup_error("WebView2 could not be started. Install or repair the Microsoft Edge WebView2 Runtime.\n\nSee startup-error.log in AppData for details.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

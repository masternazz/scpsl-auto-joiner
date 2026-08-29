"""Production WebView2 entry point for SCP:SL Auto-Joiner."""
import json
import os
import sys
import traceback
import ctypes

from app_paths import app_dir, resource_path
from web_api import WebApi

STARTUP_LOG = os.path.join(app_dir(), "startup-trace.log")
_INSTANCE_MUTEX = None


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


def _claim_single_instance():
    """Prevent two WebView2 profiles from competing during startup."""
    global _INSTANCE_MUTEX
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        _INSTANCE_MUTEX = kernel32.CreateMutexW(None, False, "Local\\SCP-SL-Auto-Joiner-WebView2")
        if not _INSTANCE_MUTEX:
            startup_trace(f"single-instance mutex failed: {ctypes.get_last_error()}")
            return True
        if ctypes.get_last_error() == 183:
            # Opening the shortcut twice should behave like a normal desktop
            # app: reveal the existing window instead of showing a fake crash.
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
            user32.FindWindowW.restype = ctypes.c_void_p
            user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
            user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
            hwnd = user32.FindWindowW(None, "SCP:SL // CONTAINMENT")
            if hwnd:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                startup_trace("duplicate launch focused existing window")
            else:
                startup_trace("duplicate launch found no visible window")
            return False
    except Exception as exc:
        startup_trace(f"single-instance check failed: {exc}")
    return True


def main():
    if "--legacy-ui" in sys.argv:
        import gui
        return gui.main()
    startup_trace("webview main entered")
    if not _claim_single_instance():
        return 1
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
    startup_trace("creating webview window")
    window = webview.create_window("SCP:SL // CONTAINMENT", page, js_api=bridge,
                                   width=1280, height=820, min_size=(960, 640), background_color="#0b090f")
    bridge.window = window
    try:
        # User data is persisted by the backend in AppData. A private WebView2
        # session avoids stale or locked EBWebView profiles breaking startup.
        webview.start(gui="edgechromium", debug=not getattr(sys, "frozen", False),
                      http_server=True, private_mode=True)
        return 0
    except Exception:
        startup_trace(traceback.format_exc())
        _show_startup_error("WebView2 could not be started. Install or repair the Microsoft Edge WebView2 Runtime.\n\nSee startup-error.log in AppData for details.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

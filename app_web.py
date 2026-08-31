"""Production WebView2 entry point for SCP:SL Auto-Joiner."""
import json
import os
import sys
import traceback
import ctypes

from app_paths import app_dir, resource_path
from web_api import WebApi
from instance_forward import ForwardingServer, send as forward_send

STARTUP_LOG = os.path.join(app_dir(), "startup-trace.log")
_INSTANCE_MUTEX = None


def send_destination_to_existing_instance(link):
    """Forward a registered destination URI to the already-running instance."""
    value = str(link or "").strip()
    if not value.lower().startswith("scpsl-autojoin://"):
        return False
    forward_send({"command": "import_destination", "data": value})
    return True


def forward_startup_link(link):
    """Best-effort duplicate-instance handoff used by URI protocol launches."""
    value = str(link or "").strip()
    if not value.lower().startswith("scpsl-autojoin://"):
        return False
    try:
        return bool(send_destination_to_existing_instance(value))
    except (OSError, EOFError, ConnectionError, TimeoutError):
        startup_trace("destination link could not be forwarded to existing instance")
        return False


def startup_trace(message):
    os.makedirs(os.path.dirname(STARTUP_LOG), exist_ok=True)
    with open(STARTUP_LOG, "a", encoding="utf-8") as stream:
        stream.write(f"{message}\n")


def application_icon_path():
    """Return the packaged S mark for Qt's title bar and Windows taskbar."""
    icon = resource_path(os.path.join("assets", "app.ico"))
    return icon if os.path.isfile(icon) else None


class Bridge:
    """Small, explicit API surface exposed to WebView2.

    pywebview recursively inspects every *public* attribute of ``js_api``.
    Keeping the application service and native Window private is essential:
    exposing either makes pywebview walk a very large object graph during
    startup, before it can raise ``pywebviewready`` in the page.
    """

    _COMMANDS = (
        "activate_translation_pack", "capture_calibration_point",
        "create_bug_report", "deactivate_translation_pack", "delete_group",
        "delete_server", "delete_translation_pack", "export_local_data",
        "get_app_state", "get_calibration_state", "get_groups",
        "get_join_status", "get_servers", "get_settings", "get_update_status",
        "get_server_history", "get_server_insights", "get_watch_status", "get_monitor_status",
        "get_calibration_profiles", "get_discord_status",
        "get_companion_status",
        "check_translation_updates", "update_translation_pack",
        "import_translation_pack", "install_translation_link", "install_update",
        "open_data_folder", "open_translation_folder", "refresh_server_status",
        "remember_server", "rename_server", "reset_local_storage", "reset_theme",
        "restore_translation_backup", "run_input_diagnostic", "save_calibration",
        "save_custom_theme", "save_group", "save_server", "save_setting",
        "save_server_profile", "start_watch", "pause_watch", "resume_watch", "stop_watch",
        "start_background_monitor", "stop_background_monitor",
        "set_game_audio_muted",
        "save_group_policy",
        "export_destination", "export_destination_link", "preview_destination", "import_destination", "import_destination_link",
        "save_calibration_profile", "set_active_calibration_profile", "delete_calibration_profile",
        "rename_calibration_profile", "duplicate_calibration_profile",
        "set_discord_enabled", "set_discord_application_id", "clear_discord_presence",
        "update_discord_presence",
        "search_translation_packs", "set_theme", "start_join", "start_remember",
        "stop_join", "stop_remember",
    )

    def __init__(self):
        self._api = WebApi()
        self._window = None
        self._api.set_event_sink(self._send_event)
        # Bind only the deliberate, serializable command methods. Do not
        # subclass WebApi: its managers, paths and threads are implementation
        # details, not JavaScript API objects.
        for command in self._COMMANDS:
            setattr(self, command, getattr(self._api, command))

    def _attach_window(self, window):
        self._window = window

    def _send_event(self, event):
        if not self._window:
            return
        try:
            self._window.evaluate_js(f"window.__appEvent({json.dumps(event, ensure_ascii=False)})")
        except Exception:
            startup_trace("event delivery failed")

    def pick_translation_source(self, kind="file"):
        """Use pywebview's native picker; WebView2 does not expose local paths to JS."""
        if not self._window:
            return {"ok": False, "error": "The native file picker is unavailable."}
        try:
            import webview
            dialog = webview.FileDialog.FOLDER if kind == "folder" else webview.FileDialog.OPEN
            types = () if kind == "folder" else ("ZIP files (*.zip)",)
            paths = self._window.create_file_dialog(dialog, allow_multiple=False, file_types=types)
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
    pending_link = next((arg for arg in sys.argv[1:] if str(arg).lower().startswith("scpsl-autojoin://")), None)
    if not _claim_single_instance():
        return 0 if forward_startup_link(pending_link) else 1
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
    bridge._attach_window(window)
    forwarder = ForwardingServer(
        lambda payload: bridge._api.emit("destination_import_requested", {"raw": payload["data"]})
    )
    try:
        forwarder.start()
    except (OSError, RuntimeError) as exc:
        startup_trace(f"destination forwarding unavailable: {exc}")
    # Do not construct Qt tray objects before pywebview has created its Qt
    # application.  On frozen Windows builds this can terminate the process
    # inside Qt before Python gets a chance to report an exception.
    tray_holder = {"tray": None}

    def install_tray_after_qt():
        # The tray implementation is native Win32 and does not create Qt
        # objects, so it can safely be installed after WebView initialization.
        try:
            from tray import install_tray
            tray_holder["tray"] = install_tray(window, bridge._api)
            startup_trace("tray installed" if tray_holder["tray"] else "tray unavailable")
        except Exception as exc:
            startup_trace(f"tray unavailable: {exc}")
    # These markers distinguish an unavailable WebView2 runtime from a page
    # loading without the Python API. They are intentionally tiny and remain
    # useful in a packaged build where DevTools are not enabled.
    window.events.before_load += lambda: startup_trace("webview before_load")
    window.events._pywebviewready += lambda: startup_trace("webview api ready")
    window.events.loaded += lambda: (startup_trace("webview loaded"), install_tray_after_qt())
    if pending_link:
        window.events.loaded += lambda: bridge._api.emit("destination_import_requested", {"raw": pending_link})
    def on_closing():
        # Closing an active run hides the window and leaves the worker alive;
        # an explicit tray Exit sets _tray_exit_requested so it can really
        # terminate. Idle windows close normally.
        if getattr(window, "_tray_exit_requested", False):
            return True
        try:
            active_join = bridge._api.get_join_status().get("join", {}).get("running")
            active_watch = bridge._api.get_watch_status().get("watch", {}).get("state") not in {"idle", "stopped", "failed", "joined"}
            if active_join or active_watch:
                window.hide()
                startup_trace("active close hidden to tray")
                return False
        except Exception as exc:
            startup_trace(f"close-state check failed: {exc}")
        return True

    def on_closed():
        bridge._api.shutdown()
        forwarder.stop()
        if tray_holder["tray"]:
            tray_holder["tray"].stop()
    window.events.closing += on_closing
    window.events.closed += on_closed
    try:
        # User data is persisted by the backend in AppData. A private WebView2
        # session avoids stale or locked EBWebView profiles breaking startup.
        # Qt WebEngine is bundled with the application. It avoids pywebview's
        # optional pythonnet/WinForms host, which can fail before WebView2 has
        # a chance to initialise in a frozen Python application.
        webview.start(gui="qt", debug=not getattr(sys, "frozen", False), icon=application_icon_path(),
                      http_server=True, private_mode=True)
        return 0
    except Exception:
        startup_trace(traceback.format_exc())
        _show_startup_error("The desktop browser shell could not be started.\n\nSee startup-error.log in AppData for details.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

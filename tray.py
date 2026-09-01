"""Crash-safe Windows notification-area controls using the Win32 shell API."""
import os
import threading

from app_paths import resource_path

if os.name == "nt":
    import win32api
    import win32con
    import win32gui


class NativeTray:
    WM_TRAY = win32con.WM_USER + 1 if os.name == "nt" else 0
    WM_EXIT = win32con.WM_APP + 1 if os.name == "nt" else 0
    CMD_SHOW, CMD_PAUSE, CMD_RESUME, CMD_STOP, CMD_MUTE, CMD_EXIT = range(1001, 1007)

    def __init__(self, window, api):
        self.window, self.api = window, api
        self.hwnd = self.thread = self.failed = None
        self.ready = threading.Event()
        self._muted = False
        self._icon = None

    def start(self):
        if os.name != "nt":
            return False
        self.thread = threading.Thread(target=self._run, name="native-tray", daemon=True)
        self.thread.start(); self.ready.wait(3)
        return bool(self.hwnd and not self.failed)

    def _run(self):
        try:
            instance = win32api.GetModuleHandle(None)
            name = "SCPSLAutoJoinerTray"
            wc = win32gui.WNDCLASS(); wc.hInstance = instance
            wc.lpszClassName = name; wc.lpfnWndProc = self._window_proc
            try: win32gui.RegisterClass(wc)
            except win32gui.error: pass
            self.hwnd = win32gui.CreateWindow(name, "SCP:SL Auto-Joiner", 0, 0, 0, 0, 0, 0, 0, instance, None)
            icon_path = resource_path(os.path.join("assets", "app.ico"))
            if os.path.isfile(icon_path):
                self._icon = win32gui.LoadImage(None, icon_path, win32con.IMAGE_ICON, 0, 0,
                                                 win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE)
            icon = self._icon or win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
            flags = win32gui.NIF_MESSAGE | win32gui.NIF_ICON | win32gui.NIF_TIP
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, (self.hwnd, 0, flags, self.WM_TRAY, icon, "SCP:SL Auto-Joiner"))
            self.ready.set(); win32gui.PumpMessages()
        except Exception as exc:
            self.failed = exc; self.ready.set()

    def _window_proc(self, hwnd, message, wparam, lparam):
        if message == self.WM_TRAY:
            if lparam in (win32con.WM_RBUTTONUP, win32con.WM_LBUTTONUP): self._show_menu()
            return 0
        if message == self.WM_EXIT:
            win32gui.PostQuitMessage(0); return 0
        if message == win32con.WM_COMMAND:
            self._command(wparam & 0xffff); return 0
        return win32gui.DefWindowProc(hwnd, message, wparam, lparam)

    def _show_menu(self):
        self._refresh_tip()
        menu = win32gui.CreatePopupMenu()
        for command, label in ((self.CMD_SHOW, "Show"), (self.CMD_PAUSE, "Pause watch"), (self.CMD_RESUME, "Resume watch"), (self.CMD_STOP, "Stop watch")):
            win32gui.AppendMenu(menu, win32con.MF_STRING, command, label)
        flags = win32con.MF_STRING | (win32con.MF_CHECKED if self._muted else 0)
        win32gui.AppendMenu(menu, flags, self.CMD_MUTE, "Mute game audio")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, self.CMD_EXIT, "Exit")
        win32gui.SetForegroundWindow(self.hwnd)
        x, y = win32gui.GetCursorPos()
        win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, x, y, 0, self.hwnd, None)
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0); win32gui.DestroyMenu(menu)

    def _refresh_tip(self):
        """Refresh the tooltip lazily on interaction; never block the tray loop."""
        try:
            watch = self.api.get_watch_status().get("watch", {})
            state = str(watch.get("state") or "idle").upper()
            target = str(watch.get("server_name") or "")
            status = watch.get("last_status") or {}
            detail = f" · {target}" if target else ""
            if status.get("players") is not None and status.get("max_players"):
                detail = f" · {status['players']}/{status['max_players']}"
                if status.get("latency_ms") is not None:
                    detail += f" · {round(status['latency_ms'])} ms"
            text = (f"SCP:SL Auto-Joiner · {state}{detail}")[:127]
            icon = self._icon or win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
            win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, (self.hwnd, 0, win32gui.NIF_TIP | win32gui.NIF_ICON, self.WM_TRAY, icon, text))
        except Exception:
            pass

    def _command(self, command):
        if command == self.CMD_SHOW: self.window.show()
        elif command == self.CMD_PAUSE: self.api.pause_watch()
        elif command == self.CMD_RESUME: self.api.resume_watch()
        elif command == self.CMD_STOP: self.api.stop_watch()
        elif command == self.CMD_MUTE:
            self._muted = not self._muted; self.api.set_game_audio_muted(self._muted)
        elif command == self.CMD_EXIT:
            self.api.shutdown()
            self.window._tray_exit_requested = True
            self.window.destroy()
            win32gui.PostQuitMessage(0)

    def stop(self):
        if self.hwnd:
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0))
                win32api.PostMessage(self.hwnd, self.WM_EXIT, 0, 0)
            except Exception: pass
        if self._icon:
            try: win32gui.DestroyIcon(self._icon)
            except Exception: pass
            self._icon = None


def install_tray(window, api):
    tray = NativeTray(window, api)
    return tray if tray.start() else None

"""Minimal Windows window/input helpers for driving SCP:SL — no screen
capture, no template matching, just window-finding and clicking/typing. Click
and key-tap logic (SendInput byte layout, PostMessage lParam bit packing) is
adapted from the proven implementation in
H:\\vscode\\Full-Auto-Forza-Edition\\capture.py, trimmed to what this project
needs. Pure ctypes — no new pip dependency."""
import ctypes
import time
from ctypes import wintypes as _wintypes

VK_ESCAPE = 0x1B
VK_RETURN = 0x0D
VK_BACK = 0x08
VK_CONTROL = 0x11
VK_A = 0x41
VK_F8 = 0x77
VK_F9 = 0x78

_WM_KEYDOWN = 0x0100
_WM_KEYUP = 0x0101
_WM_CHAR = 0x0102
_WM_MOUSEMOVE = 0x0200
_WM_LBUTTONDOWN = 0x0201
_WM_LBUTTONUP = 0x0202
_WM_ACTIVATEAPP = 0x001C
_MK_LBUTTON = 0x0001
_CLICK_MOVE_DWELL = 0.15  # let a hover-highlight settle before the click lands

_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004


def get_cursor_pos():
    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    point = _POINT()
    if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        return point.x, point.y
    return None


def key_is_down(vk):
    """Return whether a global Windows virtual key is currently held."""
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def set_dpi_awareness():
    """Per-Monitor-v2 DPI awareness. Call once at startup so click
    coordinates captured during calibration match physical pixels at run
    time — same requirement documented in H:\\vscode\\halo\\common.py."""
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _is_game_window(title, class_name, target):
    title = title.strip().lower()
    return title == target.strip().lower() or (title == "scpsl" and class_name == "UnityWndClass")


def find_game_window(title_exact: str):
    """Find SCP:SL's visible top-level window.

    Borderless/fullscreen builds commonly expose ``SCPSL`` as the window
    title instead of the game's display name, so accept that Unity window
    as well as the requested title.
    """
    try:
        u32 = ctypes.windll.user32
        target = title_exact.strip().lower()
        matches = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def _cb(hwnd, _lparam):
            try:
                if not u32.IsWindowVisible(hwnd):
                    return True
                n = u32.GetWindowTextLengthW(hwnd)
                if n <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                class_buf = ctypes.create_unicode_buffer(256)
                u32.GetClassNameW(hwnd, class_buf, len(class_buf))
                if _is_game_window(buf.value, class_buf.value, target):
                    matches.append(hwnd)
            except Exception:
                pass
            return True

        u32.EnumWindows(WNDENUMPROC(_cb), 0)
        return matches[0] if matches else None
    except Exception:
        return None


def get_window_rect(hwnd):
    """Return (left, top, right, bottom) for a top-level window."""
    rect = _wintypes.RECT()
    if hwnd and ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return rect.left, rect.top, rect.right, rect.bottom
    return None


def get_client_rect(hwnd):
    """Return the client rectangle in screen coordinates.

    Unity menu coordinates belong to the client surface, not the title bar or
    non-client frame. Returning screen coordinates keeps this usable by both
    PostMessage and SendInput callers.
    """
    if not hwnd:
        return None
    try:
        u32 = ctypes.windll.user32
        rect = _wintypes.RECT()
        if not u32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        origin = _wintypes.POINT(0, 0)
        if not u32.ClientToScreen(hwnd, ctypes.byref(origin)):
            return None
        return origin.x, origin.y, origin.x + rect.right, origin.y + rect.bottom
    except Exception:
        return None


def get_window_dpi(hwnd):
    """Return the effective DPI for a window when Windows exposes it."""
    if not hwnd:
        return None
    try:
        getter = getattr(ctypes.windll.user32, "GetDpiForWindow", None)
        if getter:
            value = int(getter(hwnd))
            return value or None
    except Exception:
        pass
    return None


def focus_window(hwnd) -> bool:
    """Best-effort bring `hwnd` to the foreground — needed before the
    SendInput fallback path, which always targets whatever window is
    focused. Works around Windows' foreground-lock via AttachThreadInput."""
    if not hwnd:
        return False
    try:
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        fg = u32.GetForegroundWindow()
        if fg == hwnd:
            return True
        cur_tid = k32.GetCurrentThreadId()
        fg_tid = u32.GetWindowThreadProcessId(fg, None) if fg else 0
        tgt_tid = u32.GetWindowThreadProcessId(hwnd, None)
        attached_fg = attached_tgt = False
        if fg_tid and fg_tid != cur_tid:
            attached_fg = bool(u32.AttachThreadInput(cur_tid, fg_tid, True))
        if tgt_tid and tgt_tid != cur_tid and tgt_tid != fg_tid:
            attached_tgt = bool(u32.AttachThreadInput(cur_tid, tgt_tid, True))
        try:
            if u32.IsIconic(hwnd):
                u32.ShowWindow(hwnd, 9)  # SW_RESTORE
            u32.BringWindowToTop(hwnd)
            ok = bool(u32.SetForegroundWindow(hwnd))
        finally:
            if attached_fg:
                u32.AttachThreadInput(cur_tid, fg_tid, False)
            if attached_tgt:
                u32.AttachThreadInput(cur_tid, tgt_tid, False)
        return ok
    except Exception:
        return False


# ── SendInput structures (foreground path) ─────────────────────────────
class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", _wintypes.DWORD), ("dwFlags", _wintypes.DWORD),
                ("time", _wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _MINPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("_pad", ctypes.c_byte * 28)]


class _MINPUT(ctypes.Structure):
    _fields_ = [("type", _wintypes.DWORD), ("union", _MINPUT_UNION)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", _wintypes.WORD), ("wScan", _wintypes.WORD),
                ("dwFlags", _wintypes.DWORD), ("time", _wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _KINPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("_pad", ctypes.c_byte * 28)]


class _KINPUT(ctypes.Structure):
    _fields_ = [("type", _wintypes.DWORD), ("union", _KINPUT_UNION)]


def mouse_click(x: int, y: int, post_wait: float = 0.5):
    """Foreground click at absolute screen (x, y) via SendInput. Only
    reliable when the target window is already focused — call focus_window
    first."""
    ctypes.windll.user32.SetCursorPos(int(x), int(y))
    time.sleep(0.1)
    for flag in (0x0002, 0x0004):  # LEFTDOWN, LEFTUP
        inp = _MINPUT(type=0, union=_MINPUT_UNION(mi=_MOUSEINPUT(
            dx=0, dy=0, mouseData=0, dwFlags=flag, time=0, dwExtraInfo=None)))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_MINPUT))
        time.sleep(0.05)
    time.sleep(post_wait)


def send_key_tap(vk: int, post_wait: float = 0.1):
    """Foreground key tap via SendInput (both wVk and wScan set, matching
    both the VK message path and the DirectInput/Raw-Input scancode path)."""
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    for key_up in (False, True):
        flags = _KEYEVENTF_KEYUP if key_up else 0
        inp = _KINPUT(type=1, union=_KINPUT_UNION(ki=_KEYBDINPUT(
            wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=None)))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_KINPUT))
        time.sleep(0.05)
    if post_wait:
        time.sleep(post_wait)


def send_hotkey(modifier: int, vk: int, post_wait: float = 0.05):
    """Foreground modifier+key shortcut using SendInput."""
    send_key_down(modifier)
    send_key_tap(vk, post_wait=0)
    send_key_up(modifier)
    if post_wait:
        time.sleep(post_wait)


def send_key_down(vk: int):
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    inp = _KINPUT(type=1, union=_KINPUT_UNION(ki=_KEYBDINPUT(
        wVk=vk, wScan=scan, dwFlags=0, time=0, dwExtraInfo=None)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_KINPUT))


def send_key_up(vk: int):
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    inp = _KINPUT(type=1, union=_KINPUT_UNION(ki=_KEYBDINPUT(
        wVk=vk, wScan=scan, dwFlags=_KEYEVENTF_KEYUP, time=0, dwExtraInfo=None)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_KINPUT))


def send_text(text: str, post_wait: float = 0.02):
    """Type text into the focused control through Unicode SendInput events."""
    u32 = ctypes.windll.user32
    for char in text:
        code = ord(char)
        for flags in (_KEYEVENTF_UNICODE, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP):
            inp = _KINPUT(type=1, union=_KINPUT_UNION(ki=_KEYBDINPUT(
                wVk=0, wScan=code, dwFlags=flags, time=0, dwExtraInfo=None)))
            u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_KINPUT))
            time.sleep(post_wait)


def _restore_user_input(previous_hwnd, previous_cursor):
    try:
        if previous_cursor:
            ctypes.windll.user32.SetCursorPos(*map(int, previous_cursor))
        if previous_hwnd and ctypes.windll.user32.IsWindow(previous_hwnd):
            focus_window(previous_hwnd)
    except Exception:
        # Restoring another app is best-effort and must never fail a join.
        pass


def foreground_click(hwnd, x: int, y: int, post_wait: float = 0.5):
    """Reliable Unity click with best-effort restoration of user input."""
    previous_hwnd = ctypes.windll.user32.GetForegroundWindow()
    previous_cursor = get_cursor_pos()
    try:
        if not focus_window(hwnd):
            return
        mouse_click(x, y, post_wait=post_wait)
    finally:
        _restore_user_input(previous_hwnd, previous_cursor)


def foreground_key_tap(hwnd, vk: int, post_wait: float = 0.1):
    previous_hwnd = ctypes.windll.user32.GetForegroundWindow()
    previous_cursor = get_cursor_pos()
    try:
        if focus_window(hwnd):
            send_key_tap(vk, post_wait=post_wait)
    finally:
        _restore_user_input(previous_hwnd, previous_cursor)


def foreground_replace_text(hwnd, text: str):
    previous_hwnd = ctypes.windll.user32.GetForegroundWindow()
    previous_cursor = get_cursor_pos()
    try:
        if not focus_window(hwnd):
            return
        send_hotkey(VK_CONTROL, VK_A)
        send_key_tap(VK_BACK, post_wait=0.05)
        send_text(text)
    finally:
        _restore_user_input(previous_hwnd, previous_cursor)


# ── PostMessage (background path — doesn't steal focus) ────────────────
def post_click(hwnd, screen_x: int, screen_y: int, post_wait: float = 0.5):
    """Background click at absolute screen (x, y) via PostMessage. Moves
    twice + dwells before pressing so a hover-highlight settles first."""
    if not hwnd:
        return
    try:
        u32 = ctypes.windll.user32
        post_window_active(hwnd)

        class _PT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = _PT(int(screen_x), int(screen_y))
        u32.ScreenToClient(hwnd, ctypes.byref(pt))
        lparam = ((pt.y & 0xFFFF) << 16) | (pt.x & 0xFFFF)
        u32.PostMessageW(hwnd, _WM_MOUSEMOVE, 0, lparam)
        time.sleep(0.03)
        u32.PostMessageW(hwnd, _WM_MOUSEMOVE, 0, lparam)
        time.sleep(_CLICK_MOVE_DWELL)
        u32.PostMessageW(hwnd, _WM_LBUTTONDOWN, _MK_LBUTTON, lparam)
        time.sleep(0.05)
        u32.PostMessageW(hwnd, _WM_LBUTTONUP, 0, lparam)
        if post_wait:
            time.sleep(post_wait)
    except Exception:
        pass


def _post_key(hwnd, vk: int, key_up: bool):
    u32 = ctypes.windll.user32
    scan = u32.MapVirtualKeyW(vk, 0) & 0xFF
    lparam = 1 | (scan << 16)
    if key_up:
        lparam |= (1 << 30) | (1 << 31)
        msg = _WM_KEYUP
    else:
        msg = _WM_KEYDOWN
    u32.PostMessageW(hwnd, msg, vk, lparam)


def post_key_tap(hwnd, vk: int, post_wait: float = 0.1):
    """Background key tap via PostMessage."""
    if not hwnd:
        return
    try:
        post_window_active(hwnd)
        _post_key(hwnd, vk, key_up=False)
        time.sleep(0.05)
        _post_key(hwnd, vk, key_up=True)
        if post_wait:
            time.sleep(post_wait)
    except Exception:
        pass


def post_hotkey(hwnd, modifier: int, vk: int, post_wait: float = 0.1):
    """Send a two-key shortcut to the game window without stealing focus."""
    if not hwnd:
        return
    try:
        post_window_active(hwnd)
        _post_key(hwnd, modifier, key_up=False)
        _post_key(hwnd, vk, key_up=False)
        _post_key(hwnd, vk, key_up=True)
        _post_key(hwnd, modifier, key_up=True)
        if post_wait:
            time.sleep(post_wait)
    except Exception:
        pass


def replace_text(hwnd, text: str):
    """Replace the active field instead of appending to retained contents."""
    post_hotkey(hwnd, VK_CONTROL, VK_A)
    post_key_tap(hwnd, VK_BACK)
    post_text(hwnd, text)


def post_text(hwnd, text: str, post_wait: float = 0.02):
    """Background text entry via WM_CHAR — types into whatever field the
    game's UI currently has internally focused. Used for the IP:port field."""
    if not hwnd:
        return
    u32 = ctypes.windll.user32
    post_window_active(hwnd)
    for ch in text:
        u32.PostMessageW(hwnd, _WM_CHAR, ord(ch), 0)
        time.sleep(post_wait)


def post_window_active(hwnd):
    """Tell a background target it is active without changing Windows focus.

    This mirrors the background-safe activation hint used by Full Auto Forza.
    It is only a window message: it never moves the cursor or calls a focus
    API, and SCP:SL remains free to ignore it.
    """
    if not hwnd:
        return False
    try:
        return bool(ctypes.windll.user32.PostMessageW(hwnd, _WM_ACTIVATEAPP, 1, 0))
    except Exception:
        return False


if __name__ == "__main__":
    # Runnable smoke check: find_game_window against a window guaranteed to
    # exist on any Windows machine, so this proves the enum/match logic
    # works without needing SCP:SL running.
    set_dpi_awareness()
    hwnd = find_game_window("Program Manager")
    print(f"find_game_window('Program Manager') -> {hwnd}")
    assert hwnd, "expected to find the desktop's Program Manager window"
    print("OK")

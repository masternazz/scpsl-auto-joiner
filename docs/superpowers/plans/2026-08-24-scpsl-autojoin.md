# SCP:SL Auto-Joiner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A small Windows tool that launches SCP:SL, navigates its menus, and repeatedly attempts to join a named server until it gets in or gives up — notifying you either way.

**Architecture:** Log-driven, not vision-driven. `Player.log` is tailed and classified into success/rejected/cancelled outcomes; a local `servers.json` (populated by watching your own manual join attempts) maps friendly names to IP:port; Windows input is driven via raw `ctypes` (PostMessage for background clicks, SendInput as a focus-stealing fallback) — no OCR, no template matching, no new automation dependency.

**Tech Stack:** Python 3.11+, stdlib (`tkinter`, `difflib`, `ctypes`, `json`, `re`), `pytest` for the unit-testable modules, `win11toast` (the one new pip dependency, for Windows toast notifications).

## Global Constraints

- No OCR, screen-reading, or template matching anywhere in the normal run path (spec Non-goals).
- No new pip dependency for input automation — `ctypes` only, using Windows PostMessage/SendInput patterns.
- Server identity comes only from local `servers.json`, never from `api.scpslgame.com` (Cloudflare-gated, requires a Northwood-issued key — confirmed dead end, see spec).
- Outcome detection signatures (verified live against the real client):
  - Success: `Scene Manager: Loaded scene 'Facility'`
  - Rejected: `Connection has been delayed by` AND `OnPeerDisconnected` both present
  - Cancelled: `Connection Failed` present
  - Menu ready: `Scene Manager: Loaded scene 'NewMainMenu'`
  - Attempt started (IP + port): `Connection IP set to ([0-9.]+), port: (\d+)`
- Default tunables: `retry_interval_s=6`, `attempt_timeout_s=20`, `max_unclear=3`, `max_attempts=100`, `max_minutes=30`.
- SCP:SL Steam AppID: `700330` (launch via `steam://rungameid/700330`).
- Project root: `H:\vscode\scpsl-autojoin`.

---

### Task 1: Project scaffolding + config module

**Files:**
- Create: `H:\vscode\scpsl-autojoin\requirements.txt`
- Create: `H:\vscode\scpsl-autojoin\config.py`
- Test: `H:\vscode\scpsl-autojoin\tests\test_config.py`

**Interfaces:**
- Produces: `config.DEFAULTS` (dict), `config.load_config(path=None) -> dict`, `config.save_config(cfg, path=None) -> None`, `config.calibrated(cfg) -> bool`, `config.CONFIG_PATH` (str, default location next to this file).

- [ ] **Step 1: Create the project layout and requirements file**

```bash
mkdir -p "H:/vscode/scpsl-autojoin/tests"
```

`H:\vscode\scpsl-autojoin\requirements.txt`:
```
win11toast
pytest
```

Install them:
```bash
cd "H:/vscode/scpsl-autojoin" && python -m pip install -r requirements.txt
```

- [ ] **Step 2: Write the failing tests**

`H:\vscode\scpsl-autojoin\tests\test_config.py`:
```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config as config_mod


def test_load_config_creates_defaults_when_missing(tmp_path):
    path = str(tmp_path / "config.json")
    cfg = config_mod.load_config(path)
    assert os.path.exists(path)
    assert cfg["retry_interval_s"] == 6
    assert cfg["click_points"]["play"] == [0, 0]


def test_load_config_merges_saved_values(tmp_path):
    path = str(tmp_path / "config.json")
    config_mod.save_config(
        {"retry_interval_s": 9, "click_points": {"play": [12, 34]}}, path)
    cfg = config_mod.load_config(path)
    assert cfg["retry_interval_s"] == 9
    assert cfg["click_points"]["play"] == [12, 34]
    assert cfg["click_points"]["servers_tab"] == [0, 0]


def test_calibrated_false_until_all_points_set(tmp_path):
    path = str(tmp_path / "config.json")
    cfg = config_mod.load_config(path)
    assert config_mod.calibrated(cfg) is False
    for k in cfg["click_points"]:
        cfg["click_points"][k] = [1, 1]
    assert config_mod.calibrated(cfg) is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd "H:/vscode/scpsl-autojoin" && python -m pytest tests/test_config.py -v`
Expected: FAIL / ERROR — `config` module doesn't exist yet.

- [ ] **Step 4: Write the implementation**

`H:\vscode\scpsl-autojoin\config.py`:
```python
"""Persisted settings for the auto-joiner: retry tuning + calibrated click
points. See docs/superpowers/specs/2026-08-24-scpsl-autojoin-design.md."""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULTS = {
    "retry_interval_s": 6,
    "attempt_timeout_s": 20,
    "max_unclear": 3,
    "max_attempts": 100,
    "max_minutes": 30,
    "click_points": {
        "play": [0, 0],
        "servers_tab": [0, 0],
        "internet_tab": [0, 0],
        "direct_connect": [0, 0],
        "ip_field": [0, 0],
        "connect_button": [0, 0],
    },
}


def load_config(path=None):
    path = path or CONFIG_PATH
    if not os.path.exists(path):
        save_config(DEFAULTS, path)
        return json.loads(json.dumps(DEFAULTS))  # deep copy
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    merged = dict(DEFAULTS)
    merged.update(data)
    merged["click_points"] = {**DEFAULTS["click_points"], **data.get("click_points", {})}
    return merged


def save_config(cfg, path=None):
    path = path or CONFIG_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def calibrated(cfg):
    return all(tuple(v) != (0, 0) for v in cfg["click_points"].values())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "H:/vscode/scpsl-autojoin" && python -m pytest tests/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd "H:/vscode/scpsl-autojoin"
git add requirements.txt config.py tests/test_config.py
git commit -m "Add project scaffolding and config module"
```

---

### Task 2: Log watcher / outcome classifier

**Files:**
- Create: `H:\vscode\scpsl-autojoin\logwatch.py`
- Test: `H:\vscode\scpsl-autojoin\tests\test_logwatch.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `logwatch.classify_log_text(text) -> str|None` (one of `"success"`, `"rejected"`, `"cancelled"`, `"connecting"`, or `None`), `logwatch.CONNECTING_IP_RE` (compiled regex, groups `(ip, port)`), `logwatch.MENU_MARK` (str), `logwatch.LogWatcher(path=DEFAULT_LOG_PATH)` with methods `.read_new() -> str`, `.wait_for_outcome(timeout_s, poll_interval=0.25, stop_on_connecting=False) -> str`, `.wait_for_regex(pattern, timeout_s, poll_interval=0.25) -> re.Match|None`, `.wait_for_marker(marker, timeout_s, poll_interval=0.25) -> bool`, `.close()`.

This is the module with real branching logic (spec's designated test target), so it gets full TDD.

- [ ] **Step 1: Write the failing tests**

`H:\vscode\scpsl-autojoin\tests\test_logwatch.py`:
```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from logwatch import classify_log_text, CONNECTING_IP_RE


def test_success_signature():
    text = "Some noise\nScene Manager: Loaded scene 'Facility' [Assets/_Scenes/Facility.unity]\n"
    assert classify_log_text(text) == "success"


def test_rejected_signature():
    text = (
        "Connecting to 1.2.3.4!\n"
        "Connection has been delayed by 1 seconds.\n"
        "NullReferenceException: Object reference not set to an instance of an object.\n"
        "  at Mirror.LiteNetLib4Mirror.LiteNetLib4MirrorClient+<>c__DisplayClass8_0."
        "<OnPeerDisconnected>b__0 () [0x00000] in <00000000000000000000000000000000>:0 \n"
    )
    assert classify_log_text(text) == "rejected"


def test_cancelled_signature():
    text = (
        "Connecting to 1.2.3.4!\n"
        "Connection IP set to 1.2.3.4, port: 7777\n"
        "Connection Failed\n"
        "IP: 1.2.3.4\n"
        "Port: 7777\n"
    )
    assert classify_log_text(text) == "cancelled"


def test_connecting_only_is_not_terminal():
    text = "Connecting to 1.2.3.4!\nConnection IP set to 1.2.3.4, port: 7777\n"
    assert classify_log_text(text) == "connecting"


def test_unrelated_noise_is_none():
    text = "PollingLoop started\nLoading IPHistory\n"
    assert classify_log_text(text) is None


def test_success_wins_even_after_a_prior_rejection_in_the_same_buffer():
    text = (
        "Connection has been delayed by 1 seconds.\n"
        "...OnPeerDisconnected...\n"
        "Scene Manager: Loaded scene 'Facility'\n"
    )
    assert classify_log_text(text) == "success"


def test_connecting_ip_regex_captures_ip_and_port():
    m = CONNECTING_IP_RE.search("Connection IP set to 158.69.52.5, port: 7777\n")
    assert m is not None
    assert m.group(1) == "158.69.52.5"
    assert m.group(2) == "7777"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "H:/vscode/scpsl-autojoin" && python -m pytest tests/test_logwatch.py -v`
Expected: FAIL / ERROR — `logwatch` module doesn't exist yet.

- [ ] **Step 3: Write the implementation**

`H:\vscode\scpsl-autojoin\logwatch.py`:
```python
"""Tails Player.log and classifies join-attempt outcomes. No OCR, no screen
reading — the game's own log tells us everything we need. Signatures verified
live against the real client on 2026-08-24; see the design spec."""
import os
import re
import time

SUCCESS_MARK = "Scene Manager: Loaded scene 'Facility'"
DELAY_MARK = "Connection has been delayed by"
DISCONNECT_MARK = "OnPeerDisconnected"
CANCEL_MARK = "Connection Failed"
CONNECTING_MARK = "Connecting to"
MENU_MARK = "Scene Manager: Loaded scene 'NewMainMenu'"
CONNECTING_IP_RE = re.compile(r"Connection IP set to ([0-9.]+), port: (\d+)")

DEFAULT_LOG_PATH = os.path.join(
    os.environ.get("USERPROFILE", ""), "AppData", "LocalLow",
    "Northwood", "SCPSL", "Player.log")


def classify_log_text(text):
    """Classify accumulated log text since a connect attempt started.
    Returns "success", "rejected", "cancelled", "connecting", or None.
    Checked in this order so a later success in the same buffer always wins
    over an earlier rejection (a retry can succeed after prior failures)."""
    if SUCCESS_MARK in text:
        return "success"
    if DELAY_MARK in text and DISCONNECT_MARK in text:
        return "rejected"
    if CANCEL_MARK in text:
        return "cancelled"
    if CONNECTING_MARK in text:
        return "connecting"
    return None


class LogWatcher:
    """Tails Player.log from the moment it's opened (not from the start of
    the file) — each instance only sees lines written after it was created."""

    def __init__(self, path=None):
        self.path = path or DEFAULT_LOG_PATH
        self._fh = open(self.path, "r", encoding="utf-8", errors="replace")
        self._fh.seek(0, os.SEEK_END)

    def read_new(self):
        return self._fh.read()

    def wait_for_outcome(self, timeout_s, poll_interval=0.25, stop_on_connecting=False):
        """Accumulate new log text and classify it until a terminal outcome
        (success/rejected/cancelled), a timeout, or — if stop_on_connecting —
        the first sighting of "connecting" (used to confirm a click landed,
        without waiting the full attempt timeout for a final result)."""
        deadline = time.monotonic() + timeout_s
        buf = ""
        while time.monotonic() < deadline:
            buf += self.read_new()
            result = classify_log_text(buf)
            if result in ("success", "rejected", "cancelled"):
                return result
            if result == "connecting" and stop_on_connecting:
                return "connecting"
            time.sleep(poll_interval)
        buf += self.read_new()
        return classify_log_text(buf) or "timeout"

    def wait_for_regex(self, pattern, timeout_s, poll_interval=0.25):
        """Wait for a compiled regex to appear in new log text. Returns the
        match, or None on timeout."""
        deadline = time.monotonic() + timeout_s
        buf = ""
        while time.monotonic() < deadline:
            buf += self.read_new()
            m = pattern.search(buf)
            if m:
                return m
            time.sleep(poll_interval)
        return None

    def wait_for_marker(self, marker, timeout_s, poll_interval=0.25):
        """Wait for a plain substring (e.g. MENU_MARK) to appear."""
        return self.wait_for_regex(re.compile(re.escape(marker)), timeout_s, poll_interval) is not None

    def close(self):
        self._fh.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "H:/vscode/scpsl-autojoin" && python -m pytest tests/test_logwatch.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
cd "H:/vscode/scpsl-autojoin"
git add logwatch.py tests/test_logwatch.py
git commit -m "Add log watcher and join-outcome classifier"
```

---

### Task 3: Server resolver + local servers.json

**Files:**
- Create: `H:\vscode\scpsl-autojoin\resolver.py`
- Test: `H:\vscode\scpsl-autojoin\tests\test_resolver.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `resolver.SERVERS_PATH` (str), `resolver.load_servers(path=None) -> dict`, `resolver.save_servers(servers, path=None) -> None`, `resolver.remember_server(name, ip, port, path=None) -> None`, `resolver.resolve(query, path=None) -> tuple[str, str, int] | None`.

- [ ] **Step 1: Write the failing tests**

`H:\vscode\scpsl-autojoin\tests\test_resolver.py`:
```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import resolver as resolver_mod


def test_resolve_returns_none_when_no_servers(tmp_path):
    path = str(tmp_path / "servers.json")
    assert resolver_mod.resolve("canada", path) is None


def test_remember_then_resolve_close_match(tmp_path):
    path = str(tmp_path / "servers.json")
    resolver_mod.remember_server("Northwood Canada 2", "1.2.3.4", 7777, path)
    result = resolver_mod.resolve("canada 2", path)
    assert result == ("Northwood Canada 2", "1.2.3.4", 7777)


def test_resolve_no_close_match_returns_none(tmp_path):
    path = str(tmp_path / "servers.json")
    resolver_mod.remember_server("Northwood Canada 2", "1.2.3.4", 7777, path)
    assert resolver_mod.resolve("totally unrelated xyz", path) is None


def test_remember_server_overwrites_same_name(tmp_path):
    path = str(tmp_path / "servers.json")
    resolver_mod.remember_server("Canada 2", "1.2.3.4", 7777, path)
    resolver_mod.remember_server("Canada 2", "5.6.7.8", 8888, path)
    result = resolver_mod.resolve("Canada 2", path)
    assert result == ("Canada 2", "5.6.7.8", 8888)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "H:/vscode/scpsl-autojoin" && python -m pytest tests/test_resolver.py -v`
Expected: FAIL / ERROR — `resolver` module doesn't exist yet.

- [ ] **Step 3: Write the implementation**

`H:\vscode\scpsl-autojoin\resolver.py`:
```python
"""Resolves a typed server name to (name, ip, port) via a local servers.json
— NOT api.scpslgame.com (Cloudflare-gated, needs a Northwood-issued key; see
the design spec). servers.json is populated by the "remember a server" flow
in gui.py, not hand-edited."""
import difflib
import json
import os

SERVERS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "servers.json")


def load_servers(path=None):
    path = path or SERVERS_PATH
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_servers(servers, path=None):
    path = path or SERVERS_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(servers, f, indent=2)


def remember_server(name, ip, port, path=None):
    path = path or SERVERS_PATH
    servers = load_servers(path)
    servers[name] = {"ip": ip, "port": int(port)}
    save_servers(servers, path)


def resolve(query, path=None):
    """Return (name, ip, port) for the closest saved server name, or None if
    servers.json is empty or nothing is close enough."""
    path = path or SERVERS_PATH
    servers = load_servers(path)
    if not servers:
        return None
    matches = difflib.get_close_matches(query, servers.keys(), n=1, cutoff=0.3)
    if not matches:
        return None
    name = matches[0]
    entry = servers[name]
    return name, entry["ip"], entry["port"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "H:/vscode/scpsl-autojoin" && python -m pytest tests/test_resolver.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd "H:/vscode/scpsl-autojoin"
git add resolver.py tests/test_resolver.py
git commit -m "Add local servers.json resolver"
```

---

### Task 4: Windows input driver (ctypes, no new dependency)

**Files:**
- Create: `H:\vscode\scpsl-autojoin\winput.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `winput.set_dpi_awareness() -> None`, `winput.find_game_window(title_exact) -> int|None`, `winput.focus_window(hwnd) -> bool`, `winput.mouse_click(x, y, post_wait=0.5) -> None` (foreground, SendInput), `winput.send_key_tap(vk, post_wait=0.1) -> None` (foreground, SendInput), `winput.post_click(hwnd, screen_x, screen_y, post_wait=0.5) -> None` (background, PostMessage), `winput.post_key_tap(hwnd, vk, post_wait=0.1) -> None` (background, PostMessage), `winput.post_text(hwnd, text, post_wait=0.02) -> None` (background, WM_CHAR), `winput.VK_ESCAPE` (int).

This module is pure Windows API glue with no meaningful unit-testable branching (its logic is "call this ctypes function with these bytes"). Verification is a runnable smoke check (finds a window guaranteed to exist) plus manual verification against the real game in Task 7.

- [ ] **Step 1: Write the implementation**

`H:\vscode\scpsl-autojoin\winput.py`:
```python
"""Minimal Windows window/input helpers for driving SCP:SL — no screen
capture, no template matching, just window-finding and clicking/typing. Click
and key-tap logic (SendInput byte layout, PostMessage lParam bit packing) is
adapted from the proven implementation in
Windows message/input helpers, trimmed to what this project
needs. Pure ctypes — no new pip dependency."""
import ctypes
import time
from ctypes import wintypes as _wintypes

VK_ESCAPE = 0x1B
VK_RETURN = 0x0D

_WM_KEYDOWN = 0x0100
_WM_KEYUP = 0x0101
_WM_CHAR = 0x0102
_WM_MOUSEMOVE = 0x0200
_WM_LBUTTONDOWN = 0x0201
_WM_LBUTTONUP = 0x0202
_MK_LBUTTON = 0x0001
_CLICK_MOVE_DWELL = 0.15  # let a hover-highlight settle before the click lands

_KEYEVENTF_KEYUP = 0x0002


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


def find_game_window(title_exact: str):
    """Visible top-level window whose title matches `title_exact` exactly
    (case-insensitive, trimmed), or None."""
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
                if buf.value.strip().lower() == target:
                    matches.append(hwnd)
            except Exception:
                pass
            return True

        u32.EnumWindows(WNDENUMPROC(_cb), 0)
        return matches[0] if matches else None
    except Exception:
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


# ── PostMessage (background path — doesn't steal focus) ────────────────
def post_click(hwnd, screen_x: int, screen_y: int, post_wait: float = 0.5):
    """Background click at absolute screen (x, y) via PostMessage. Moves
    twice + dwells before pressing so a hover-highlight settles first."""
    if not hwnd:
        return
    try:
        u32 = ctypes.windll.user32

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
        _post_key(hwnd, vk, key_up=False)
        time.sleep(0.05)
        _post_key(hwnd, vk, key_up=True)
        if post_wait:
            time.sleep(post_wait)
    except Exception:
        pass


def post_text(hwnd, text: str, post_wait: float = 0.02):
    """Background text entry via WM_CHAR — types into whatever field the
    game's UI currently has internally focused. Used for the IP:port field."""
    if not hwnd:
        return
    u32 = ctypes.windll.user32
    for ch in text:
        u32.PostMessageW(hwnd, _WM_CHAR, ord(ch), 0)
        time.sleep(post_wait)


if __name__ == "__main__":
    # Runnable smoke check: find_game_window against a window guaranteed to
    # exist on any Windows machine, so this proves the enum/match logic
    # works without needing SCP:SL running.
    set_dpi_awareness()
    hwnd = find_game_window("Program Manager")
    print(f"find_game_window('Program Manager') -> {hwnd}")
    assert hwnd, "expected to find the desktop's Program Manager window"
    print("OK")
```

- [ ] **Step 2: Run the smoke check**

Run: `cd "H:/vscode/scpsl-autojoin" && python winput.py`
Expected: prints a non-null hwnd and `OK`.

- [ ] **Step 3: Commit**

```bash
cd "H:/vscode/scpsl-autojoin"
git add winput.py
git commit -m "Add ctypes Windows input driver (background + foreground click/key paths)"
```

---

### Task 5: Toast notifier

**Files:**
- Create: `H:\vscode\scpsl-autojoin\notify.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `notify.notify(title, message) -> None`.

Trivial one-function wrapper — no test warranted (ponytail: a one-liner needs no test), just a runnable demo.

- [ ] **Step 1: Write the implementation**

`H:\vscode\scpsl-autojoin\notify.py`:
```python
"""Windows toast notifications. Falls back to a console print if the toast
backend isn't available (e.g. running on an unsupported Windows build) so a
notification failure never crashes the driver loop."""
from win11toast import toast


def notify(title: str, message: str):
    try:
        toast(title, message)
    except Exception:
        print(f"[notify] {title}: {message}")


if __name__ == "__main__":
    notify("SCP:SL Auto-Joiner", "Test notification — if you see a toast, this works.")
```

- [ ] **Step 2: Run the demo**

Run: `cd "H:/vscode/scpsl-autojoin" && python notify.py`
Expected: a Windows toast notification appears (or the console print, if toasts aren't supported).

- [ ] **Step 3: Commit**

```bash
cd "H:/vscode/scpsl-autojoin"
git add notify.py
git commit -m "Add toast notifier"
```

---

### Task 6: Calibration tool

**Files:**
- Create: `H:\vscode\scpsl-autojoin\calibrate.py`

**Interfaces:**
- Consumes: `config.load_config`, `config.save_config` (Task 1); `winput.set_dpi_awareness` (Task 4).
- Produces: `calibrate.run_calibration(cfg_path=None) -> None`, `calibrate.CLICK_POINT_NAMES` (list of str, in prompt order).

Interactive console tool — no automated test (it's blocking terminal I/O by design). Verified manually in Task 9's end-to-end pass.

- [ ] **Step 1: Write the implementation**

`H:\vscode\scpsl-autojoin\calibrate.py`:
```python
"""One-time interactive calibration: records the screen coordinates of the
menu buttons and Direct Connect fields the driver loop clicks blind. Run this
once per machine/resolution, and again any time the game window moves,
resizes, or the menu layout changes."""
import ctypes

import config as config_mod
import winput

CLICK_POINT_NAMES = [
    "play", "servers_tab", "internet_tab", "direct_connect",
    "ip_field", "connect_button",
]

_PROMPTS = {
    "play": "the main menu's Play button",
    "servers_tab": "the Servers tab",
    "internet_tab": "the Internet tab",
    "direct_connect": "the Direct Connect button",
    "ip_field": "the Direct Connect IP:port text field",
    "connect_button": "the Direct Connect dialog's Connect button",
}


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _cursor_pos():
    pt = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def run_calibration(cfg_path=None):
    winput.set_dpi_awareness()
    cfg = config_mod.load_config(cfg_path)
    print("Get SCP:SL open and sitting at the main menu, then continue.")
    input("Press Enter when ready...")
    for name in CLICK_POINT_NAMES:
        input(f"Hover your mouse over {_PROMPTS[name]} (don't click), then press Enter...")
        x, y = _cursor_pos()
        cfg["click_points"][name] = [x, y]
        print(f"  {name} = ({x}, {y})")
    config_mod.save_config(cfg, cfg_path)
    print(f"Calibration saved to {cfg_path or config_mod.CONFIG_PATH}")


if __name__ == "__main__":
    run_calibration()
```

- [ ] **Step 2: Run it manually against the real game**

Run: `cd "H:/vscode/scpsl-autojoin" && python calibrate.py`, follow the prompts with SCP:SL open.
Expected: `config.json`'s `click_points` are all non-`[0, 0]` afterward; `python -c "import config; print(config.calibrated(config.load_config()))"` prints `True`.

- [ ] **Step 3: Commit**

```bash
cd "H:/vscode/scpsl-autojoin"
git add calibrate.py
git commit -m "Add interactive calibration tool"
```

---

### Task 7: Driver loop (orchestration)

**Files:**
- Create: `H:\vscode\scpsl-autojoin\joiner.py`

**Interfaces:**
- Consumes: `config.load_config`, `config.calibrated` (Task 1); `logwatch.LogWatcher`, `logwatch.MENU_MARK`, `logwatch.CONNECTING_MARK` (Task 2); `resolver.resolve` (Task 3); `winput.find_game_window`, `winput.focus_window`, `winput.mouse_click`, `winput.post_click`, `winput.post_key_tap`, `winput.post_text`, `winput.VK_ESCAPE` (Task 4); `notify.notify` (Task 5).
- Produces: `joiner.JoinError` (Exception subclass), `joiner.run(server_name, on_status=None) -> str` (one of `"success"`, `"gave_up"`, `"unclear"`, `"not_calibrated"`, `"not_found"`, `"launch_failed"`).

Pure orchestration glue over already-tested pieces plus live game/OS interaction — no automated test (would require a running SCP:SL instance); verified manually in Task 9.

- [ ] **Step 1: Write the implementation**

`H:\vscode\scpsl-autojoin\joiner.py`:
```python
"""Orchestrates one auto-join run: launch the game if needed, navigate to
Direct Connect, then retry until the log says success/give-up/unclear."""
import os
import time

import config as config_mod
import logwatch
import notify
import resolver
import winput

GAME_TITLE = "SCP: Secret Laboratory"
STEAM_URI = "steam://rungameid/700330"
MENU_CLICK_ORDER = ["play", "servers_tab", "internet_tab", "direct_connect"]
APP_NAME = "SCP:SL Auto-Joiner"


class JoinError(Exception):
    """Setup failure the caller should show and stop on."""


def ensure_game_running(watcher, launch_timeout=90):
    hwnd = winput.find_game_window(GAME_TITLE)
    if hwnd:
        return hwnd
    os.startfile(STEAM_URI)
    if not watcher.wait_for_marker(logwatch.MENU_MARK, launch_timeout):
        raise JoinError("Timed out waiting for SCP:SL to reach the main menu.")
    hwnd = winput.find_game_window(GAME_TITLE)
    if not hwnd:
        raise JoinError("Game launched but its window couldn't be found.")
    return hwnd


def click_with_fallback(hwnd, point, watcher, confirm_marker, confirm_timeout=5):
    """Click `point` via background PostMessage; if `confirm_marker` doesn't
    show up in the log within confirm_timeout, retry once via a
    focus-stealing SendInput click instead. Returns True if either click was
    confirmed."""
    x, y = point
    winput.post_click(hwnd, x, y)
    if watcher.wait_for_marker(confirm_marker, confirm_timeout):
        return True
    winput.focus_window(hwnd)
    winput.mouse_click(x, y)
    return watcher.wait_for_marker(confirm_marker, confirm_timeout)


def navigate_to_direct_connect(hwnd, cfg):
    points = cfg["click_points"]
    for name in MENU_CLICK_ORDER:
        winput.post_click(hwnd, *points[name])
        time.sleep(0.5)


def attempt_join(hwnd, cfg, ip, port, watcher):
    points = cfg["click_points"]
    winput.post_click(hwnd, *points["ip_field"])
    winput.post_text(hwnd, f"{ip}:{port}")
    if not click_with_fallback(hwnd, points["connect_button"], watcher,
                                confirm_marker=logwatch.CONNECTING_MARK):
        raise JoinError("Clicks aren't registering. Re-run calibration.")
    return watcher.wait_for_outcome(cfg["attempt_timeout_s"])


def run(server_name, on_status=None):
    """Blocking — call from a background thread, not the UI thread. Returns
    a final status string; on_status(str), if given, gets progress updates."""
    def status(msg):
        if on_status:
            on_status(msg)

    cfg = config_mod.load_config()
    if not config_mod.calibrated(cfg):
        notify.notify(APP_NAME, "Run calibration first (calibrate.py).")
        return "not_calibrated"

    match = resolver.resolve(server_name)
    if match is None:
        notify.notify(APP_NAME, f"No saved server matches '{server_name}'. Use Remember a server first.")
        return "not_found"
    name, ip, port = match

    watcher = logwatch.LogWatcher()
    try:
        status("Making sure SCP:SL is running...")
        try:
            hwnd = ensure_game_running(watcher)
        except JoinError as e:
            notify.notify(APP_NAME, str(e))
            return "launch_failed"

        status("Navigating to Direct Connect...")
        navigate_to_direct_connect(hwnd, cfg)

        unclear = 0
        attempts = 0
        deadline = time.monotonic() + cfg["max_minutes"] * 60
        while attempts < cfg["max_attempts"] and time.monotonic() < deadline:
            attempts += 1
            status(f"Attempt {attempts}: connecting to {name} ({ip}:{port})...")
            try:
                outcome = attempt_join(hwnd, cfg, ip, port, watcher)
            except JoinError as e:
                notify.notify(APP_NAME, str(e))
                return "unclear"

            if outcome == "success":
                notify.notify(APP_NAME, f"Joined {name}!")
                return "success"

            if outcome == "rejected":
                unclear = 0
                winput.post_key_tap(hwnd, winput.VK_ESCAPE)
                time.sleep(cfg["retry_interval_s"])
                continue

            unclear += 1
            if unclear >= cfg["max_unclear"]:
                notify.notify(APP_NAME, f"Stuck on an unclear result ({outcome}) — check the game.")
                return "unclear"
            winput.post_key_tap(hwnd, winput.VK_ESCAPE)
            time.sleep(cfg["retry_interval_s"])

        notify.notify(APP_NAME, f"Gave up trying to join {name}.")
        return "gave_up"
    finally:
        watcher.close()
```

- [ ] **Step 2: Verify manually against the real game**

With calibration already done (Task 6) and at least one server remembered (Task 8 adds the UI for this — for now, seed it directly):
```bash
cd "H:/vscode/scpsl-autojoin" && python -c "import resolver; resolver.remember_server('test', '<a real server ip you have>', 7777)"
python -c "import joiner; print(joiner.run('test', on_status=print))"
```
Expected: status lines print as it navigates and retries; ends in `success`, `gave_up`, or `unclear` matching what actually happened in the game, and a toast fires.

- [ ] **Step 3: Commit**

```bash
cd "H:/vscode/scpsl-autojoin"
git add joiner.py
git commit -m "Add driver loop orchestrating launch, navigation, and retries"
```

---

### Task 8: GUI

**Files:**
- Create: `H:\vscode\scpsl-autojoin\gui.py`

**Interfaces:**
- Consumes: `joiner.run` (Task 7); `logwatch.LogWatcher`, `logwatch.CONNECTING_IP_RE` (Task 2); `resolver.remember_server` (Task 3).
- Produces: `gui.App` (class), `gui.main() -> None`.

tkinter UI glue — no automated test (manual verification in Task 9).

- [ ] **Step 1: Write the implementation**

`H:\vscode\scpsl-autojoin\gui.py`:
```python
"""Tiny GUI: type a server name and hit Join, or click Remember a server to
learn a new one by watching your next manual in-game join attempt."""
import threading
import tkinter as tk
from tkinter import simpledialog

import joiner
import logwatch
import resolver


class App:
    def __init__(self, root):
        self.root = root
        root.title("SCP:SL Auto-Joiner")

        tk.Label(root, text="Server name:").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self.name_var = tk.StringVar()
        tk.Entry(root, textvariable=self.name_var, width=30).grid(row=0, column=1, padx=8, pady=8)

        tk.Button(root, text="Join", command=self.on_join).grid(row=1, column=0, padx=8, pady=4)
        tk.Button(root, text="Remember a server", command=self.on_remember).grid(
            row=1, column=1, padx=8, pady=4)

        self.status_var = tk.StringVar(value="Idle.")
        tk.Label(root, textvariable=self.status_var, wraplength=320, justify="left").grid(
            row=2, column=0, columnspan=2, padx=8, pady=8, sticky="w")

    def set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    # ── Join ─────────────────────────────────────────────────────────
    def on_join(self):
        name = self.name_var.get().strip()
        if not name:
            return
        threading.Thread(target=self._run_join, args=(name,), daemon=True).start()

    def _run_join(self, name):
        joiner.run(name, on_status=self.set_status)

    # ── Remember a server ────────────────────────────────────────────
    def on_remember(self):
        threading.Thread(target=self._run_remember, daemon=True).start()

    def _run_remember(self):
        self.set_status("Click Play on the server you want to remember, in the game...")
        watcher = logwatch.LogWatcher()
        try:
            m = watcher.wait_for_regex(logwatch.CONNECTING_IP_RE, 120)
        finally:
            watcher.close()
        if not m:
            self.set_status("Timed out waiting for a connection attempt.")
            return
        ip, port = m.group(1), int(m.group(2))
        self.root.after(0, lambda: self._prompt_and_save(ip, port))

    def _prompt_and_save(self, ip, port):
        name = simpledialog.askstring(
            "Remember server", f"Name this server ({ip}:{port}):", parent=self.root)
        if name and name.strip():
            resolver.remember_server(name.strip(), ip, port)
            self.status_var.set(f"Saved '{name.strip()}' -> {ip}:{port}")
        else:
            self.status_var.set("Cancelled.")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify manually**

Run: `cd "H:/vscode/scpsl-autojoin" && python gui.py`
- Click "Remember a server", then manually click Play on any server in the game — expect a name prompt, and a new entry in `servers.json` after saving.
- Type that name (or a close typo of it) into the field and click Join — expect status updates and the same behavior verified in Task 7.

- [ ] **Step 3: Commit**

```bash
cd "H:/vscode/scpsl-autojoin"
git add gui.py
git commit -m "Add GUI with join and remember-a-server flows"
```

---

### Task 9: Full end-to-end verification

**Files:** none created — this task exercises the assembled tool.

- [ ] **Step 1: Run the full automated test suite**

Run: `cd "H:/vscode/scpsl-autojoin" && python -m pytest tests/ -v`
Expected: all tests from Tasks 1-3 pass (14 total).

- [ ] **Step 2: Fresh-machine calibration check**

Delete `config.json` and `servers.json` if present, then run `python calibrate.py` followed by `python gui.py`, and go through Remember a server → Join against a real official server end to end (ideally one you can force full, e.g. try joining while it's near capacity, to see a real `rejected` retry cycle — otherwise a normal join still exercises the success path).
Expected: a toast fires on success, and — if you can find/wait for a full server — the status line shows repeated attempts before eventually getting in or giving up.

- [ ] **Step 3: Commit any fixes found during verification**

If Step 2 surfaces a bug (e.g. a click point that needs nudging, a timing value that's too tight), fix it in the relevant task's file and commit separately:
```bash
cd "H:/vscode/scpsl-autojoin"
git add -A
git commit -m "Fix issues found in end-to-end verification"
```

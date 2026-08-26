"""Orchestrates one auto-join run: launch the game if needed, navigate to
Direct Connect, then retry until the log says success/give-up/unclear."""
import os
import re
import threading
import time
import traceback
import winreg
from dataclasses import dataclass
from enum import Enum

import config as config_mod
import logwatch
import notify
import resolver
import server_store
import transport
import winput
from app_paths import app_dir

GAME_TITLE = "SCP: Secret Laboratory"
STEAM_URI = "steam://rungameid/700330"
APP_NAME = "SCP:SL Auto-Joiner"
ERROR_LOG_PATH = os.path.join(app_dir(), "autojoiner.log")
_RUN_LOCK = threading.Lock()

# Normalized centers from the SCP:SL fullscreen/borderless layout. Keeping
# these relative to the game window makes resolution and monitor position
# irrelevant; tune this table if the game changes its menu layout.
LAYOUT_POINTS = {
    "servers": (0.12, 0.05),
    # SCP:SL's 4K borderless UI is laid out in a 1920x1080 logical canvas
    # and scaled to the physical window. These centers are measured from the
    # shipped client rather than assuming the controls fill the window.
    "direct_connect": (0.525, 0.193),
    "address_field": (0.50, 0.49),
    "connect": (0.53, 0.55),
}


class JoinError(Exception):
    """Setup failure the caller should show and stop on."""


class JoinState(str, Enum):
    resolving = "resolving"
    launching = "launching"
    menu_ready = "menu_ready"
    connecting = "connecting"
    waiting = "waiting"
    rejected_or_unknown = "rejected_or_unknown"
    retrying = "retrying"
    joined = "joined"
    stopped = "stopped"
    failed = "failed"


@dataclass(frozen=True)
class GroupProgress:
    group_id: str
    server_id: str
    index: int
    total: int
    attempt: int
    state: str


def resolve_target(target_type, target_id):
    """Resolve an exact saved server or ordered group to server records."""
    store = server_store.load_store()
    servers = {server["id"]: server for server in store["servers"]}
    if target_type == "server":
        server = servers.get(target_id)
        return [dict(server)] if server else []
    if target_type == "group":
        group = next((item for item in store["groups"] if item["id"] == target_id), None)
        if group is None:
            return []
        return [dict(servers[server_id]) for server_id in group["server_ids"] if server_id in servers]
    return []


def _saved_group(group_id):
    store = server_store.load_store()
    return next((group for group in store["groups"] if group["id"] == group_id), None)


def _group_status(group_name, server, progress):
    suffix = "" if progress.state.endswith("...") else "."
    return (
        f"{group_name}: server {progress.index + 1} of {progress.total} "
        f"({server['name']}), attempt {progress.attempt}: {progress.state}{suffix}"
    )


def steam_root():
    """Return Steam's install directory from the current user's registry."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            return os.path.normpath(winreg.QueryValueEx(key, "SteamPath")[0])
    except OSError:
        return None


def steam_libraries(root=None):
    """Return every Steam library without depending on Steam's UI."""
    root = root or steam_root()
    if not root:
        return []
    libraries = [os.path.normpath(root)]
    vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
    try:
        with open(vdf, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        for value in re.findall(r'"path"\s+"([^"]+)"', text, re.IGNORECASE):
            path = os.path.normpath(value.replace(r"\\", "\\"))
            if path not in libraries:
                libraries.append(path)
    except OSError:
        pass
    return libraries


def find_game_executable(root=None):
    """Locate SCPSL.exe from Steam's library metadata."""
    for library in steam_libraries(root):
        steamapps = os.path.join(library, "steamapps")
        manifest = os.path.join(steamapps, "appmanifest_700330.acf")
        install_dir = "SCP Secret Laboratory"
        try:
            with open(manifest, "r", encoding="utf-8", errors="replace") as handle:
                match = re.search(r'"installdir"\s+"([^"]+)"', handle.read(), re.IGNORECASE)
            if match:
                install_dir = match.group(1).replace(r"\\", "\\")
        except OSError:
            pass
        executable = os.path.join(steamapps, "common", install_dir, "SCPSL.exe")
        if os.path.isfile(executable):
            return executable
    return None


def launch_game_connected(ip, port):
    """Launch SCP:SL directly with Steam auth and Northwood's +connect arg.

    Steam's ``steam://connect`` URL opens a Game Info window, while passing
    custom arguments through ``steam://run`` triggers a Steam confirmation.
    Launching the installed game with the exact ``-steam`` argument Steam
    normally uses avoids both dialogs; the live client still authenticates
    through Steam and honors ``+connect``.
    """
    executable = find_game_executable()
    if not executable:
        raise JoinError("Could not find SCP:SL in your Steam libraries.")
    return transport.launch_direct(executable, ip, port)


def wait_for_game_window(timeout=15, stop_event=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if stop_event and stop_event.is_set():
            return None
        hwnd = winput.find_game_window(GAME_TITLE)
        if hwnd:
            return hwnd
        time.sleep(0.25)
    return None


def ensure_game_running(watcher, launch_timeout=90, stop_event=None):
    hwnd = winput.find_game_window(GAME_TITLE)
    if hwnd:
        return hwnd
    os.startfile(STEAM_URI)
    if not watcher.wait_for_marker(logwatch.MENU_MARK, launch_timeout, stop_event=stop_event):
        raise JoinError("Timed out waiting for SCP:SL to reach the main menu.")
    hwnd = winput.find_game_window(GAME_TITLE)
    if not hwnd:
        raise JoinError("Game launched but its window couldn't be found.")
    return hwnd


def layout_point(hwnd, name):
    rect = winput.get_window_rect(hwnd)
    if not rect:
        raise JoinError("Could not read the SCP:SL window size.")
    left, top, right, bottom = rect
    x_ratio, y_ratio = LAYOUT_POINTS[name]
    return int(left + (right - left) * x_ratio), int(top + (bottom - top) * y_ratio)


def click_layout(hwnd, name, input_mode="background"):
    cfg = config_mod.load_config()
    manual_names = {
        "servers": "servers_tab",
        "direct_connect": "direct_connect",
        "address_field": "ip_field",
        "connect": "connect_button",
    }
    if cfg.get("navigation_mode") == "manual" and config_mod.calibrated(cfg) and name in manual_names:
        point = tuple(cfg["click_points"][manual_names[name]])
    else:
        point = layout_point(hwnd, name)
    if input_mode == "foreground":
        winput.foreground_click(hwnd, *point)
    else:
        # Target only SCP:SL's window-message queue. This leaves the
        # foreground app, physical cursor, and keyboard alone. Unity's new
        # Input System may ignore this path; connect_once then retries the
        # same attempt through the compatibility path.
        winput.post_click(hwnd, *point)
    return point


def navigate_to_direct_connect(hwnd, open_servers=True, input_mode="background"):
    """Open Direct Connect from News initially or from Servers on retries."""
    if open_servers:
        click_layout(hwnd, "servers", input_mode=input_mode)
        time.sleep(0.8)
    click_layout(hwnd, "direct_connect", input_mode=input_mode)
    time.sleep(0.8)


def prepare_direct_connect(hwnd, ip, port, open_servers=True, input_mode="background"):
    navigate_to_direct_connect(hwnd, open_servers=open_servers, input_mode=input_mode)
    click_layout(hwnd, "address_field", input_mode=input_mode)
    address = f"{ip}:{port}"
    if input_mode == "foreground":
        winput.foreground_replace_text(hwnd, address)
    else:
        winput.replace_text(hwnd, address)


class _ConnectionAttempt:
    """Adapts one join attempt's UI and log operations for ``transport``."""

    def __init__(self, hwnd, cfg, watcher, ip, port, open_servers, launch_direct, stop_event):
        self.hwnd = hwnd
        self.config = cfg
        self.watcher = watcher
        self.ip = ip
        self.port = port
        self.open_servers = open_servers
        self.game_running = not launch_direct
        self.stop_event = stop_event
        self.method = None
        self.connected = False

    def start_direct(self):
        launch_game_connected(self.ip, self.port)

    def start_steam(self):
        transport.launch_steam_connect(self.ip, self.port)

    def start_background(self):
        prepare_direct_connect(self.hwnd, self.ip, self.port, open_servers=self.open_servers)
        click_layout(self.hwnd, "connect")
        winput.post_key_tap(self.hwnd, winput.VK_RETURN)

    def start_foreground(self):
        prepare_direct_connect(
            self.hwnd, self.ip, self.port,
            open_servers=self.open_servers, input_mode="foreground",
        )
        click_layout(self.hwnd, "connect", input_mode="foreground")
        winput.foreground_key_tap(self.hwnd, winput.VK_RETURN)

    def wait_for_connecting(self):
        timeout = 90 if self.method == "direct" else 5
        return self.watcher.wait_for_marker(
            logwatch.CONNECTING_MARK, timeout, stop_event=self.stop_event,
        )

    def stopped(self):
        return bool(self.stop_event and self.stop_event.is_set())


def connect_once(hwnd, cfg, watcher, ip, port, open_servers=True,
                 launch_direct=False, stop_event=None):
    """Start one connection without global input, then read its result.

    A cold automatic start uses the game's supported ``+connect`` argument.
    Warm starts and retries post controls only to SCP:SL's window. Manual mode
    uses calibrated positions; automatic mode uses resolution-relative ones.
    """
    attempt = _ConnectionAttempt(
        hwnd, cfg, watcher, ip, port, open_servers, launch_direct, stop_event,
    )
    transport.connect_with_fallback(attempt)
    if attempt.stopped():
        return "stopped"
    if not attempt.connected:
        if attempt.method == "direct":
            raise JoinError("SCP:SL launched but did not start the direct connection.")
        raise JoinError("SCP:SL did not start connecting. Check the game window and calibration.")
    return watcher.wait_for_outcome(cfg["attempt_timeout_s"], stop_event=stop_event)


def dismiss_connection_overlay(hwnd):
    """Close SCP:SL's server-full/disconnect overlay before retrying."""
    if not hwnd:
        return
    # Automatic mode must never move the cursor or activate SCP:SL. The
    # explicit foreground connection method remains available for users who
    # choose it in Settings.
    winput.post_key_tap(hwnd, winput.VK_ESCAPE)


def wait_for_retry_delay(delay, stop_event=None):
    """Wait between retries without delaying a requested stop."""
    if stop_event:
        return stop_event.wait(delay)
    time.sleep(delay)
    return False


def run_group(group_id, on_status=None, stop_event=None):
    """Run an ordered saved-server group until joined, stopped, or limited."""
    def status(msg):
        if on_status:
            on_status(msg)

    if not _RUN_LOCK.acquire(blocking=False):
        status("An auto-join run is already active.")
        return "already_running"

    watcher = None
    try:
        group = _saved_group(group_id)
        if group is None:
            status(f"No saved group matches '{group_id}'.")
            return "not_found"
        servers = resolve_target("group", group_id)
        if not servers:
            status(f"Saved group '{group['name']}' has no servers.")
            return "empty_group"
        if stop_event and stop_event.is_set():
            status("Stop requested.")
            return "stopped"

        winput.set_dpi_awareness()
        cfg = config_mod.load_config()
        watcher = logwatch.LogWatcher()
        hwnd = winput.find_game_window(GAME_TITLE)
        cold_direct = transport.choose_method(cfg, game_running=bool(hwnd)) == "direct"
        if cold_direct:
            status(f"Launching SCP:SL for group '{group['name']}'...")
        else:
            status("Making sure SCP:SL is running...")
            try:
                hwnd = ensure_game_running(watcher, stop_event=stop_event)
            except JoinError as e:
                if stop_event and stop_event.is_set():
                    return "stopped"
                notify.notify(APP_NAME, str(e))
                return "launch_failed"

        attempts = 0
        max_attempts = int(cfg["max_attempts"])
        max_minutes = int(cfg["max_minutes"])
        deadline = None if max_minutes == 0 else time.monotonic() + max_minutes * 60
        index = 0
        unclear = [0] * len(servers)
        while (
            (max_attempts == 0 or attempts < max_attempts)
            and (deadline is None or time.monotonic() < deadline)
        ):
            if stop_event and stop_event.is_set():
                status("Stop requested.")
                return "stopped"

            server = servers[index]
            attempts += 1
            progress = GroupProgress(group_id, server["id"], index, len(servers), attempts, "connecting...")
            status(_group_status(group["name"], server, progress))
            try:
                outcome = connect_once(
                    hwnd, cfg, watcher, server["ip"], server["port"],
                    open_servers=(attempts == 1),
                    launch_direct=(attempts == 1 and cold_direct),
                    stop_event=stop_event,
                )
            except JoinError:
                outcome = "unclear"

            if outcome == "success":
                notify.notify(APP_NAME, f"Joined {server['name']}!")
                return "success"
            if outcome == "stopped" or (stop_event and stop_event.is_set()):
                status("Stop requested.")
                return "stopped"

            if outcome in ("rejected", "cancelled", "rejected_or_unknown", "disconnected", "timeout"):
                reason = outcome
            else:
                unclear[index] += 1
                if unclear[index] < cfg["max_unclear"]:
                    winput.post_key_tap(hwnd, winput.VK_ESCAPE)
                    if wait_for_retry_delay(cfg["retry_interval_s"], stop_event):
                        status("Stop requested.")
                        return "stopped"
                    continue
                reason = f"unclear result ({outcome})"

            progress = GroupProgress(
                group_id, server["id"], index, len(servers), attempts,
                f"advancing after {reason}",
            )
            status(_group_status(group["name"], server, progress))
            unclear[index] = 0
            if hwnd is None:
                hwnd = wait_for_game_window(stop_event=stop_event)
                if hwnd is None:
                    notify.notify(APP_NAME, "SCP:SL is running, but its window could not be found for the next server.")
                    return "unclear"
            dismiss_connection_overlay(hwnd)
            if wait_for_retry_delay(cfg["retry_interval_s"], stop_event):
                status("Stop requested.")
                return "stopped"
            if index == len(servers) - 1 and not cfg.get("group_loop", True):
                notify.notify(APP_NAME, f"Finished one pass through group '{group['name']}'.")
                return "gave_up"
            index = (index + 1) % len(servers)

        notify.notify(APP_NAME, f"Gave up trying to join group '{group['name']}'.")
        return "gave_up"
    except Exception:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        notify.notify(APP_NAME, "Auto-joiner crashed; check autojoiner.log.")
        return "unclear"
    finally:
        if watcher is not None:
            watcher.close()
        _RUN_LOCK.release()


def run(server_name, on_status=None, stop_event=None):
    """Blocking — call from a background thread, not the UI thread. Returns
    a final status string; on_status(str), if given, gets progress updates."""
    def status(msg):
        if on_status:
            on_status(msg)

    if not _RUN_LOCK.acquire(blocking=False):
        status("An auto-join run is already active.")
        return "already_running"

    watcher = None
    try:
        # The GUI sets this at import time, but the joiner is also used by
        # tests and direct CLI/debug launches.  Without per-monitor DPI
        # awareness Windows virtualizes GetWindowRect/ScreenToClient and a
        # 4K borderless window receives clicks at 1080p-scaled positions.
        winput.set_dpi_awareness()
        cfg = config_mod.load_config()
        match = resolver.resolve(server_name)
        if match is None:
            notify.notify(APP_NAME, f"No saved server matches '{server_name}'. Use Remember a server first.")
            return "not_found"
        name, ip, port = match

        watcher = logwatch.LogWatcher()
        hwnd = winput.find_game_window(GAME_TITLE)
        cold_direct = transport.choose_method(cfg, game_running=bool(hwnd)) == "direct"
        if cold_direct:
            status(f"Launching SCP:SL and connecting to {name}...")
        else:
            status("Making sure SCP:SL is running...")
            try:
                hwnd = ensure_game_running(watcher, stop_event=stop_event)
            except JoinError as e:
                if stop_event and stop_event.is_set():
                    return "stopped"
                notify.notify(APP_NAME, str(e))
                return "launch_failed"

        unclear = 0
        attempts = 0
        max_attempts = int(cfg["max_attempts"])
        max_minutes = int(cfg["max_minutes"])
        deadline = None if max_minutes == 0 else time.monotonic() + max_minutes * 60
        while (
            (max_attempts == 0 or attempts < max_attempts)
            and (deadline is None or time.monotonic() < deadline)
        ):
            if stop_event and stop_event.is_set():
                status("Stop requested.")
                return "stopped"
            attempts += 1
            status(f"Attempt {attempts}: connecting to {name} ({ip}:{port})...")
            try:
                outcome = connect_once(
                    hwnd, cfg, watcher, ip, port,
                    open_servers=(attempts == 1),
                    launch_direct=(attempts == 1 and cold_direct),
                    stop_event=stop_event,
                )
            except JoinError as e:
                notify.notify(APP_NAME, str(e))
                return "unclear"

            if outcome == "success":
                notify.notify(APP_NAME, f"Joined {name}!")
                return "success"

            if outcome == "stopped":
                status("Stop requested.")
                return "stopped"

            if stop_event and stop_event.is_set():
                status("Stop requested.")
                return "stopped"

            if outcome in ("rejected", "cancelled", "rejected_or_unknown", "disconnected"):
                unclear = 0
                if hwnd is None:
                    hwnd = wait_for_game_window(stop_event=stop_event)
                    if hwnd is None:
                        notify.notify(APP_NAME, "SCP:SL is running, but its window could not be found for the retry.")
                        return "unclear"
                dismiss_connection_overlay(hwnd)
                delay = cfg["retry_interval_s"]
                unit = "second" if delay == 1 else "seconds"
                status(f"Server rejected/full-or-unknown. Retrying in {delay} {unit}...")
                if wait_for_retry_delay(delay, stop_event):
                    status("Stop requested.")
                    return "stopped"
                continue

            unclear += 1
            if unclear >= cfg["max_unclear"]:
                notify.notify(APP_NAME, f"Stuck on an unclear result ({outcome}) — check the game.")
                return "unclear"
            winput.post_key_tap(hwnd, winput.VK_ESCAPE)
            if wait_for_retry_delay(cfg["retry_interval_s"], stop_event):
                status("Stop requested.")
                return "stopped"

        notify.notify(APP_NAME, f"Gave up trying to join {name}.")
        return "gave_up"
    except Exception:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        notify.notify(APP_NAME, "Auto-joiner crashed; check autojoiner.log.")
        return "unclear"
    finally:
        if watcher is not None:
            watcher.close()
        _RUN_LOCK.release()

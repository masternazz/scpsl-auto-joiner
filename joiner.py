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
    "direct_connect": (0.44, 0.193),
    "address_field": (0.50, 0.49),
    "connect": (0.53, 0.55),
}


def client_point(client_rect, local_point, saved_size):
    """Map a captured client-local point onto the current client rectangle."""
    left, top, right, bottom = client_rect
    saved_width, saved_height = saved_size
    if saved_width <= 0 or saved_height <= 0:
        raise JoinError("Saved calibration has no valid client size.")
    x, y = local_point
    width, height = right - left, bottom - top
    return (
        int(left + x * width / saved_width),
        int(top + y * height / saved_height),
    )


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


class UIPhase(str, Enum):
    """Observable SCP:SL menu phase used by the retry state machine."""
    servers_page = "servers_page"
    direct_connect_open = "direct_connect_open"
    connecting = "connecting"
    disconnected = "disconnected"
    retry_ready = "retry_ready"
    joined = "joined"
    unknown = "unknown"


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
    rect = winput.get_client_rect(hwnd) or winput.get_window_rect(hwnd)
    if not rect:
        raise JoinError("Could not read the SCP:SL window size.")
    left, top, right, bottom = rect
    x_ratio, y_ratio = LAYOUT_POINTS[name]
    return int(left + (right - left) * x_ratio), int(top + (bottom - top) * y_ratio)


def calculated_click_points(hwnd):
    """Return the exact native screen targets currently used by automation."""
    return {name: layout_point(hwnd, name) for name in LAYOUT_POINTS}


def click_layout(hwnd, name, input_mode="background"):
    cfg = config_mod.load_config()
    manual_names = {
        "servers": "servers_tab",
        "direct_connect": "direct_connect",
        "address_field": "ip_field",
        "connect": "connect_button",
    }
    if cfg.get("navigation_mode") == "manual" and config_mod.calibrated(cfg) and name in manual_names:
        point_name = manual_names[name]
        client_points = cfg.get("client_click_points", {})
        saved_size = cfg.get("calibration_client_size", [0, 0])
        client_rect = winput.get_client_rect(hwnd)
        if point_name in client_points and client_rect and saved_size != [0, 0]:
            point = client_point(client_rect, client_points[point_name], saved_size)
        else:
            point = tuple(cfg["click_points"][point_name])
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


def prepare_direct_connect(hwnd, ip, port, open_servers=True, input_mode="background", open_dialog=True):
    """Fill Direct Connect.

    ``open_dialog=False`` is deliberately a separate path: after a rejected
    connection SCP:SL commonly leaves Direct Connect available. Retrying from
    that dialog must not click any Servers-page coordinate underneath it.
    """
    if open_dialog:
        navigate_to_direct_connect(hwnd, open_servers=open_servers, input_mode=input_mode)
    click_layout(hwnd, "address_field", input_mode=input_mode)
    address = f"{ip}:{port}"
    if input_mode == "foreground":
        winput.foreground_replace_text(hwnd, address)
    else:
        winput.replace_text(hwnd, address)


class _ConnectionAttempt:
    """Adapts one join attempt's UI and log operations for ``transport``."""

    def __init__(self, hwnd, cfg, watcher, ip, port, open_servers, launch_direct, stop_event,
                 reuse_dialog=False, on_status=None):
        self.hwnd = hwnd
        self.config = cfg
        self.watcher = watcher
        self.ip = ip
        self.port = port
        self.open_servers = open_servers
        self.game_running = not launch_direct
        self.stop_event = stop_event
        self.reuse_dialog = reuse_dialog
        self.on_status = on_status
        self.method = None
        self.connected = False

    def status(self, message):
        if self.on_status:
            self.on_status(message)

    def start_direct(self):
        launch_game_connected(self.ip, self.port)

    def start_steam(self):
        transport.launch_steam_connect(self.ip, self.port)

    def start_background(self):
        prepare_direct_connect(
            self.hwnd, self.ip, self.port,
            open_servers=self.open_servers, open_dialog=not self.reuse_dialog,
        )
        click_layout(self.hwnd, "connect")
        winput.post_key_tap(self.hwnd, winput.VK_RETURN)

    def start_foreground(self):
        prepare_direct_connect(
            self.hwnd, self.ip, self.port,
            open_servers=self.open_servers, input_mode="foreground",
            open_dialog=not self.reuse_dialog,
        )
        click_layout(self.hwnd, "connect", input_mode="foreground")
        winput.foreground_key_tap(self.hwnd, winput.VK_RETURN)

    def recover_foreground(self):
        """Dismiss the failure overlay before reopening Direct Connect."""
        if self.method == "foreground":
            winput.foreground_key_tap(self.hwnd, winput.VK_ESCAPE)
        else:
            winput.post_key_tap(self.hwnd, winput.VK_ESCAPE)

    def reopen_direct_connect(self):
        """Safely reopen Direct Connect without touching the Servers tab."""
        self.status("Reopening Direct Connect after dialog recovery.")
        self.reuse_dialog = False
        self.recover_foreground()
        if self.method == "foreground":
            self.start_foreground()
        else:
            self.start_background()

    def wait_for_connecting(self):
        timeout = 90 if self.method == "direct" else 5
        return self.watcher.wait_for_marker(
            logwatch.CONNECTING_MARK, timeout, stop_event=self.stop_event,
        )

    def stopped(self):
        return bool(self.stop_event and self.stop_event.is_set())


def connect_once(hwnd, cfg, watcher, ip, port, open_servers=True,
                 launch_direct=False, stop_event=None, reuse_dialog=False,
                 on_status=None):
    """Start one connection without global input, then read its result.

    Automatic starts use the recorded menu flow. The explicit Direct setting
    uses the game's supported ``+connect`` argument. Warm starts and retries
    target only SCP:SL's window; manual mode uses calibrated positions and
    automatic mode uses resolution-relative ones.
    """
    attempt = _ConnectionAttempt(
        hwnd, cfg, watcher, ip, port, open_servers, launch_direct, stop_event,
        reuse_dialog=reuse_dialog, on_status=on_status,
    )
    if reuse_dialog:
        attempt.status("Reusing Direct Connect dialog.")
        attempt.status(f"UI phase: {UIPhase.retry_ready.value}")
        dismiss_connection_overlay(hwnd, retry_input_mode(cfg))
    transport.connect_with_fallback(attempt)
    if attempt.stopped():
        return "stopped"
    if not attempt.connected and reuse_dialog:
        # ``transport`` has already tested the existing dialog. A missing
        # Connecting marker means the overlay consumed the action or the
        # dialog was closed, so recover once and reopen Direct Connect.
        attempt.status(f"UI phase: {UIPhase.unknown.value}")
        attempt.reopen_direct_connect()
        attempt.connected = attempt.wait_for_connecting()

    if not attempt.connected:
        if attempt.method == "direct":
            raise JoinError("SCP:SL launched but did not start the direct connection.")
        if attempt.method == "foreground":
            raise JoinError("SCP:SL did not start the foreground connection; check the game window and controls.")
        raise JoinError(
            "SCP:SL ignored background GUI input. Automatic mode will not take control of your mouse; choose Foreground explicitly for this client or report the SCP:SL version."
        )
    attempt.status(f"UI phase: {UIPhase.connecting.value}")
    outcome = watcher.wait_for_outcome(cfg["attempt_timeout_s"], stop_event=stop_event)
    if outcome == "success":
        attempt.status(f"UI phase: {UIPhase.joined.value}")
    elif outcome in ("disconnected", "rejected_or_unknown"):
        attempt.status(f"UI phase: {UIPhase.disconnected.value}")
    elif outcome != "stopped":
        attempt.status(f"UI phase: {UIPhase.unknown.value}")
    return outcome


def dismiss_connection_overlay(hwnd, input_mode="background"):
    """Close SCP:SL's server-full/disconnect overlay before retrying."""
    if not hwnd:
        return
    if input_mode == "foreground":
        winput.foreground_key_tap(hwnd, winput.VK_ESCAPE)
    else:
        winput.post_key_tap(hwnd, winput.VK_ESCAPE)


def retry_input_mode(cfg):
    """Return the input path used to dismiss a failed connection overlay."""
    return "foreground" if cfg.get("connection_method", "background") == "foreground" else "background"


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
        # Automatic mode follows the recorded client flow even on a cold
        # start: launch the game to its menu, then use Servers → Direct
        # Connect. The explicit Direct setting is the only +connect path.
        cold_direct = cfg.get("connection_method") == "direct" and not hwnd
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
        dialog_open = False
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
            if attempts == 1:
                status(f"UI phase: {UIPhase.servers_page.value}")
                status(f"UI phase: {UIPhase.direct_connect_open.value}")
            try:
                args = (
                    hwnd, cfg, watcher, server["ip"], server["port"],
                )
                options = dict(
                    open_servers=(attempts == 1),
                    launch_direct=(attempts == 1 and cold_direct),
                    stop_event=stop_event,
                )
                if attempts > 1:
                    options["reuse_dialog"] = dialog_open
                    options["on_status"] = status
                outcome = connect_once(*args, **options)
            except JoinError:
                outcome = "unclear"

            dialog_open = outcome != "success"

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
        # Automatic mode must use the same visible menu flow on every
        # machine; reserve the command-line path for an explicit preference.
        cold_direct = cfg.get("connection_method") == "direct" and not hwnd
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
        dialog_open = False
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
            if attempts == 1:
                status(f"UI phase: {UIPhase.servers_page.value}")
                status(f"UI phase: {UIPhase.direct_connect_open.value}")
            try:
                args = (hwnd, cfg, watcher, ip, port)
                options = dict(
                    open_servers=(attempts == 1),
                    launch_direct=(attempts == 1 and cold_direct),
                    stop_event=stop_event,
                )
                if attempts > 1:
                    options["reuse_dialog"] = dialog_open
                    options["on_status"] = status
                outcome = connect_once(*args, **options)
            except JoinError as e:
                # A background Unity interaction can be missed without the
                # game being broken. Treat it as a transient attempt failure
                # so the configured retry policy gets a chance to recover.
                outcome = "unclear"
                status(f"Could not confirm the connection start ({e}). Retrying...")

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
                dialog_open = True
                delay = cfg["retry_interval_s"]
                unit = "second" if delay == 1 else "seconds"
                if outcome in ("rejected_or_unknown", "rejected", "cancelled"):
                    status("Disconnected/full response detected.")
                else:
                    status("Disconnected response detected.")
                status(f"Retrying in {delay} {unit}...")
                if wait_for_retry_delay(delay, stop_event):
                    status("Stop requested.")
                    return "stopped"
                continue

            unclear += 1
            if unclear >= cfg["max_unclear"]:
                notify.notify(APP_NAME, f"Stuck on an unclear result ({outcome}) — check the game.")
                return "unclear"
            dialog_open = True
            status(f"UI phase: {UIPhase.unknown.value}")
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

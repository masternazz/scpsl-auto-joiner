"""Orchestrates one auto-join run: launch the game if needed, navigate to
Direct Connect, then retry until the log says success/give-up/unclear."""
import os
import time
import traceback

import config as config_mod
import logwatch
import notify
import resolver
import winput
from app_paths import app_dir

GAME_TITLE = "SCP: Secret Laboratory"
STEAM_URI = "steam://rungameid/700330"
APP_NAME = "SCP:SL Auto-Joiner"
ERROR_LOG_PATH = os.path.join(app_dir(), "autojoiner.log")

# Normalized centers from the SCP:SL fullscreen/borderless layout. Keeping
# these relative to the game window makes resolution and monitor position
# irrelevant; tune this table if the game changes its menu layout.
LAYOUT_POINTS = {
    "servers": (0.12, 0.05),
    "direct_connect": (0.49, 0.18),
    "address_field": (0.59, 0.51),
    "connect": (0.63, 0.58),
}


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


def layout_point(hwnd, name):
    rect = winput.get_window_rect(hwnd)
    if not rect:
        raise JoinError("Could not read the SCP:SL window size.")
    left, top, right, bottom = rect
    x_ratio, y_ratio = LAYOUT_POINTS[name]
    return int(left + (right - left) * x_ratio), int(top + (bottom - top) * y_ratio)


def click_layout(hwnd, name):
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
    winput.focus_window(hwnd)
    winput.mouse_click(*point)
    return point


def navigate_to_direct_connect(hwnd, _cfg):
    """Navigate using coordinates relative to the current game window."""
    click_layout(hwnd, "servers")
    time.sleep(0.8)
    click_layout(hwnd, "direct_connect")
    time.sleep(0.8)


def attempt_join(hwnd, cfg, ip, port, watcher):
    navigate_to_direct_connect(hwnd, cfg)
    field = layout_point(hwnd, "address_field")
    winput.focus_window(hwnd)
    winput.mouse_click(*field)
    winput.post_text(hwnd, f"{ip}:{port}")
    connect = layout_point(hwnd, "connect")
    winput.mouse_click(*connect)
    if not watcher.wait_for_marker(logwatch.CONNECTING_MARK, 5):
        raise JoinError("SCP:SL did not start connecting. Check the game layout.")
    return watcher.wait_for_outcome(cfg["attempt_timeout_s"])


def run(server_name, on_status=None, stop_event=None):
    """Blocking — call from a background thread, not the UI thread. Returns
    a final status string; on_status(str), if given, gets progress updates."""
    def status(msg):
        if on_status:
            on_status(msg)

    watcher = None
    try:
        cfg = config_mod.load_config()
        match = resolver.resolve(server_name)
        if match is None:
            notify.notify(APP_NAME, f"No saved server matches '{server_name}'. Use Remember a server first.")
            return "not_found"
        name, ip, port = match

        watcher = logwatch.LogWatcher()
        status("Making sure SCP:SL is running...")
        already_running = bool(winput.find_game_window(GAME_TITLE))
        try:
            hwnd = ensure_game_running(watcher)
        except JoinError as e:
            notify.notify(APP_NAME, str(e))
            return "launch_failed"

        status("Finding SCP:SL controls automatically...")
        navigate_to_direct_connect(hwnd, cfg)

        unclear = 0
        attempts = 0
        deadline = time.monotonic() + cfg["max_minutes"] * 60
        while attempts < cfg["max_attempts"] and time.monotonic() < deadline:
            if stop_event and stop_event.is_set():
                status("Stop requested.")
                return "stopped"
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

            if stop_event and stop_event.is_set():
                status("Stop requested.")
                return "stopped"

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
    except Exception:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        notify.notify(APP_NAME, "Auto-joiner crashed; check autojoiner.log.")
        return "unclear"
    finally:
        if watcher is not None:
            watcher.close()

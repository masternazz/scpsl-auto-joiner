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
MENU_CLICK_ORDER = ["play", "servers_tab", "internet_tab", "direct_connect"]
APP_NAME = "SCP:SL Auto-Joiner"
ERROR_LOG_PATH = os.path.join(app_dir(), "autojoiner.log")


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


def run(server_name, on_status=None, stop_event=None):
    """Blocking — call from a background thread, not the UI thread. Returns
    a final status string; on_status(str), if given, gets progress updates."""
    def status(msg):
        if on_status:
            on_status(msg)

    watcher = None
    try:
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
        status("Making sure SCP:SL is running...")
        already_running = bool(winput.find_game_window(GAME_TITLE))
        try:
            hwnd = ensure_game_running(watcher)
        except JoinError as e:
            notify.notify(APP_NAME, str(e))
            return "launch_failed"

        if already_running:
            status("Using the existing SCP:SL window at Direct Connect...")
        else:
            status("Navigating to Direct Connect...")
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

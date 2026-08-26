"""Persisted settings for the auto-joiner: retry tuning + calibrated click
points. See docs/superpowers/specs/2026-08-24-scpsl-autojoin-design.md."""
import copy
import json
import os
import sys

from app_paths import app_dir

CONFIG_PATH = os.path.join(app_dir(), "config.json")
CONFIG_VERSION = 5

DEFAULTS = {
    "config_version": CONFIG_VERSION,
    "navigation_mode": "automatic",
    "connection_method": "automatic",
    "group_loop": True,
    "browser_refresh_timeout_s": 2,
    "onboarding_complete": False,
    "notifications_enabled": True,
    # Qt 6 reports cursor positions in DPI-scaled logical pixels. Version 2
    # calibration records native Win32 physical pixels so the coordinates
    # match GetWindowRect/SendInput on 4K displays.
    "calibration_space": None,
    "calibration_client_size": [0, 0],
    "client_click_points": {},
    "retry_interval_s": 2,
    "attempt_timeout_s": 20,
    "max_unclear": 3,
    "max_attempts": 100,
    "max_minutes": 30,
    "auto_update": False,
    "accent": "violet",
    "custom_accent": "#b186ff",
    "click_points": {
        "play": [0, 0],
        "servers_tab": [0, 0],
        "internet_tab": [0, 0],
        "direct_connect": [0, 0],
        "ip_field": [0, 0],
        "connect_button": [0, 0],
    },
}

REQUIRED_CLICK_POINTS = ("servers_tab", "direct_connect", "ip_field", "connect_button")


def load_config(path=None):
    path = path or CONFIG_PATH
    if not os.path.exists(path):
        # v1-v4 portable builds kept config beside the executable. Preserve
        # that data when the app moves to the canonical LocalAppData store.
        legacy_paths = []
        if path == CONFIG_PATH:
            legacy_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"))
            if getattr(sys, "frozen", False):
                legacy_paths.append(os.path.join(os.path.dirname(sys.executable), "config.json"))
        for legacy in legacy_paths:
            if os.path.isfile(legacy) and os.path.abspath(legacy) != os.path.abspath(path):
                try:
                    with open(legacy, encoding="utf-8") as f:
                        data = json.load(f)
                    merged = copy.deepcopy(DEFAULTS)
                    merged.update({k: v for k, v in data.items() if k != "click_points"})
                    merged["click_points"].update(data.get("click_points", {}))
                    merged["config_version"] = CONFIG_VERSION
                    save_config(merged, path)
                    return merged
                except (OSError, ValueError, TypeError):
                    pass
        save_config(DEFAULTS, path)
        return copy.deepcopy(DEFAULTS)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    merged = copy.deepcopy(DEFAULTS)
    # Update top-level keys except click_points (which needs dict merging)
    for key, value in data.items():
        if key != "click_points":
            merged[key] = value
    # Merge saved click_points into the deepcopied defaults
    if "click_points" in data:
        merged["click_points"].update(data["click_points"])
    saved_version = int(data.get("config_version", 1))
    if saved_version < CONFIG_VERSION:
        # Version 1 shipped with a six-second default. Preserve custom values,
        # but migrate that old default for existing users.
        if data.get("retry_interval_s", 6) == 6:
            merged["retry_interval_s"] = 2
        # Version 3 replaces menu automation with Northwood's supported Steam
        # Direct Connect URI. Move old installs to that no-input default once;
        # an explicit fallback choice made on v3 remains untouched.
        if saved_version < 3:
            merged["navigation_mode"] = "automatic"
        merged["config_version"] = CONFIG_VERSION
        save_config(merged, path)
    return merged


def save_config(cfg, path=None):
    path = path or CONFIG_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def calibrated(cfg):
    return (
        cfg.get("calibration_space") == "physical_v2"
        and all(tuple(cfg["click_points"].get(name, (0, 0))) != (0, 0) for name in REQUIRED_CLICK_POINTS)
    )

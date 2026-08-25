"""Persisted settings for the auto-joiner: retry tuning + calibrated click
points. See docs/superpowers/specs/2026-08-24-scpsl-autojoin-design.md."""
import copy
import json
import os

from app_paths import app_dir

CONFIG_PATH = os.path.join(app_dir(), "config.json")

DEFAULTS = {
    "navigation_mode": "automatic",
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
    return merged


def save_config(cfg, path=None):
    path = path or CONFIG_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def calibrated(cfg):
    return all(tuple(v) != (0, 0) for v in cfg["click_points"].values())

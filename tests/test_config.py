import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config as config_mod


def test_load_config_creates_defaults_when_missing(tmp_path):
    path = str(tmp_path / "config.json")
    cfg = config_mod.load_config(path)
    assert os.path.exists(path)
    assert cfg["retry_interval_s"] == 2
    assert cfg["click_points"]["play"] == [0, 0]


def test_load_config_merges_saved_values(tmp_path):
    path = str(tmp_path / "config.json")
    config_mod.save_config(
        {"retry_interval_s": 9, "click_points": {"play": [12, 34]}}, path)
    cfg = config_mod.load_config(path)
    assert cfg["retry_interval_s"] == 9
    assert cfg["click_points"]["play"] == [12, 34]
    assert cfg["click_points"]["servers_tab"] == [0, 0]


def test_load_config_migrates_old_retry_delay_to_two_seconds(tmp_path):
    path = str(tmp_path / "config.json")
    config_mod.save_config({"retry_interval_s": 6, "click_points": {}}, path)

    cfg = config_mod.load_config(path)

    assert cfg["config_version"] == 5
    assert cfg["retry_interval_s"] == 2


def test_version_two_manual_mode_migrates_to_no_input_steam_mode(tmp_path):
    path = str(tmp_path / "config.json")
    config_mod.save_config({
        "config_version": 2,
        "navigation_mode": "manual",
        "click_points": {},
    }, path)

    cfg = config_mod.load_config(path)

    assert cfg["config_version"] == 5
    assert cfg["navigation_mode"] == "automatic"


def test_version_three_explicit_fallback_choice_is_preserved(tmp_path):
    path = str(tmp_path / "config.json")
    config_mod.save_config({
        "config_version": 3,
        "navigation_mode": "manual",
        "click_points": {},
    }, path)

    assert config_mod.load_config(path)["navigation_mode"] == "manual"


def test_version_three_config_migrates_task_six_defaults_without_losing_preferences(tmp_path):
    """A v3 upgrade keeps user choices while adding Task 6's new controls.

    Removing any of the migration assignments should make this test fail: it
    protects the installed users' updater preference, accent, and calibrated
    fallback rather than merely checking config source text.
    """
    path = str(tmp_path / "config.json")
    config_mod.save_config({
        "config_version": 3,
        "navigation_mode": "manual",
        "calibration_space": "physical_v2",
        "retry_interval_s": 9,
        "attempt_timeout_s": 45,
        "max_attempts": 0,
        "max_minutes": 0,
        "auto_update": True,
        "accent": "cyan",
        "click_points": {
            "servers_tab": [200, 100],
            "direct_connect": [980, 360],
            "ip_field": [1180, 1020],
            "connect_button": [1260, 1160],
        },
    }, path)

    cfg = config_mod.load_config(path)

    assert cfg["config_version"] == 5
    assert cfg["connection_method"] == "automatic"
    assert cfg["group_loop"] is True
    assert cfg["browser_refresh_timeout_s"] == 2
    assert cfg["onboarding_complete"] is False
    assert cfg["navigation_mode"] == "manual"
    assert cfg["calibration_space"] == "physical_v2"
    assert cfg["click_points"]["connect_button"] == [1260, 1160]
    assert cfg["retry_interval_s"] == 9
    assert cfg["attempt_timeout_s"] == 45
    assert cfg["max_attempts"] == 0
    assert cfg["max_minutes"] == 0
    assert cfg["auto_update"] is True
    assert cfg["accent"] == "cyan"


def test_calibrated_false_until_all_points_set(tmp_path):
    path = str(tmp_path / "config.json")
    cfg = config_mod.load_config(path)
    assert config_mod.calibrated(cfg) is False
    for k in cfg["click_points"]:
        cfg["click_points"][k] = [1, 1]
    cfg["calibration_space"] = "physical_v2"
    assert config_mod.calibrated(cfg) is True


def test_legacy_dpi_scaled_calibration_is_not_used(tmp_path):
    cfg = config_mod.load_config(str(tmp_path / "config.json"))
    for key in config_mod.REQUIRED_CLICK_POINTS:
        cfg["click_points"][key] = [500, 300]
    assert config_mod.calibrated(cfg) is False


def test_load_config_no_shared_mutable_defaults(tmp_path):
    """Verify that mutating a loaded config doesn't corrupt module DEFAULTS.

    This test exercises the partial-merge path: save a config missing some
    click_points keys, load it (which fills missing keys from DEFAULTS under
    the buggy code), mutate one in place, and load again to verify DEFAULTS
    wasn't corrupted.
    """
    path = str(tmp_path / "config.json")
    # Save a PARTIAL config (only "play" click_point, others are absent)
    config_mod.save_config(
        {"retry_interval_s": 9, "click_points": {"play": [12, 34]}}, path)

    # Load it; under buggy code, missing keys like "servers_tab" come from DEFAULTS list objects
    cfg1 = config_mod.load_config(path)
    assert cfg1["click_points"]["servers_tab"] == [0, 0]

    # Mutate a missing-from-save key in place (this would corrupt DEFAULTS under buggy code)
    cfg1["click_points"]["servers_tab"][0] = 999
    assert cfg1["click_points"]["servers_tab"] == [999, 0]

    # Load again from the same partial file
    cfg2 = config_mod.load_config(path)
    # Fresh config must still have default [0, 0], not the mutated [999, 0]
    assert cfg2["click_points"]["servers_tab"] == [0, 0]
    # And module DEFAULTS itself must never be mutated
    assert config_mod.DEFAULTS["click_points"]["servers_tab"] == [0, 0]

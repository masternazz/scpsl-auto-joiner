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

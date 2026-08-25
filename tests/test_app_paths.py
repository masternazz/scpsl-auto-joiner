import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app_paths


def test_app_dir_always_uses_local_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    path = app_paths.app_dir()

    assert path == str(tmp_path / "SCP-SL-Auto-Joiner")
    assert os.path.isdir(path)

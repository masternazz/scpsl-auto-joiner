import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import notify


def test_notifications_setting_suppresses_native_toast(monkeypatch):
    """Turning off the Task 6 preference must prevent the toast side effect."""
    sent = []
    monkeypatch.setattr(notify.config_mod, "load_config", lambda: {"notifications_enabled": False})
    monkeypatch.setattr(notify, "toast", lambda title, message: sent.append((title, message)))

    notify.notify("SCP:SL", "Joined")

    assert sent == []

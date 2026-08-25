import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import winput


def test_scpsl_unity_window_matches_even_when_display_title_differs():
    assert winput._is_game_window("SCPSL", "UnityWndClass", "SCP: Secret Laboratory")


def test_unrelated_unity_window_does_not_match():
    assert not winput._is_game_window("Another Game", "UnityWndClass", "SCP: Secret Laboratory")


def test_replace_text_clears_retained_endpoint_before_typing(monkeypatch):
    events = []
    monkeypatch.setattr(winput, "post_hotkey", lambda hwnd, modifier, key: events.append(("hotkey", hwnd, modifier, key)))
    monkeypatch.setattr(winput, "post_key_tap", lambda hwnd, key: events.append(("key", hwnd, key)))
    monkeypatch.setattr(winput, "post_text", lambda hwnd, text: events.append(("text", hwnd, text)))

    winput.replace_text(123, "1.2.3.4:7778")

    assert events == [
        ("hotkey", 123, winput.VK_CONTROL, winput.VK_A),
        ("key", 123, winput.VK_BACK),
        ("text", 123, "1.2.3.4:7778"),
    ]

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import winput


def test_scpsl_unity_window_matches_even_when_display_title_differs():
    assert winput._is_game_window("SCPSL", "UnityWndClass", "SCP: Secret Laboratory")


def test_unrelated_unity_window_does_not_match():
    assert not winput._is_game_window("Another Game", "UnityWndClass", "SCP: Secret Laboratory")

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import transport


def test_build_direct_args_uses_the_exact_supported_connect_arguments():
    assert transport.build_direct_args("C:/Games/SCPSL.exe", "1.2.3.4", 7778) == [
        "C:/Games/SCPSL.exe", "-steam", "+connect", "1.2.3.4:7778",
    ]


def test_automatic_method_uses_direct_only_while_the_game_is_cold():
    assert transport.choose_method({"connection_method": "automatic"}, game_running=False) == "direct"
    assert transport.choose_method({"connection_method": "automatic"}, game_running=True) == "background"


def test_warm_background_connection_falls_back_to_foreground_after_missing_log_marker():
    events = []

    class Context:
        config = {"connection_method": "automatic"}
        game_running = True

        def start_direct(self):
            events.append("direct")

        def start_background(self):
            events.append("background")

        def start_foreground(self):
            events.append("foreground")

        def wait_for_connecting(self):
            events.append("log")
            return len([event for event in events if event == "log"]) == 2

        def stopped(self):
            return False

    context = Context()

    assert transport.connect_with_fallback(context) is None
    assert context.method == "foreground"
    assert events == ["background", "log", "foreground", "log"]

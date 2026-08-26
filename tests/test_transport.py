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
    assert transport.choose_method({"connection_method": "automatic"}, game_running=True) == "foreground"


def test_automatic_warm_connection_uses_verified_foreground_path():
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
            return True

        def stopped(self):
            return False

    context = Context()

    assert transport.connect_with_fallback(context) is None
    assert context.method == "foreground"
    assert events == ["foreground", "log"]


def test_explicit_background_mode_never_falls_back_to_foreground():
    events = []

    class Context:
        config = {"connection_method": "background"}
        game_running = True

        def start_direct(self):
            events.append("direct")

        def start_background(self):
            events.append("background")

        def start_foreground(self):
            raise AssertionError("background-only mode must not use foreground input")

        def wait_for_connecting(self):
            events.append("log")
            return False

        def stopped(self):
            return False

    context = Context()
    transport.connect_with_fallback(context)
    assert context.method == "background"
    assert events == ["background", "log"]


def test_build_steam_connect_uri_uses_the_supported_warm_connection_path():
    assert transport.build_steam_connect_uri("1.2.3.4", 7778) == "steam://connect/1.2.3.4:7778"

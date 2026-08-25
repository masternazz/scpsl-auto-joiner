"""Connection-method selection and small, testable launch primitives."""
import os
import subprocess
from typing import Literal


ConnectionMethod = Literal["direct", "background", "foreground"]


def build_direct_args(executable, ip, port) -> list[str]:
    """Build SCP:SL's supported Steam-authenticated direct-connect command."""
    return [executable, "-steam", "+connect", f"{ip}:{port}"]


def launch_direct(executable, ip, port) -> subprocess.Popen:
    """Start a cold SCP:SL client with its direct-connect arguments."""
    return subprocess.Popen(build_direct_args(executable, ip, port), cwd=os.path.dirname(executable))


def choose_method(config, game_running) -> ConnectionMethod:
    """Choose a method without ever direct-launching an existing client."""
    preferred = config.get("connection_method", "automatic")
    if preferred == "foreground":
        return "foreground"
    if preferred == "background":
        return "background"
    if not game_running:
        return "direct"
    return "background"


def connect_with_fallback(ctx) -> None:
    """Start a connection and record the method confirmed by ``Player.log``.

    ``ctx`` owns UI and log-watcher details. It provides ``start_direct``,
    ``start_background``, ``start_foreground``, ``wait_for_connecting``, and
    ``stopped`` methods, plus ``config`` and ``game_running`` attributes.
    """
    method = choose_method(ctx.config, ctx.game_running)
    ctx.method = method

    if method == "direct":
        ctx.start_direct()
        ctx.connected = ctx.wait_for_connecting()
        return

    if method == "foreground":
        ctx.start_foreground()
        ctx.connected = ctx.wait_for_connecting()
        return

    ctx.start_background()
    ctx.connected = ctx.wait_for_connecting()
    if ctx.connected or ctx.stopped():
        return

    ctx.method = "foreground"
    ctx.start_foreground()
    ctx.connected = ctx.wait_for_connecting()

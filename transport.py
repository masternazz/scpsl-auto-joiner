"""Connection-method selection and small, testable launch primitives."""
import os
import subprocess
from typing import Literal


ConnectionMethod = Literal["direct", "steam", "background", "foreground"]


def build_steam_connect_uri(ip, port) -> str:
    return f"steam://connect/{ip}:{int(port)}"


def launch_steam_connect(ip, port) -> None:
    """Ask the running Steam game to connect without global input."""
    os.startfile(build_steam_connect_uri(ip, port))


def build_direct_args(executable, ip, port) -> list[str]:
    """Build SCP:SL's supported Steam-authenticated direct-connect command."""
    return [executable, "-steam", "+connect", f"{ip}:{port}"]


def launch_direct(executable, ip, port) -> subprocess.Popen:
    """Start a cold SCP:SL client with its direct-connect arguments."""
    return subprocess.Popen(build_direct_args(executable, ip, port), cwd=os.path.dirname(executable))


def choose_method(config, game_running) -> ConnectionMethod:
    """Choose a method without launching Steam's connection dialog."""
    if not game_running:
        return "direct"
    # Old test/config dictionaries may omit the new setting. The persisted
    # config migration supplies "automatic" for real users; treating an
    # omitted value as background preserves that legacy API behavior.
    preferred = config.get("connection_method", "background")
    if preferred == "foreground":
        return "foreground"
    if preferred == "background":
        return "background"
    # ``steam://connect`` opens Steam's Game Info dialog for full/rejected
    # servers. Automatic retries must stay inside SCP:SL's existing window.
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

    # Automatic mode is deliberately background-only. Unity can ignore window
    # messages, but silently switching to SendInput would move the user's
    # cursor, steal focus, and type into the wrong application. The caller
    # reports the missing marker and applies its normal retry policy instead.
    ctx.method = "background"
    ctx.start_background()
    ctx.connected = ctx.wait_for_connecting()
    if (
        not ctx.connected
        and not ctx.stopped()
        and ctx.config.get("connection_method", "automatic") == "automatic"
    ):
        if hasattr(ctx, "recover_foreground"):
            ctx.recover_foreground()
        ctx.method = "foreground"
        ctx.start_foreground()
        ctx.connected = ctx.wait_for_connecting()

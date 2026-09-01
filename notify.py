"""Windows toast notifications. Falls back to a console print if the toast
backend isn't available (e.g. running on an unsupported Windows build) so a
notification failure never crashes the driver loop."""
from win11toast import toast
from urllib.parse import quote
try:
    import winsound
except ImportError:  # packaged product is Windows-only; tests may not be.
    winsound = None

import config as config_mod


def notify(title: str, message: str):
    if not config_mod.load_config().get("notifications_enabled", True):
        return
    try:
        toast(title, message)
    except Exception:
        print(f"[notify] {title}: {message}")


def slot_available(server_name: str, server_id: str, players=None, max_players=None, sound=False, actions=False):
    """Show an opt-in slot alert. Protocol actions go to the same-user app pipe."""
    suffix = f" ({players}/{max_players})" if players is not None and max_players else ""
    if sound and winsound is not None:
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except RuntimeError:
            pass
    try:
        if not config_mod.load_config().get("notifications_enabled", True):
            return False
        buttons = []
        if actions:
            base = f"scpsl-autojoin://watch-action?server_id={quote(str(server_id))}&action="
            buttons = [
                {"activationType": "protocol", "arguments": base + "join", "content": "Join now"},
                {"activationType": "protocol", "arguments": base + "keep", "content": "Keep watching"},
                {"activationType": "protocol", "arguments": base + "mute_join", "content": "Mute game and join"},
            ]
        toast("SCP:SL slot confirmed", f"{server_name}{suffix} is ready.", buttons=buttons)
        return True
    except Exception:
        print(f"[notify] SCP:SL slot confirmed: {server_name}{suffix}")
        return False


if __name__ == "__main__":
    notify("SCP:SL Auto-Joiner", "Test notification — if you see a toast, this works.")

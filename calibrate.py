"""One-time interactive calibration: records the screen coordinates of the
menu buttons and Direct Connect fields the driver loop clicks blind. Run this
once per machine/resolution, and again any time the game window moves,
resizes, or the menu layout changes."""
import ctypes

import config as config_mod
import winput

CLICK_POINT_NAMES = [
    "play", "servers_tab", "internet_tab", "direct_connect",
    "ip_field", "connect_button",
]

_PROMPTS = {
    "play": "the main menu's Play button",
    "servers_tab": "the Servers tab",
    "internet_tab": "the Internet tab",
    "direct_connect": "the Direct Connect button",
    "ip_field": "the Direct Connect IP:port text field",
    "connect_button": "the Direct Connect dialog's Connect button",
}


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _cursor_pos():
    pt = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def run_calibration(cfg_path=None):
    winput.set_dpi_awareness()
    cfg = config_mod.load_config(cfg_path)
    print("Get SCP:SL open and sitting at the main menu, then continue.")
    input("Press Enter when ready...")
    for name in CLICK_POINT_NAMES:
        input(f"Hover your mouse over {_PROMPTS[name]} (don't click), then press Enter...")
        x, y = _cursor_pos()
        cfg["click_points"][name] = [x, y]
        print(f"  {name} = ({x}, {y})")
    config_mod.save_config(cfg, cfg_path)
    print(f"Calibration saved to {cfg_path or config_mod.CONFIG_PATH}")


if __name__ == "__main__":
    run_calibration()

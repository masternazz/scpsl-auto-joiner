"""Windows toast notifications. Falls back to a console print if the toast
backend isn't available (e.g. running on an unsupported Windows build) so a
notification failure never crashes the driver loop."""
from win11toast import toast


def notify(title: str, message: str):
    try:
        toast(title, message)
    except Exception:
        print(f"[notify] {title}: {message}")


if __name__ == "__main__":
    notify("SCP:SL Auto-Joiner", "Test notification — if you see a toast, this works.")

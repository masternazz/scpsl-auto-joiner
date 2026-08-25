"""Render a readable, generic auto-join walkthrough for the README."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FRAMES = ROOT / "assets" / "generated" / "auto-join-demo-frames"
FRAMES.mkdir(exist_ok=True)

BASE_W, BASE_H = 960, 540
SCALE = 2
W, H = BASE_W * SCALE, BASE_H * SCALE
BG = "#0c0910"
PANEL = "#17111f"
CARD = "#21182d"
LINE = "#3e2d52"
WHITE = "#f5effa"
MUTED = "#ab9db8"
PURPLE = "#b186ff"
AMBER = "#ffb74d"
GREEN = "#68d391"


def font(size, bold=False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size * SCALE)


class Canvas:
    """Draw at logical coordinates while preserving native 1080p output."""

    def __init__(self, draw):
        self._draw = draw

    @staticmethod
    def coords(values):
        return tuple(round(value * SCALE) for value in values)

    def line(self, coords, **kwargs):
        kwargs["width"] = kwargs.get("width", 1) * SCALE
        self._draw.line(self.coords(coords), **kwargs)

    def rectangle(self, coords, **kwargs):
        self._draw.rectangle(self.coords(coords), **kwargs)

    def rounded_rectangle(self, coords, **kwargs):
        kwargs["radius"] = kwargs.get("radius", 0) * SCALE
        kwargs["width"] = kwargs.get("width", 1) * SCALE
        self._draw.rounded_rectangle(self.coords(coords), **kwargs)

    def ellipse(self, coords, **kwargs):
        kwargs["width"] = kwargs.get("width", 1) * SCALE
        self._draw.ellipse(self.coords(coords), **kwargs)

    def text(self, coords, text, **kwargs):
        self._draw.text(self.coords(coords), text, **kwargs)

    def textbbox(self, coords, text, **kwargs):
        return self._draw.textbbox(self.coords(coords), text, **kwargs)


def ease(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def fit_text(draw, text, max_width, start_size, bold=False):
    size = start_size
    while size > 10:
        f = font(size, bold)
        if draw.textbbox((0, 0), text, font=f)[2] <= max_width * SCALE:
            return f
        size -= 1
    return font(10, bold)


def render(index, total):
    t = index / (total - 1)
    image = Image.new("RGB", (W, H), BG)
    draw = Canvas(ImageDraw.Draw(image))

    for x in range(40, BASE_W, 80):
        draw.line((x, 0, x, BASE_H), fill="#130e19", width=1)
    for y in range(40, BASE_H, 80):
        draw.line((0, y, BASE_W, y), fill="#130e19", width=1)
    draw.rectangle((0, 0, 7, BASE_H), fill=PURPLE)

    draw.text((48, 36), "SCP:SL", font=font(22, True), fill=WHITE)
    draw.text((49, 66), "AUTO-JOINER", font=font(11, True), fill=PURPLE)
    draw.text((48, 465), "WINDOWS UTILITY", font=font(10, True), fill=PURPLE)
    draw.text((48, 484), "Server data stays local", font=font(12), fill=MUTED)

    draw.text((180, 42), "Stay in the queue.", font=font(31, True), fill=WHITE)
    draw.text((181, 86), "The joiner handles retries while you do something else.", font=font(15), fill=MUTED)

    draw.rounded_rectangle((180, 136, 900, 406), radius=12, fill=PANEL, outline=LINE, width=2)
    draw.text((214, 164), "SAVED SERVER", font=font(11, True), fill=PURPLE)
    draw.text((214, 194), "Northwood Official #1", font=font(24, True), fill=WHITE)
    draw.text((214, 232), "example.server:7777", font=font(15), fill=MUTED)

    if t < 0.18:
        state, status, detail, color, progress = "READY", "Choose a server", "Press Start auto-join", PURPLE, 0.0
    elif t < 0.34:
        p = ease((t - 0.18) / 0.16)
        state, status, detail, color, progress = "LAUNCHING", "Starting SCP:SL", "Opening the game in the background", PURPLE, p
    elif t < 0.50:
        p = ease((t - 0.34) / 0.16)
        state, status, detail, color, progress = "CONNECTING", "Direct Connect", "Submitting the saved endpoint", PURPLE, 1.0 + p
    elif t < 0.76:
        p = (t - 0.50) / 0.26
        state, status, detail, color, progress = "RETRYING", "Server full", f"Retrying in {max(1, 2 - int(p * 2))} seconds", AMBER, 2.0 + ease(p) * 1.0
    else:
        p = ease((t - 0.76) / 0.24)
        state, status, detail, color, progress = "JOINED", "Connection accepted", "You can leave it running", GREEN, 3.0 + p * 1.0

    draw.rounded_rectangle((214, 282, 866, 360), radius=9, fill=CARD, outline=color, width=2)
    draw.ellipse((237, 311, 253, 327), fill=color)
    draw.text((273, 298), status, font=fit_text(draw, status, 220, 20, True), fill=WHITE)
    draw.text((273, 329), detail, font=fit_text(draw, detail, 470, 14), fill=MUTED)
    draw.text((838, 298), state, font=font(11, True), fill=color, anchor="ra")

    steps = [("SELECT", 0), ("LAUNCH", 1), ("CONNECT", 2), ("RETRY", 3), ("JOINED", 4)]
    x0, gap, y = 240, 150, 445
    for i, (label, step) in enumerate(steps):
        x = x0 + gap * i
        if i < len(steps) - 1:
            draw.line((x + 10, y, x + gap - 10, y), fill=LINE, width=4)
        dot_color = color if progress >= step else LINE
        draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=dot_color)
        draw.text((x, y + 20), label, font=font(10, True), fill=WHITE if progress >= step else MUTED, anchor="ma")
    moving_x = x0 + gap * min(4, progress)
    draw.ellipse((moving_x - 16, y - 16, moving_x + 16, y + 16), outline=color, width=2)
    return image


def main():
    for old in FRAMES.glob("frame_*.png"):
        old.unlink()
    total = 68
    for index in range(total):
        render(index, total).save(FRAMES / f"frame_{index:04d}.png")
    print(f"Rendered {total} frames to {FRAMES}")


if __name__ == "__main__":
    main()

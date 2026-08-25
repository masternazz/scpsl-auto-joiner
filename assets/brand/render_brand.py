from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "generated"
OUT.mkdir(exist_ok=True)

BG = "#0d0a12"
PURPLE = "#b186ff"
WHITE = "#f5effa"
MUTED = "#b1a3bd"
SUBTLE = "#7c6d89"
AMBER = "#ffb74d"
GREEN = "#68d391"
GRID = "#1d1728"


def font(size, bold=False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    path = Path("C:/Windows/Fonts") / name
    return ImageFont.truetype(str(path), size)


def mark(size=1024):
    scale = 4
    image = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    s = size * scale
    c = s // 2
    draw.rounded_rectangle((0, 0, s - 1, s - 1), radius=112 * scale, fill=BG)
    draw.ellipse((c - 352 * scale, c - 352 * scale, c + 352 * scale, c + 352 * scale), outline=PURPLE, width=32 * scale)
    draw.ellipse((c - 232 * scale, c - 232 * scale, c + 232 * scale, c + 232 * scale), outline=WHITE, width=16 * scale)
    for box in ((c - 352 * scale, c - 16 * scale, c - 232 * scale, c + 16 * scale), (c + 232 * scale, c - 16 * scale, c + 352 * scale, c + 16 * scale), (c - 16 * scale, c - 352 * scale, c + 16 * scale, c - 232 * scale), (c - 16 * scale, c + 232 * scale, c + 16 * scale, c + 352 * scale)):
        draw.rectangle(box, fill=PURPLE)
    draw.rectangle((c - 144 * scale, c - 128 * scale, c + 144 * scale, c + 128 * scale), outline=WHITE, width=20 * scale)
    draw.rectangle((c - 80 * scale, c - 64 * scale, c + 80 * scale, c + 64 * scale), fill=PURPLE)
    draw.line((c - 48 * scale, c, c + 48 * scale, c), fill=BG, width=20 * scale)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def banner(width=1600, height=500):
    scale = 2
    image = Image.new("RGB", (width * scale, height * scale), BG)
    draw = ImageDraw.Draw(image)
    for y in range(80, height, 80):
        draw.line((0, y * scale, width * scale, y * scale), fill=GRID, width=2)
    for x in range(100, width, 100):
        draw.line((x * scale, 0, x * scale, height * scale), fill="#17121f", width=2)
    cx, cy = 1160 * scale, 250 * scale
    draw.ellipse((cx - 190 * scale, cy - 190 * scale, cx + 190 * scale, cy + 190 * scale), outline="#3a2d4b", width=8 * scale)
    draw.ellipse((cx - 128 * scale, cy - 128 * scale, cx + 128 * scale, cy + 128 * scale), outline=PURPLE, width=5 * scale)
    draw.rectangle((cx - 76 * scale, cy - 48 * scale, cx + 76 * scale, cy + 48 * scale), outline=WHITE, width=5 * scale)
    draw.rectangle((cx - 42 * scale, cy - 24 * scale, cx + 42 * scale, cy + 24 * scale), fill=PURPLE)
    draw.text((118 * scale, 145 * scale), "SCP:SL", font=font(68 * scale, True), fill=WHITE)
    draw.text((116 * scale, 260 * scale), "AUTO-JOINER", font=font(30 * scale, True), fill=PURPLE)
    draw.line((118 * scale, 335 * scale, 458 * scale, 335 * scale), fill=PURPLE, width=4 * scale)
    draw.text((118 * scale, 350 * scale), "SERVER RETRIES • WINDOWS UTILITY", font=font(22 * scale), fill=MUTED)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def workflow_frame(state, frame, width=960, height=600):
    scale = 2
    image = Image.new("RGB", (width * scale, height * scale), BG)
    draw = ImageDraw.Draw(image)
    px = lambda value: int(value * scale)
    draw.rectangle((px(0), px(0), px(210), px(height)), fill="#15111d")
    draw.line((px(210), 0, px(210), px(height)), fill="#3a2d4b", width=2 * scale)
    draw.text((px(32), px(34)), "SCP:SL", font=font(px(27), True), fill=WHITE)
    draw.text((px(32), px(73)), "AUTO-JOINER", font=font(px(13), True), fill=PURPLE)
    for y, text in ((150, "01  Auto-Join"), (198, "02  Calibration"), (246, "03  Settings"), (294, "04  Help")):
        active = y == 150
        draw.rounded_rectangle((px(22), px(y - 12), px(188), px(y + 28)), radius=px(6), fill="#282038" if active else BG)
        draw.text((px(36), px(y)), text, font=font(px(15)), fill=WHITE if active else MUTED)
    draw.text((px(32), px(530)), "LOCAL DESKTOP TOOL", font=font(px(10), True), fill=PURPLE)
    draw.text((px(32), px(552)), "Server data stays local", font=font(px(11)), fill=MUTED)
    draw.text((px(252), px(52)), "Auto-Join", font=font(px(31), True), fill=WHITE)
    draw.text((px(252), px(101)), "Keeps trying until the server accepts the connection.", font=font(px(15)), fill=MUTED)
    draw.rounded_rectangle((px(252), px(155), px(910), px(315)), radius=px(10), fill="#1d1728", outline="#3a2d4b", width=2 * scale)
    draw.text((px(280), px(181)), "SAVED SERVER", font=font(px(11), True), fill=PURPLE)
    draw.text((px(280), px(214)), "Northwood Official #1", font=font(px(22), True), fill=WHITE)
    draw.text((px(280), px(260)), "example.server:7777", font=font(px(14)), fill=MUTED)
    labels = ["Select", "Launch", "Connect", "Full", "Retry", "Joined"]
    progress = min(5.0, state + (frame / 3.0 if state < 5 else 0.0))
    for i, label_text in enumerate(labels):
        x = 280 + i * 100
        color = PURPLE if i <= state else "#3a2d4b"
        draw.ellipse((px(x), px(390), px(x + 18), px(408)), fill=color)
        if i < len(labels) - 1:
            draw.line((px(x + 18), px(399), px(x + 100), px(399)), fill="#3a2d4b", width=3 * scale)
        draw.text((px(x - 8), px(430)), label_text, font=font(px(11), True), fill=WHITE if i <= state else SUBTLE)
    pulse_x = 280 + min(5.0, progress) * 100
    draw.ellipse((px(pulse_x - 7), px(393), px(pulse_x + 25), px(425)), outline=PURPLE, width=3 * scale)
    messages = [
        ("Ready", "Choose a saved server and start.", PURPLE),
        ("Launching SCP:SL", "Starting the game in the background.", PURPLE),
        ("Connecting", "Opening Direct Connect and submitting the address.", PURPLE),
        ("Server full", f"Retrying in {max(1, 2 - min(frame, 1))} seconds.", AMBER),
        ("Retrying", "Trying again after the two-second delay.", PURPLE),
        ("Joined", "Connection accepted.", GREEN),
    ]
    title, detail, color = messages[state]
    draw.rounded_rectangle((px(252), px(485), px(910), px(565)), radius=px(8), fill="#15111d", outline=color, width=2 * scale)
    draw.ellipse((px(274), px(519), px(286), px(531)), fill=color)
    draw.text((px(302), px(502)), title, font=font(px(16), True), fill=WHITE)
    draw.text((px(430), px(505)), detail, font=font(px(13)), fill=MUTED)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def workflow_gif():
    frames = []
    durations = []
    for state, count, duration in ((0, 3, 550), (1, 3, 500), (2, 3, 500), (3, 4, 350), (4, 3, 450), (5, 5, 650)):
        for frame in range(count):
            frames.append(workflow_frame(state, frame))
            durations.append(duration)
    frames[0].save(OUT / "auto-join-flow.gif", save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=False)


mark().save(OUT / "containment-mark-purple.png")
banner().save(OUT / "github-banner-purple.png")
workflow_gif()

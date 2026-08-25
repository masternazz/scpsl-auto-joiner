from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "generated"
OUT.mkdir(exist_ok=True)

BG = "#0d0a12"
PURPLE = "#b186ff"
WHITE = "#f5effa"
MUTED = "#b1a3bd"
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


mark().save(OUT / "containment-mark-purple.png")
banner().save(OUT / "github-banner-purple.png")

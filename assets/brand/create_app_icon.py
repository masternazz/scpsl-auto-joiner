"""Create the compact purple S mark used by the app, taskbar, and tray.

Run from the repository root:
    py -3.13 assets/brand/create_app_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "assets"
SIZE = 1024


def main():
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((32, 32, SIZE - 32, SIZE - 32), radius=220, fill="#100d15")
    # Match the app's sidebar seal: a restrained diamond and a centered S.
    draw.polygon(((512, 128), (896, 512), (512, 896), (128, 512)), outline="#a77dff", width=22)
    face = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 460)
    label = Image.new("RGBA", (640, 640), (0, 0, 0, 0))
    label_draw = ImageDraw.Draw(label)
    box = label_draw.textbbox((0, 0), "S", font=face)
    label_draw.text(((640 - (box[2] - box[0])) / 2 - box[0], (640 - (box[3] - box[1])) / 2 - box[1]), "S", font=face, fill="#a77dff")
    label = label.rotate(45, resample=Image.Resampling.BICUBIC, expand=False)
    image.alpha_composite(label, (192, 192))
    image.save(OUTPUT / "app-icon.png")
    image.convert("RGBA").save(OUTPUT / "app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()

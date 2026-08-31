"""Create reproducible README screenshots and two sanitized demo candidates.

Run from the repository root:
    py -3.13 assets/brand/render_readme_assets.py

The WebView captures use only fake, local-looking data. Raw PNG frames are
temporary and are never kept in the repository.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
WEBUI = ROOT / "webui" / "index.html"
OUT = ROOT / "assets" / "generated"
OUT.mkdir(exist_ok=True)
# Render the UI at its proven wide-desktop layout, then capture at 1.5x DPI.
# This produces 3840x2160 screenshots without shrinking the actual interface.
CAPTURE_W, CAPTURE_H = 2560, 1440
CAPTURE_SCALE = 1.5


def font(size: int, bold: bool = False):
    face = "segoeuib.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / face), size)


def product_hero():
    """Create a compact product-led banner anchored by the app's S mark."""
    image = Image.new("RGB", (1920, 520), "#0b0910")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 8, 520), fill="#a77dff")
    draw.line((628, 82, 628, 438), fill="#322442", width=2)
    draw.text((708, 120), "SCP:SL AUTO-JOINER", font=font(60, True), fill="#f8f4fb")
    draw.text((712, 214), "Watch a saved server. Join when capacity opens.", font=font(29), fill="#c8bad5")
    draw.text((713, 280), "WATCH MODE  /  SMART GROUPS  /  LOCAL-FIRST", font=font(17, True), fill="#a77dff")
    draw.text((713, 374), "Windows 10 / 11  /  SCP: Secret Laboratory", font=font(18), fill="#8e809d")

    # The mark keeps the hero legible at every GitHub width. Product UI belongs
    # in the walkthrough directly below it, where controls can be read.
    mark = Image.open(ROOT / "assets" / "app-icon.png").convert("RGBA")
    mark = mark.resize((272, 272), Image.Resampling.LANCZOS)
    image.paste(mark, (308, 124), mark)
    image.save(OUT / "readme-hero-s.png")


BRIDGE = """
window.pywebview = {api: {
 get_app_state: async () => ({ok:true,version:'0.3.33', servers:[
  {id:'srv-1',name:'Masternazz Private',ip:'sanitized.example',port:7777,status:{players:18,max_players:20,latency_ms:28},monitoring:{enabled:true,query_interval_s:2},join_profile:{},share_presence:false},
  {id:'srv-2',name:'Containment Reserve',ip:'reserve.example',port:7778,status:{players:12,max_players:20,latency_ms:43},monitoring:{enabled:false},join_profile:{},share_presence:false}],
 groups:[{id:'group-1',name:'Evening queue',server_ids:['srv-1','srv-2'],policy:{strategy:'first_available',minimum_players:0,maximum_fill_percent:90,loop:true}}],
 settings:{retry_interval_s:2,max_attempts:0,max_minutes:0,connection_method:'automatic',mute_game_audio:false,notifications_enabled:true,motion_preset:'expressive',accent:'violet',custom_accent:'#a77dff'},
 calibration:{calibrated:true,points:{servers_tab:[1,1],direct_connect:[1,1],ip_field:[1,1],connect_button:[1,1]}},
 calibration_profiles:{profiles:[{id:'profile-1',name:'Primary display',health:'healthy'}],active:'profile-1'},
 packs:{packs:[],active_pack:null},
 theme:{preset:'violet'}, join:{running:false}, storage:{migrated:false,paths:{}}}),
 get_servers: async () => ({servers:[]}), get_groups: async () => ({groups:[]}), get_monitor_status:async()=>({running:false,servers:1}),
 get_server_insights:async()=>({ok:true,insights:{samples:42,peak_players:20,average_latency_ms:31,full_frequency:0.42,availability_likelihood:0.71,periods:{'24h':{},'7d':{},'30d':{}}}}),
 get_server_history:async()=>({ok:true,samples:[]}), get_discord_status:async()=>({ok:true,enabled:false}),
 get_update_status:async()=>({ok:true,update:null}), get_calibration_state:async()=>({calibration:{calibrated:true,points:{}}}),
 get_calibration_profiles:async()=>({ok:true,profiles:[{id:'profile-1',name:'Primary display',health:'healthy'}],active:'profile-1'}),
 check_translation_updates:async()=>({ok:true,updates:[]}), get_translation_updates:async()=>({ok:true,updates:[]}),
 refresh_server_status:async()=>({ok:true,status:{available:true,players:18,max_players:20,latency_ms:28}}),
 start_join:async()=>({ok:true}), stop_join:async()=>({ok:true}), start_watch:async()=>({ok:true}), stop_watch:async()=>({ok:true}),
 save_setting:async()=>({ok:true,settings:{}}), save_server:async()=>({ok:true}), save_group:async()=>({ok:true}), delete_server:async()=>({ok:true}), delete_group:async()=>({ok:true}),
 set_theme:async()=>({ok:true}), reset_theme:async()=>({ok:true}), set_active_calibration_profile:async()=>({ok:true}),
 import_translation_pack:async()=>({ok:true}), activate_translation_pack:async()=>({ok:true}), delete_translation_pack:async()=>({ok:true}),
 search_translation_packs:async()=>({ok:true,results:[]}), start_remember:async()=>({ok:true}), preview_destination:async()=>({ok:true}), import_destination:async()=>({ok:true})
}};
"""


def capture_webview_assets(temp: Path):
    screenshots = {"join": "readme-auto-join.png", "servers": "readme-servers.png", "packs": "readme-text-packs.png", "diagnostics": "readme-diagnostics.png", "settings": "readme-themes.png"}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Dense product pages are captured at their wide-desktop breakpoint.
        page = browser.new_page(viewport={"width": CAPTURE_W, "height": CAPTURE_H}, device_scale_factor=CAPTURE_SCALE)
        page.add_init_script(BRIDGE)
        page.goto(WEBUI.as_uri())
        page.wait_for_selector("h1")
        for target, name in screenshots.items():
            if target != "join":
                page.locator(f".nav-item[data-page='{target}']").click()
                page.wait_for_timeout(150)
            page.screenshot(path=str(OUT / name), full_page=False)
        # Record the actual WebView between structured state updates. The
        # README GIF therefore uses the same CSS transitions as the app.
        page.locator(".nav-item[data-page='join']").click()
        page.wait_for_timeout(320)
        steps = [
            ("watching", {"message": "Watching Masternazz Private / 18 of 20 players"}, 11),
            ("slot_candidate", {"message": "Slot candidate detected / confirming"}, 12),
            ("join_attempt_started", {"attempt": 1, "message": "Opening Direct Connect"}, 11),
            ("join_succeeded", {"message": "Joined Masternazz Private"}, 29),
            ("watching", {"message": "Watching Masternazz Private / 18 of 20 players"}, 9),
        ]
        frame = 0
        focus = {"x": 400, "y": 93, "width": 1960, "height": 960}
        for event, data, frames in steps:
            page.evaluate("([event,data]) => window.__appEvent({event,data})", [event, data])
            for _ in range(frames):
                page.screenshot(path=str(temp / f"sequence-{frame:03d}.png"), clip=focus)
                frame += 1
                page.wait_for_timeout(83)
        browser.close()


def make_video_and_gif(frames: Path, pattern: str, stem: str, fps: int = 8, output_width: int = 1920, gif_width: int = 720):
    mp4 = OUT / f"{stem}.mp4"
    gif = OUT / f"{stem}.gif"
    palette = frames / f"{stem}-palette.png"
    source = str(frames / pattern)
    subprocess.run(["ffmpeg", "-y", "-framerate", str(fps), "-i", source, "-vf", f"scale={output_width}:-2:flags=lanczos", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(mp4), "-vf", f"fps=12,scale={gif_width}:-1:flags=lanczos,palettegen=max_colors=192", str(palette)], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(mp4), "-i", str(palette), "-lavfi", f"fps=12,scale={gif_width}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3", "-loop", "0", str(gif)], check=True)
    palette.unlink(missing_ok=True)


def main():
    with tempfile.TemporaryDirectory(prefix="scpsl-readme-") as raw:
        raw = Path(raw)
        live = raw / "live"; live.mkdir()
        capture_webview_assets(live)
        product_hero()

        make_video_and_gif(live, "sequence-%03d.png", "demo-webview", fps=12, output_width=2880, gif_width=1080)
    print("README assets written to", OUT)


if __name__ == "__main__":
    main()

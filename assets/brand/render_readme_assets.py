"""Create reproducible README screenshots and two sanitized demo candidates.

Run from the repository root:
    py -3.13 assets/brand/render_readme_assets.py

The WebView captures use only fake, local-looking data. Raw PNG frames are
temporary and are never kept in the repository.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
WEBUI = ROOT / "webui" / "index.html"
OUT = ROOT / "assets" / "generated"
OUT.mkdir(exist_ok=True)
W, H = 1920, 1080
CAPTURE_W, CAPTURE_H = 2560, 1440


def font(size: int, bold: bool = False):
    face = "segoeuib.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / face), size)


def hero():
    image = Image.new("RGB", (W, 600), "#0b0910")
    draw = ImageDraw.Draw(image)
    for x in range(0, W, 96):
        draw.line((x, 0, x, 600), fill="#18121f", width=1)
    for y in range(0, 600, 96):
        draw.line((0, y, W, y), fill="#18121f", width=1)
    draw.rectangle((0, 0, 10, 600), fill="#a77dff")
    draw.text((118, 135), "SCP:SL AUTO-JOINER", font=font(74, True), fill="#f8f4fb")
    draw.text((122, 240), "Find the slot. Take the connection.", font=font(36), fill="#c8bad5")
    draw.text((123, 318), "WATCH MODE  /  SMART GROUPS  /  LOCAL-FIRST", font=font(19, True), fill="#a77dff")
    cx, cy = 1510, 300
    for radius, color, width in ((195, "#2d2141", 4), (136, "#a77dff", 5), (78, "#f8f4fb", 3)):
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), outline=color, width=width)
    draw.rounded_rectangle((cx-102, cy-48, cx+102, cy+48), radius=12, outline="#f8f4fb", width=5)
    draw.rounded_rectangle((cx-50, cy-20, cx+50, cy+20), radius=5, fill="#a77dff")
    draw.text((123, 475), "Windows 10 / 11  /  SCP: Secret Laboratory", font=font(20), fill="#8e809d")
    image.save(OUT / "readme-hero.png")


def rendered_frame(frame: int, total: int) -> Image.Image:
    t = frame / max(1, total - 1)
    image = Image.new("RGB", (W, H), "#0b0910")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 330, H), fill="#100c17")
    draw.line((330, 0, 330, H), fill="#36264a", width=2)
    draw.text((58, 74), "SCP:SL", font=font(35, True), fill="#f8f4fb")
    draw.text((58, 122), "CONTAINMENT / LIVE", font=font(16, True), fill="#a77dff")
    for index, label in enumerate(("01  Auto-Join", "02  Servers", "03  History", "04  Settings")):
        y = 242 + index * 84
        if index == 0:
            draw.rounded_rectangle((40, y-14, 290, y+44), radius=10, fill="#2b1d3d")
        draw.text((62, y), label, font=font(20), fill="#f8f4fb" if index == 0 else "#b8a9c5")
    draw.text((430, 90), "WATCH MODE", font=font(18, True), fill="#a77dff")
    draw.text((430, 136), "Auto-Join", font=font(64, True), fill="#f8f4fb")
    draw.text((432, 218), "Monitor a server quietly, then connect when capacity opens.", font=font(24), fill="#c8bad5")
    draw.rounded_rectangle((430, 300, 1760, 690), radius=22, fill="#15101c", outline="#4e3670", width=2)
    draw.text((480, 350), "SELECTED DESTINATION", font=font(15, True), fill="#a77dff")
    draw.text((480, 404), "Masternazz Private", font=font(38, True), fill="#f8f4fb")
    draw.text((480, 458), "sanitized.example:7777", font=font(22), fill="#b8a9c5")
    phase = min(4, int(t * 5))
    phases = [("WATCHING", "Polling server capacity", "#a77dff"), ("SLOT CANDIDATE", "First available-slot sample", "#e5aa56"), ("CONFIRMED", "Second sample confirms the slot", "#e5aa56"), ("CONNECTING", "Handing off to Direct Connect", "#a77dff"), ("JOINED", "Connection accepted", "#65d49a")]
    label, detail, color = phases[phase]
    draw.rounded_rectangle((480, 530, 1704, 630), radius=14, fill="#0d0a12", outline=color, width=3)
    draw.ellipse((520, 566, 548, 594), fill=color)
    draw.text((580, 548), label, font=font(25, True), fill="#f8f4fb")
    draw.text((860, 553), detail, font=font(21), fill="#c8bad5")
    steps = ("WATCH", "SAMPLE", "CONFIRM", "CONNECT", "JOIN")
    for index, step in enumerate(steps):
        x = 505 + index * 280
        active = index <= phase
        if index < 4:
            draw.line((x+26, 786, x+254, 786), fill="#4e3670", width=5)
        draw.ellipse((x, 762, x+48, 810), fill=color if active else "#39294e")
        draw.text((x-4, 836), step, font=font(16, True), fill="#f8f4fb" if active else "#917da1")
    draw.text((430, 972), "LOCAL-FIRST / NO ACCOUNT / NO PUBLIC ROLE DETECTION", font=font(16, True), fill="#a77dff")
    return image


BRIDGE = """
window.pywebview = {api: {
 get_app_state: async () => ({ok:true,version:'0.3.33', servers:[
  {id:'srv-1',name:'Masternazz Private',ip:'sanitized.example',port:7777,status:{players:18,max_players:20,latency_ms:28},monitoring:{enabled:true,query_interval_s:2},join_profile:{},share_presence:false},
  {id:'srv-2',name:'Containment Reserve',ip:'reserve.example',port:7778,status:{players:12,max_players:20,latency_ms:43},monitoring:{enabled:false},join_profile:{},share_presence:false}],
 groups:[{id:'group-1',name:'Evening queue',server_ids:['srv-1','srv-2'],policy:{strategy:'first_available',minimum_players:0,maximum_fill_percent:90,loop:true}}],
 settings:{retry_interval_s:2,max_attempts:0,max_minutes:0,connection_method:'automatic',mute_game_audio:false,notifications_enabled:true,accent:'violet',custom_accent:'#a77dff'},
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
        page = browser.new_page(viewport={"width": CAPTURE_W, "height": CAPTURE_H}, device_scale_factor=1)
        page.add_init_script(BRIDGE)
        page.goto(WEBUI.as_uri())
        page.wait_for_selector("h1")
        for target, name in screenshots.items():
            if target != "join":
                page.locator(f".nav-item[data-page='{target}']").click()
                page.wait_for_timeout(150)
            page.screenshot(path=str(OUT / name), full_page=False)
        # The app emits real structured events. Capture its joined state for
        # the staged candidate rather than painting text over a screenshot.
        page.locator(".nav-item[data-page='join']").click()
        page.wait_for_timeout(100)
        steps = [
            ("watching", {"message": "Watching Masternazz Private / 18 of 20 players"}),
            ("slot_candidate", {"message": "Slot candidate detected / confirming"}),
            ("join_attempt_started", {"attempt": 1, "message": "Opening Direct Connect"}),
            ("join_succeeded", {"message": "Joined Masternazz Private"}),
        ]
        for index, (event, data) in enumerate(steps):
            page.evaluate("([event,data]) => window.__appEvent({event,data})", [event, data])
            page.wait_for_timeout(180)
            page.screenshot(path=str(temp / f"live-{index:03d}.png"), full_page=False)
        browser.close()


def make_video_and_gif(frames: Path, pattern: str, stem: str, fps: int = 8):
    mp4 = OUT / f"{stem}.mp4"
    gif = OUT / f"{stem}.gif"
    palette = frames / f"{stem}-palette.png"
    source = str(frames / pattern)
    subprocess.run(["ffmpeg", "-y", "-framerate", str(fps), "-i", source, "-vf", "scale=1920:1080:flags=lanczos", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(mp4), "-vf", "fps=12,scale=720:-1:flags=lanczos,palettegen=max_colors=128", str(palette)], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(mp4), "-i", str(palette), "-lavfi", "fps=12,scale=720:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3", "-loop", "0", str(gif)], check=True)
    palette.unlink(missing_ok=True)


def main():
    hero()
    with tempfile.TemporaryDirectory(prefix="scpsl-readme-") as raw:
        raw = Path(raw)
        rendered = raw / "rendered"; rendered.mkdir()
        # 15 seconds at 8 fps; duplicate frames keep each status readable.
        for index in range(120):
            rendered_frame(index, 120).save(rendered / f"rendered-{index:03d}.png")
        make_video_and_gif(rendered, "rendered-%03d.png", "demo-rendered")

        live = raw / "live"; live.mkdir()
        capture_webview_assets(live)
        # Hold each of the four real UI states for three seconds.
        for source in sorted(live.glob("live-*.png")):
            for copy in range(24):
                target = live / f"sequence-{len(list(live.glob('sequence-*.png'))):03d}.png"
                shutil.copyfile(source, target)
        make_video_and_gif(live, "sequence-%03d.png", "demo-webview")
    print("README assets written to", OUT)


if __name__ == "__main__":
    main()

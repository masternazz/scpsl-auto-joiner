"""Responsive native desktop UI for the SCP:SL Auto-Joiner."""
import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import config as config_mod
import joiner
import logwatch
import resolver
import winput
from app_paths import resource_path

BG = "#0b1220"
PANEL = "#121d2e"
CARD = "#18263a"
FIELD = "#0f1a2a"
TEXT = "#eef5ff"
MUTED = "#91a4bd"
CYAN = "#39d8ff"
AMBER = "#ffb84d"
GREEN = "#55d68a"


class ScrollFrame(ttk.Frame):
    """A vertical scrolling surface that keeps the content width responsive."""

    def __init__(self, parent):
        super().__init__(parent, style="App.TFrame")
        self.canvas = tk.Canvas(self, background=BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.content = ttk.Frame(self.canvas, style="App.TFrame")
        self.window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.content.bind("<Configure>", self._content_changed)
        self.canvas.bind("<Configure>", self._canvas_changed)
        self.canvas.bind_all("<MouseWheel>", self._wheel, add="+")

    def _content_changed(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _canvas_changed(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _wheel(self, event):
        if self.winfo_containing(event.x_root, event.y_root) is not None:
            self.canvas.yview_scroll(-int(event.delta / 120), "units")


class App:
    def __init__(self, root):
        self.root = root
        root.title("SCP:SL Auto-Joiner")
        root.geometry("960x700")
        root.minsize(620, 500)
        root.configure(bg=BG)
        self.busy = False
        self.servers = {}
        self.setup_styles()
        try:
            root.iconbitmap(resource_path("assets/app.ico"))
        except tk.TclError:
            pass
        self.build()
        self.refresh()

    def setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("App.TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 25, "bold"))
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 11))
        style.configure("PanelTitle.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 15, "bold"))
        style.configure("Body.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Meta.TLabel", background=PANEL, foreground=CYAN, font=("Segoe UI", 9, "bold"))
        style.configure("Accent.TButton", background=CYAN, foreground="#06111d", font=("Segoe UI", 10, "bold"), padding=(16, 10))
        style.map("Accent.TButton", background=[("active", "#8beaff"), ("disabled", "#2e7181")])
        style.configure("Secondary.TButton", background=CARD, foreground=TEXT, font=("Segoe UI", 10), padding=(13, 9))
        style.map("Secondary.TButton", background=[("active", "#263a55")])
        style.configure("TCombobox", fieldbackground=FIELD, background=FIELD, foreground=TEXT, insertcolor=TEXT, padding=9)
        style.configure("Horizontal.TProgressbar", background=CYAN, troughcolor="#0a1524", bordercolor="#0a1524", lightcolor=CYAN, darkcolor=CYAN)

    def card(self, parent, padding=22):
        return tk.Frame(parent, bg=PANEL, padx=padding, pady=padding, highlightthickness=1, highlightbackground="#20324a")

    def build(self):
        surface = ScrollFrame(self.root)
        surface.pack(fill="both", expand=True)
        outer = surface.content
        outer.columnconfigure(0, weight=1)

        header = ttk.Frame(outer, style="App.TFrame", padding=(28, 26, 28, 20))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="SCP:SL Auto-Joiner", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="A quiet queue assistant for SCP: Secret Laboratory.", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Label(header, text="RESPONSIVE UI · BUILD 2026.08.24-R2", style="Subtitle.TLabel").grid(row=2, column=0, sticky="w", pady=(3, 0))
        self.mode_badge = tk.Label(header, text="READY", bg="#163148", fg=CYAN, font=("Segoe UI", 9, "bold"), padx=12, pady=6)
        self.mode_badge.grid(row=0, column=1, rowspan=2, sticky="e")

        destination = self.card(outer)
        destination.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 14))
        destination.columnconfigure(0, weight=1)
        ttk.Label(destination, text="DESTINATION", style="Meta.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(destination, text="Choose a saved server or enter its saved name.", style="PanelTitle.TLabel").grid(row=1, column=0, sticky="w", pady=(5, 3))
        ttk.Label(destination, text="The endpoint is captured automatically when you use Remember a server.", style="Body.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 14))
        self.server_var = tk.StringVar()
        self.server_box = ttk.Combobox(destination, textvariable=self.server_var, font=("Segoe UI", 12))
        self.server_box.grid(row=3, column=0, sticky="ew")
        self.server_box.bind("<KeyRelease>", self.filter_servers)
        self.server_box.bind("<Return>", lambda _event: self.join())
        actions = ttk.Frame(destination, style="Panel.TFrame")
        actions.grid(row=4, column=0, sticky="w", pady=(16, 0))
        self.join_button = ttk.Button(actions, text="Start auto-join", style="Accent.TButton", command=self.join)
        self.join_button.pack(side="left")
        self.remember_button = ttk.Button(actions, text="Remember a server", style="Secondary.TButton", command=self.remember)
        self.remember_button.pack(side="left", padx=(10, 0))

        status = self.card(outer, padding=18)
        status.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 14))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, text="ACTIVITY", style="Meta.TLabel").grid(row=0, column=0, sticky="w")
        self.status = tk.StringVar(value="Ready. Choose a server and start. Automatic controls are enabled.")
        self.status_label = tk.Label(status, textvariable=self.status, bg=PANEL, fg=TEXT, font=("Segoe UI", 10), anchor="w", justify="left", wraplength=850)
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(6, 9))
        self.progress = ttk.Progressbar(status, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew")

        setup = self.card(outer)
        setup.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 14))
        setup.columnconfigure(0, weight=1)
        setup.columnconfigure(1, weight=1)
        ttk.Label(setup, text="SETUP & RECOVERY", style="Meta.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(setup, text="Automatic mode is the default", style="PanelTitle.TLabel").grid(row=1, column=0, sticky="w", pady=(5, 3))
        ttk.Label(setup, text="It scales clicks to the current SCP:SL window and supports different monitor resolutions.", style="Body.TLabel", wraplength=430).grid(row=2, column=0, sticky="nw", padx=(0, 20))
        self.calibration = tk.StringVar()
        tk.Label(setup, textvariable=self.calibration, bg=PANEL, fg=AMBER, font=("Segoe UI", 10, "bold"), anchor="w", justify="left", wraplength=420).grid(row=1, column=1, rowspan=2, sticky="nw")
        setup_actions = ttk.Frame(setup, style="Panel.TFrame")
        setup_actions.grid(row=3, column=0, columnspan=2, sticky="w", pady=(16, 0))
        ttk.Button(setup_actions, text="Calibrate controls", style="Secondary.TButton", command=self.calibrate).pack(side="left")
        ttk.Button(setup_actions, text="How it works", style="Secondary.TButton", command=self.help).pack(side="left", padx=(10, 0))
        ttk.Button(setup_actions, text="Open data folder", style="Secondary.TButton", command=self.open_folder).pack(side="left", padx=(10, 0))

        notes = self.card(outer, padding=18)
        notes.grid(row=4, column=0, sticky="ew", padx=28, pady=(0, 28))
        notes.columnconfigure(0, weight=1)
        ttk.Label(notes, text="QUICK START", style="Meta.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(notes, text="1  Remember a server   ·   2  Choose it above   ·   3  Start auto-join", style="PanelTitle.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 3))
        ttk.Label(notes, text="Use Calibrate controls only if automatic navigation misses a button after a display or game-layout change.", style="Body.TLabel", wraplength=850).grid(row=2, column=0, sticky="w")

    def refresh(self):
        self.servers = resolver.load_servers()
        self.server_box["values"] = sorted(self.servers)
        cfg = config_mod.load_config()
        manual = cfg.get("navigation_mode") == "manual" and config_mod.calibrated(cfg)
        self.calibration.set("Manual calibration saved and active." if manual else "Automatic control detection enabled.")

    def filter_servers(self, _event=None):
        query = self.server_var.get().lower()
        self.server_box["values"] = sorted(name for name in self.servers if query in name.lower()) or sorted(self.servers)

    def set_status(self, text):
        self.root.after(0, lambda: self.status.set(text))

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.join_button.configure(state=state)
        self.remember_button.configure(state=state)
        self.mode_badge.configure(text="RUNNING" if busy else "READY", bg="#314021" if busy else "#163148", fg=GREEN if busy else CYAN)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()

    def join(self):
        name = self.server_var.get().strip()
        if not name or self.busy:
            return
        self.set_busy(True)
        threading.Thread(target=self.run_join, args=(name,), daemon=True).start()

    def run_join(self, name):
        try:
            result = joiner.run(name, on_status=self.set_status)
            messages = {"success": "Joined successfully.", "gave_up": "Stopped after reaching the retry limit.", "unclear": "Stopped because the game returned an unclear result.", "not_found": "That server is not saved yet.", "launch_failed": "SCP:SL could not be started."}
            self.set_status(messages.get(result, result))
        finally:
            self.root.after(0, lambda: self.set_busy(False))

    def remember(self):
        if self.busy:
            return
        self.set_busy(True)
        threading.Thread(target=self.watch_server, daemon=True).start()

    def watch_server(self):
        try:
            self.set_status("Join the server normally in SCP:SL. Reading its connection details...")
            watcher = logwatch.LogWatcher()
            try:
                match = watcher.wait_for_regex(logwatch.CONNECTING_IP_RE, 120)
            finally:
                watcher.close()
            if match:
                self.root.after(0, lambda: self.save_server(match.group(1), int(match.group(2))))
            else:
                self.set_status("Timed out waiting for a connection attempt.")
                self.root.after(0, lambda: self.set_busy(False))
        except Exception:
            self.set_status("Could not watch the SCP:SL log. Is the game installed?")
            self.root.after(0, lambda: self.set_busy(False))

    def save_server(self, ip, port):
        name = f"{ip}:{port}"
        resolver.remember_server(name, ip, port)
        self.server_var.set(name)
        self.refresh()
        self.status.set(f"Saved {name}.")
        self.set_busy(False)

    def calibrate(self):
        if not self.busy:
            CalibrationWindow(self)

    def help(self):
        HelpWindow(self)

    def open_folder(self):
        os.startfile(os.path.dirname(config_mod.CONFIG_PATH))


class CalibrationWindow:
    steps = [("servers_tab", "Servers tab"), ("direct_connect", "Direct Connect button"), ("ip_field", "IP/Hostname field"), ("connect_button", "Connect button")]

    def __init__(self, app):
        self.app, self.index = app, 0
        self.cfg = config_mod.load_config()
        self.win = tk.Toplevel(app.root)
        self.win.title("Calibrate SCP:SL controls")
        self.win.geometry("600x430")
        self.win.minsize(500, 380)
        self.win.configure(bg=BG)
        self.win.transient(app.root)
        self.win.grab_set()
        try:
            self.win.iconbitmap(resource_path("assets/app.ico"))
        except tk.TclError:
            pass
        frame = ttk.Frame(self.win, style="App.TFrame", padding=28)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Calibrate controls", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Optional manual fallback for this computer. Keep SCP:SL visible, hover the named control, and capture without clicking the game.", style="Subtitle.TLabel", wraplength=520).pack(anchor="w", pady=(6, 18))
        self.bar = ttk.Progressbar(frame, maximum=len(self.steps))
        self.bar.pack(fill="x", pady=(0, 24))
        self.step = ttk.Label(frame, style="PanelTitle.TLabel")
        self.step.pack(anchor="w")
        self.instructions = ttk.Label(frame, style="Subtitle.TLabel", wraplength=520)
        self.instructions.pack(anchor="w", pady=(8, 25))
        ttk.Button(frame, text="Capture current mouse position", style="Accent.TButton", command=self.capture).pack(anchor="w")
        ttk.Button(frame, text="Cancel", style="Secondary.TButton", command=self.close).pack(anchor="w", pady=(14, 0))
        self.show_step()

    def show_step(self):
        if self.index == len(self.steps):
            self.cfg["navigation_mode"] = "manual"
            config_mod.save_config(self.cfg)
            self.app.refresh()
            self.app.status.set("Manual calibration saved and active.")
            return self.close()
        name, title = self.steps[self.index]
        self.step.configure(text=f"Step {self.index + 1} of {len(self.steps)}  ·  {title}")
        self.instructions.configure(text=f"Hover your mouse over SCP:SL's {title}, then click Capture. Do not click the game itself.")
        self.bar.configure(value=self.index)

    def capture(self):
        winput.set_dpi_awareness()
        position = winput.get_cursor_pos()
        if position is None:
            return messagebox.showerror("Calibration error", "Could not read the mouse position.", parent=self.win)
        self.cfg["click_points"][self.steps[self.index][0]] = list(position)
        self.index += 1
        self.show_step()

    def close(self):
        self.win.grab_release()
        self.win.destroy()


class HelpWindow:
    def __init__(self, app):
        win = tk.Toplevel(app.root)
        win.title("How SCP:SL Auto-Joiner works")
        win.geometry("700x560")
        win.minsize(560, 420)
        win.configure(bg=BG)
        frame = ttk.Frame(win, style="App.TFrame", padding=28)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="How it works", style="Title.TLabel").pack(anchor="w")
        box = tk.Text(frame, bg=PANEL, fg=TEXT, relief="flat", wrap="word", font=("Segoe UI", 11), padx=16, pady=16, spacing1=4, spacing3=10)
        box.pack(fill="both", expand=True, pady=(18, 0))
        text = ("1. Automatic mode\nBy default, the app scales its clicks to SCP:SL's current window. Different resolutions and borderless fullscreen layouts do not need calibration.\n\n" "2. Optional calibration\nIf automatic navigation misses a control, use Calibrate controls. Hover each requested game control and capture its position. The manual coordinates are saved only on this computer.\n\n" "3. Remember a server\nJoin a server normally and click Remember a server. The app reads the IP and port from Player.log and saves the endpoint.\n\n" "4. Start auto-join\nChoose the saved server. The app launches SCP:SL if needed, opens Servers and Direct Connect, enters the endpoint, and retries rejected joins in the background.\n\n" "5. Safety\nIt does not read memory, use OCR, modify packets, or bypass anti-cheat. It sends normal Windows input and watches Player.log for the result.")
        box.insert("1.0", text)
        box.configure(state="disabled")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""Native, dark desktop UI for the SCP:SL Auto-Joiner."""
import os
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import config as config_mod
import joiner
import logwatch
import resolver
import winput
from app_paths import resource_path

BG, PANEL, CARD = "#0b1220", "#121d2e", "#18263a"
TEXT, MUTED, CYAN, AMBER = "#eef5ff", "#91a4bd", "#39d8ff", "#ffb84d"


class App:
    def __init__(self, root):
        self.root = root
        root.title("SCP:SL Auto-Joiner")
        root.geometry("820x560")
        root.minsize(720, 500)
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
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure("App.TFrame", background=BG)
        s.configure("Panel.TFrame", background=PANEL)
        s.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 24, "bold"))
        s.configure("Sub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        s.configure("PanelTitle.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 13, "bold"))
        s.configure("Body.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 10))
        s.configure("Accent.TButton", background=CYAN, foreground="#06111d", font=("Segoe UI", 10, "bold"), padding=(14, 9))
        s.map("Accent.TButton", background=[("active", "#8beaff")])
        s.configure("Secondary.TButton", background=CARD, foreground=TEXT, font=("Segoe UI", 10), padding=(11, 8))
        s.map("Secondary.TButton", background=[("active", "#263a55")])
        s.configure("TCombobox", fieldbackground="#0f1a2a", background="#0f1a2a", foreground=TEXT, insertcolor=TEXT, padding=8)
        s.configure("Horizontal.TProgressbar", background=CYAN, troughcolor="#0a1524", bordercolor="#0a1524", lightcolor=CYAN, darkcolor=CYAN)

    def build(self):
        outer = ttk.Frame(self.root, style="App.TFrame", padding=28)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="SCP:SL Auto-Joiner", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Stay in the queue. The joiner handles retries while you do something else.", style="Sub.TLabel").pack(anchor="w", pady=(4, 22))
        content = ttk.Frame(outer, style="App.TFrame")
        content.pack(fill="both", expand=True)
        left = ttk.Frame(content, style="Panel.TFrame", padding=24)
        left.pack(side="left", fill="both", expand=True, padx=(0, 14))
        right = ttk.Frame(content, style="Panel.TFrame", padding=24, width=255)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        ttk.Label(left, text="Join a server", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(left, text="Choose a saved server or type its name. Suggestions appear as you type.", style="Body.TLabel", wraplength=470).pack(anchor="w", pady=(6, 18))
        ttk.Label(left, text="SERVER", style="Body.TLabel").pack(anchor="w")
        self.server_var = tk.StringVar()
        self.server_box = ttk.Combobox(left, textvariable=self.server_var, font=("Segoe UI", 12))
        self.server_box.pack(fill="x", pady=(5, 16))
        self.server_box.bind("<KeyRelease>", self.filter_servers)
        self.server_box.bind("<Return>", lambda _e: self.join())
        row = ttk.Frame(left, style="Panel.TFrame")
        row.pack(fill="x")
        self.join_button = ttk.Button(row, text="Start auto-join", style="Accent.TButton", command=self.join)
        self.join_button.pack(side="left")
        self.remember_button = ttk.Button(row, text="Remember a server", style="Secondary.TButton", command=self.remember)
        self.remember_button.pack(side="left", padx=(10, 0))
        card = tk.Frame(left, bg=CARD, padx=16, pady=14)
        card.pack(fill="x", pady=(26, 0))
        tk.Label(card, text="STATUS", bg=CARD, fg=CYAN, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.status = tk.StringVar(value="Ready. Calibrate once, remember a server, then start.")
        tk.Label(card, textvariable=self.status, bg=CARD, fg=TEXT, font=("Segoe UI", 10), anchor="w", justify="left", wraplength=470).pack(fill="x", pady=(6, 8))
        self.progress = ttk.Progressbar(card, mode="indeterminate")
        self.progress.pack(fill="x")
        ttk.Label(right, text="Setup", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(right, text="Every computer gets its own calibration because monitor scaling and window positions differ.", style="Body.TLabel", wraplength=205).pack(anchor="w", pady=(7, 16))
        self.calibration = tk.StringVar()
        tk.Label(right, textvariable=self.calibration, bg=PANEL, fg=AMBER, font=("Segoe UI", 10, "bold"), wraplength=205, justify="left").pack(anchor="w", pady=(0, 14))
        ttk.Button(right, text="Calibrate this computer", style="Secondary.TButton", command=self.calibrate).pack(fill="x", pady=4)
        ttk.Button(right, text="How it works", style="Secondary.TButton", command=self.help).pack(fill="x", pady=4)
        ttk.Button(right, text="Open data folder", style="Secondary.TButton", command=self.open_folder).pack(fill="x", pady=4)
        ttk.Separator(right).pack(fill="x", pady=22)
        ttk.Label(right, text="Quick start", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(right, text="1. Calibrate\n2. Remember a server\n3. Start auto-join", style="Body.TLabel", justify="left").pack(anchor="w", pady=(7, 0))

    def refresh(self):
        self.servers = resolver.load_servers()
        self.server_box["values"] = sorted(self.servers)
        ok = config_mod.calibrated(config_mod.load_config())
        self.calibration.set("Calibration saved for this computer" if ok else "Calibration needed before joining")

    def filter_servers(self, _event=None):
        q = self.server_var.get().lower()
        self.server_box["values"] = sorted(n for n in self.servers if q in n.lower()) or sorted(self.servers)

    def set_status(self, text):
        self.root.after(0, lambda: self.status.set(text))

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.join_button.configure(state=state)
        self.remember_button.configure(state=state)
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
            messages = {"success": "Joined successfully!", "gave_up": "Stopped after reaching the retry limit.", "unclear": "Stopped because the game returned an unclear result.", "not_calibrated": "Calibrate this computer first.", "not_found": "That server is not saved yet.", "launch_failed": "SCP:SL could not be started."}
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
        name = simpledialog.askstring("Save server", f"What should I call this server?\n\nDetected: {ip}:{port}", parent=self.root)
        if name and name.strip():
            resolver.remember_server(name.strip(), ip, port)
            self.server_var.set(name.strip())
            self.refresh()
            self.status.set(f"Saved {name.strip()}  •  {ip}:{port}")
        else:
            self.status.set("Server was not saved.")
        self.set_busy(False)

    def calibrate(self):
        if not self.busy:
            CalibrationWindow(self)

    def help(self):
        HelpWindow(self)

    def open_folder(self):
        os.startfile(os.path.dirname(config_mod.CONFIG_PATH))


class CalibrationWindow:
    steps = [("play", "Play button"), ("servers_tab", "Servers tab"), ("internet_tab", "Internet tab"), ("direct_connect", "Direct Connect"), ("ip_field", "IP:port field"), ("connect_button", "Connect button")]

    def __init__(self, app):
        self.app, self.index = app, 0
        self.cfg = config_mod.load_config()
        self.win = tk.Toplevel(app.root)
        self.win.title("Calibrate SCP:SL")
        self.win.geometry("540x350")
        self.win.configure(bg=BG)
        self.win.transient(app.root)
        self.win.grab_set()
        try:
            self.win.iconbitmap(resource_path("assets/app.ico"))
        except tk.TclError:
            pass
        frame = ttk.Frame(self.win, style="App.TFrame", padding=28)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Calibrate this computer", style="Title.TLabel").pack(anchor="w")
        self.bar = ttk.Progressbar(frame, maximum=len(self.steps))
        self.bar.pack(fill="x", pady=(18, 24))
        self.step = ttk.Label(frame, style="PanelTitle.TLabel")
        self.step.pack(anchor="w")
        self.instructions = ttk.Label(frame, style="Sub.TLabel", wraplength=470)
        self.instructions.pack(anchor="w", pady=(8, 25))
        ttk.Button(frame, text="Capture current mouse position", style="Accent.TButton", command=self.capture).pack(anchor="w")
        ttk.Button(frame, text="Cancel", style="Secondary.TButton", command=self.close).pack(anchor="w", pady=(14, 0))
        self.show_step()

    def show_step(self):
        if self.index == len(self.steps):
            config_mod.save_config(self.cfg)
            self.app.refresh()
            self.app.status.set("Calibration complete. You can now remember a server or start joining.")
            return self.close()
        name, title = self.steps[self.index]
        self.step.configure(text=f"Step {self.index + 1} of {len(self.steps)}  •  {title}")
        self.instructions.configure(text=f"Hover your mouse over SCP:SL’s {title}, then click Capture. Do not click the game itself.")
        self.bar.configure(value=self.index)

    def capture(self):
        winput.set_dpi_awareness()
        pos = winput.get_cursor_pos()
        if pos is None:
            return messagebox.showerror("Calibration error", "Could not read the mouse position.", parent=self.win)
        self.cfg["click_points"][self.steps[self.index][0]] = list(pos)
        self.index += 1
        self.show_step()

    def close(self):
        self.win.grab_release()
        self.win.destroy()


class HelpWindow:
    def __init__(self, app):
        win = tk.Toplevel(app.root)
        win.title("How SCP:SL Auto-Joiner works")
        win.geometry("650x500")
        win.configure(bg=BG)
        frame = ttk.Frame(win, style="App.TFrame", padding=28)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="How it works", style="Title.TLabel").pack(anchor="w")
        text = ("1. Calibration\nThe app remembers where SCP:SL’s buttons are on your monitor. Do this once per computer, and repeat it if you move or resize the game.\n\n" "2. Remember a server\nJoin a server normally and give it a friendly name. The app reads the IP and port from the game’s own log.\n\n" "3. Auto-join\nChoose the saved name and start. The app opens Direct Connect, enters the address, and retries rejected joins in the background.\n\n" "4. Safety\nIt does not read memory, use OCR, modify packets, or bypass anti-cheat. It sends normal clicks and watches Player.log for the result.")
        box = tk.Text(frame, bg=PANEL, fg=TEXT, relief="flat", wrap="word", font=("Segoe UI", 11), padx=16, pady=16)
        box.pack(fill="both", expand=True, pady=(18, 0))
        box.insert("1.0", text)
        box.configure(state="disabled")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

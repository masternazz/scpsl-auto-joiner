"""Small GUI for joining saved SCP:SL servers or remembering new ones."""
import threading
import tkinter as tk
from tkinter import simpledialog

import joiner
import logwatch
import resolver


class App:
    def __init__(self, root):
        self.root = root
        root.title("SCP:SL Auto-Joiner")

        tk.Label(root, text="Server name:").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self.name_var = tk.StringVar()
        tk.Entry(root, textvariable=self.name_var, width=30).grid(row=0, column=1, padx=8, pady=8)

        tk.Button(root, text="Join", command=self.on_join).grid(row=1, column=0, padx=8, pady=4)
        tk.Button(root, text="Remember a server", command=self.on_remember).grid(
            row=1, column=1, padx=8, pady=4)

        self.status_var = tk.StringVar(value="Idle.")
        tk.Label(root, textvariable=self.status_var, wraplength=320, justify="left").grid(
            row=2, column=0, columnspan=2, padx=8, pady=8, sticky="w")

    def set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def on_join(self):
        name = self.name_var.get().strip()
        if name:
            threading.Thread(target=self._run_join, args=(name,), daemon=True).start()

    def _run_join(self, name):
        joiner.run(name, on_status=self.set_status)

    def on_remember(self):
        threading.Thread(target=self._run_remember, daemon=True).start()

    def _run_remember(self):
        self.set_status("Click Play on the server you want to remember, in the game...")
        watcher = logwatch.LogWatcher()
        try:
            match = watcher.wait_for_regex(logwatch.CONNECTING_IP_RE, 120)
        finally:
            watcher.close()
        if match:
            ip, port = match.group(1), int(match.group(2))
            self.root.after(0, lambda: self._prompt_and_save(ip, port))
        else:
            self.set_status("Timed out waiting for a connection attempt.")

    def _prompt_and_save(self, ip, port):
        name = simpledialog.askstring(
            "Remember server", f"Name this server ({ip}:{port}):", parent=self.root)
        if name and name.strip():
            name = name.strip()
            resolver.remember_server(name, ip, port)
            self.status_var.set(f"Saved '{name}' -> {ip}:{port}")
        else:
            self.status_var.set("Cancelled.")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""Tails Player.log and classifies join-attempt outcomes. No OCR, no screen
reading — the game's own log tells us everything we need. Signatures verified
live against the real client on 2026-08-24; see the design spec."""
import os
import re
import time

SUCCESS_MARK = "Scene Manager: Loaded scene 'Facility'"
DELAY_MARK = "Connection has been delayed by"
DISCONNECT_MARK = "OnPeerDisconnected"
CANCEL_MARK = "Connection Failed"
CONNECTING_MARK = "Connecting to"
RESPONSE_MARK = "Response sent. ID:"
POLLING_STOP_MARK = "PollingLoop stopped"
MENU_MARK = "Scene Manager: Loaded scene 'NewMainMenu'"
CONNECTING_IP_RE = re.compile(r"Connection IP set to ([0-9.]+), port: (\d+)")

DEFAULT_LOG_PATH = os.path.join(
    os.environ.get("USERPROFILE", ""), "AppData", "LocalLow",
    "Northwood", "SCPSL", "Player.log")


def classify_log_text(text):
    """Classify accumulated log text since a connect attempt started.
    Returns "success", "rejected", "cancelled", "connecting", or None.
    Checked in this order so a later success in the same buffer always wins
    over an earlier rejection (a retry can succeed after prior failures)."""
    if SUCCESS_MARK in text:
        return "success"
    if DELAY_MARK in text and DISCONNECT_MARK in text:
        return "rejected"
    if RESPONSE_MARK in text:
        after_response = text.rsplit(RESPONSE_MARK, 1)[1]
        if after_response.count(POLLING_STOP_MARK) >= 2:
            return "rejected"
    if CANCEL_MARK in text:
        return "cancelled"
    if CONNECTING_MARK in text:
        return "connecting"
    return None


class LogWatcher:
    """Tails Player.log from the moment it's opened (not from the start of
    the file) — each instance only sees lines written after it was created."""

    def __init__(self, path=None):
        self.path = path or DEFAULT_LOG_PATH
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        try:
            self._fh = open(self.path, "r", encoding="utf-8", errors="replace")
        except FileNotFoundError:
            self._fh = open(self.path, "a+", encoding="utf-8", errors="replace")
        self._file_signature = self._signature()
        self._fh.seek(0, os.SEEK_END)
        self._pending = ""

    def _signature(self):
        try:
            stat = os.stat(self.path)
        except OSError:
            return None
        return stat.st_dev, stat.st_ino

    def _refresh_handle(self):
        """Follow Unity if it truncates/replaces Player.log during startup."""
        try:
            size = os.path.getsize(self.path)
            position = self._fh.tell()
        except (OSError, ValueError):
            return
        signature = self._signature()
        if signature == self._file_signature and size >= position:
            return
        self._fh.close()
        self._fh = open(self.path, "r", encoding="utf-8", errors="replace")
        self._file_signature = signature
        self._fh.seek(0)

    def read_new(self):
        self._refresh_handle()
        text, self._pending = self._pending + self._fh.read(), ""
        return text

    def wait_for_outcome(self, timeout_s, poll_interval=0.25, stop_on_connecting=False, stop_event=None):
        """Accumulate new log text and classify it until a terminal outcome
        (success/rejected/cancelled), a timeout, or — if stop_on_connecting —
        the first sighting of "connecting" (used to confirm a click landed,
        without waiting the full attempt timeout for a final result)."""
        deadline = time.monotonic() + timeout_s
        buf = ""
        while time.monotonic() < deadline:
            if stop_event and stop_event.is_set():
                return "stopped"
            buf += self.read_new()
            result = classify_log_text(buf)
            if result in ("success", "rejected", "cancelled"):
                return result
            if result == "connecting" and stop_on_connecting:
                return "connecting"
            time.sleep(poll_interval)
        buf += self.read_new()
        return classify_log_text(buf) or "timeout"

    def wait_for_regex(self, pattern, timeout_s, poll_interval=0.25, stop_event=None):
        """Wait for a compiled regex to appear in new log text. Returns the
        match, or None on timeout."""
        deadline = time.monotonic() + timeout_s
        buf = ""
        while time.monotonic() < deadline:
            if stop_event and stop_event.is_set():
                return None
            buf += self.read_new()
            m = pattern.search(buf)
            if m:
                # Preserve anything logged after the marker. A fast join can
                # write Connecting and the final outcome in the same read.
                self._pending = buf[m.end():]
                return m
            time.sleep(poll_interval)
        return None

    def wait_for_marker(self, marker, timeout_s, poll_interval=0.25, stop_event=None):
        """Wait for a plain substring (e.g. MENU_MARK) to appear."""
        return self.wait_for_regex(re.compile(re.escape(marker)), timeout_s, poll_interval, stop_event) is not None

    def close(self):
        self._fh.close()

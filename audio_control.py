"""Best-effort per-process Windows audio-session muting for SCP:SL."""
import threading

GAME_PROCESS_NAMES = {"scpsl.exe", "scpsl-win64-shipping.exe"}


class GameAudioMute:
    def __init__(self, on_status=None):
        self.on_status = on_status
        self._stop = threading.Event()
        self._thread = None
        self._sessions = {}
        try:
            from pycaw.pycaw import AudioUtilities  # noqa: F401
            self.available = True
        except Exception:
            self.available = False

    def _status(self, message):
        if self.on_status:
            self.on_status(message)

    @staticmethod
    def _game_sessions():
        from pycaw.pycaw import AudioUtilities
        result = []
        for session in AudioUtilities.GetAllSessions():
            process = session.Process
            if process and process.name().casefold() in GAME_PROCESS_NAMES:
                result.append(session)
        return result

    def _mute_current(self):
        try:
            sessions = self._game_sessions()
        except Exception as exc:
            self._status(f"Game audio mute unavailable: {exc}")
            return
        for session in sessions:
            volume = session.SimpleAudioVolume
            key = id(volume)
            if key not in self._sessions:
                was_muted = bool(volume.GetMute())
                self._sessions[key] = (volume, was_muted)
                volume.SetMute(1, None)
                self._status("SCP:SL audio muted while auto-join is running.")

    def start(self):
        if not self.available:
            self._status("Game audio mute is unavailable; the run will continue without muting.")
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="scpsl-audio-mute", daemon=True)
        self._thread.start()
        return True

    def _run(self):
        while not self._stop.is_set():
            self._mute_current()
            self._stop.wait(0.5)

    def stop(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
        for volume, was_muted in list(self._sessions.values()):
            try:
                volume.SetMute(1 if was_muted else 0, None)
            except Exception:
                pass
        if self._sessions:
            self._status("SCP:SL audio restored.")
        self._sessions.clear()


def start_for_run(enabled, on_status=None):
    if not enabled:
        return None
    controller = GameAudioMute(on_status=on_status)
    controller.start()
    return controller

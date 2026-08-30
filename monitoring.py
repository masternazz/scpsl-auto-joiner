"""Opt-in background server monitoring with a bounded, jittered sweep."""
import random
import threading
import time


class BackgroundMonitor:
    def __init__(self, servers, query, record, interval=60, jitter=5, max_servers=50):
        self.servers = list(servers)[: int(max_servers)]
        self.query = query
        self.record = record
        self.interval = max(1.0, float(interval))
        self.jitter = max(0.0, float(jitter))
        self._stop = threading.Event()
        self._thread = None

    def sample_once(self):
        count = 0
        for server in self.servers:
            if self._stop.is_set():
                break
            try:
                status = self.query(server) or {"available": False}
                self.record(server, status)
            except Exception as exc:
                self.record(server, {"available": False, "error": str(exc)})
            count += 1
        return count

    def start(self):
        if self._thread and self._thread.is_alive():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="server-monitor", daemon=True)
        self._thread.start()
        return True

    def _run(self):
        while not self._stop.is_set():
            self.sample_once()
            delay = self.interval + random.uniform(-self.jitter, self.jitter)
            self._stop.wait(max(1.0, delay))

    def stop(self):
        self._stop.set()
        return True

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

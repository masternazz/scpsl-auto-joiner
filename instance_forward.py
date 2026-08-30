"""Same-user command forwarding for registered destination links."""
import json
from multiprocessing.connection import Client, Listener
import threading


def endpoint(user_name=None):
    safe = str(user_name or "default").replace("\\", "_").replace("/", "_")
    return rf"\\.\pipe\scpsl-autojoin-{safe}"


def send(payload, address=None):
    with Client(address or endpoint(), family="AF_PIPE") as connection:
        connection.send(json.dumps(payload, separators=(",", ":")))


def receive(connection):
    payload = json.loads(connection.recv())
    if not isinstance(payload, dict) or payload.get("command") != "import_destination":
        raise ValueError("unsupported forwarded command")
    return payload


def dispatch_payload(payload, handler):
    payload = payload if isinstance(payload, dict) else json.loads(payload)
    if payload.get("command") != "import_destination" or not isinstance(payload.get("data"), str):
        raise ValueError("unsupported forwarded command")
    handler(payload)
    return True


class ForwardingServer:
    """A same-user named-pipe receiver for URI imports."""
    def __init__(self, handler, address=None):
        self.handler = handler
        self.address = address or endpoint()
        self._stop = threading.Event()
        self._listener = None
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return False
        self._stop.clear()
        self._listener = Listener(self.address, family="AF_PIPE")
        self._thread = threading.Thread(target=self._run, name="destination-forwarder", daemon=True)
        self._thread.start()
        return True

    def _run(self):
        while not self._stop.is_set():
            try:
                connection = self._listener.accept()
            except (OSError, EOFError):
                break
            try:
                with connection:
                    dispatch_payload(connection.recv(), self.handler)
            except (OSError, EOFError, ValueError, TypeError, json.JSONDecodeError):
                continue

    def stop(self):
        self._stop.set()
        if self._listener:
            self._listener.close()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)

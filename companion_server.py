"""Minimal optional LabAPI companion HTTP contract for an owned server."""
import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from companion import TokenStore


class RequestRateLimiter:
    """Small per-client limiter for the owner-operated status endpoint."""
    def __init__(self, interval=1.0):
        self.interval = float(interval)
        self._last = {}
        self._lock = threading.Lock()

    def allow(self, client, now=None):
        now = time.monotonic() if now is None else float(now)
        with self._lock:
            previous = self._last.get(str(client))
            if previous is not None and now - previous < self.interval:
                return False
            self._last[str(client)] = now
            return True


def make_handler(token_store, status_provider):
    limiter = RequestRateLimiter()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/v1/status":
                self.send_error(404); return
            auth = self.headers.get("Authorization", "")
            supplied = auth[7:] if auth.startswith("Bearer ") else ""
            if not token_store.verify(supplied):
                self.send_error(401); return
            if not limiter.allow(self.client_address[0]):
                self.send_error(429); return
            body = json.dumps(status_provider(), separators=(",", ":")).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, *_args):
            return
    return Handler


def serve(host, port, token, status_provider):
    server = HTTPServer((host, int(port)), make_handler(TokenStore.from_token(token), status_provider))
    return server

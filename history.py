"""Small local SQLite history store for server observations."""
import datetime as _dt
import sqlite3
import os


class ServerHistory:
    def __init__(self, path, retention_days=30, max_rows=250000):
        self.path = str(path)
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self.retention_days = int(retention_days)
        self.max_rows = int(max_rows)
        try:
            db = self._connect()
            try:
                db.execute("PRAGMA integrity_check")
                db.execute("CREATE TABLE IF NOT EXISTS server_samples (id INTEGER PRIMARY KEY, server_id TEXT NOT NULL, observed_at TEXT NOT NULL, online INTEGER NOT NULL, players INTEGER, max_players INTEGER, latency_ms REAL)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_server_samples_server_time ON server_samples(server_id, observed_at)")
            finally:
                db.close()
        except sqlite3.DatabaseError:
            # A torn/corrupt local history database must never block app
            # startup. Keep it for diagnosis and start a clean history store.
            backup = self.path + ".corrupt"
            index = 1
            while os.path.exists(backup):
                backup = f"{self.path}.corrupt.{index}"; index += 1
            try: os.replace(self.path, backup)
            except OSError: pass
            db = self._connect()
            try:
                db.execute("CREATE TABLE IF NOT EXISTS server_samples (id INTEGER PRIMARY KEY, server_id TEXT NOT NULL, observed_at TEXT NOT NULL, online INTEGER NOT NULL, players INTEGER, max_players INTEGER, latency_ms REAL)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_server_samples_server_time ON server_samples(server_id, observed_at)")
            finally:
                db.close()

    def _connect(self):
        return sqlite3.connect(self.path)

    def record(self, server_id, online, players, max_players, latency_ms, observed_at=None):
        stamp = observed_at or _dt.datetime.now(_dt.timezone.utc).isoformat()
        with self._connect() as db:
            db.execute("INSERT INTO server_samples(server_id, observed_at, online, players, max_players, latency_ms) VALUES (?, ?, ?, ?, ?, ?)", (str(server_id), stamp, int(bool(online)), players, max_players, latency_ms))
            cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=self.retention_days)).isoformat()
            db.execute("DELETE FROM server_samples WHERE observed_at < ?", (cutoff,))
            db.execute("DELETE FROM server_samples WHERE id NOT IN (SELECT id FROM server_samples ORDER BY observed_at DESC LIMIT ?)", (self.max_rows,))

    def recent(self, server_id, limit=100):
        with self._connect() as db:
            rows = db.execute("SELECT observed_at, online, players, max_players, latency_ms FROM server_samples WHERE server_id=? ORDER BY observed_at DESC LIMIT ?", (str(server_id), int(limit))).fetchall()
        return [{"observed_at": r[0], "online": bool(r[1]), "players": r[2], "max_players": r[3], "latency_ms": r[4]} for r in rows]

    def insights(self, server_id, limit=1000):
        rows = self.recent(server_id, limit)
        online = [r for r in rows if r["online"]]
        full = [r for r in online if r["max_players"] and r["players"] is not None and r["players"] >= r["max_players"]]
        now = _dt.datetime.now(_dt.timezone.utc)
        periods = {}
        for label, days in (("24h", 1), ("7d", 7), ("30d", 30)):
            cutoff = now - _dt.timedelta(days=days)
            subset = []
            for row in rows:
                try:
                    stamp = _dt.datetime.fromisoformat(row["observed_at"])
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=_dt.timezone.utc)
                    if stamp >= cutoff:
                        subset.append(row)
                except (TypeError, ValueError):
                    continue
            periods[label] = {"samples": len(subset), "online_samples": sum(1 for row in subset if row["online"]), "peak_players": max((row["players"] or 0 for row in subset if row["online"]), default=0)}
        latencies = [r["latency_ms"] for r in online if r["latency_ms"] is not None]
        return {"samples": len(rows), "online_samples": len(online), "peak_players": max((r["players"] or 0 for r in online), default=0), "average_latency_ms": sum(latencies) / max(1, len(latencies)), "full_frequency": len(full) / max(1, len(online)), "availability_likelihood": len(online) / max(1, len(rows)), "periods": periods}

    def heatmap(self, server_id, limit=5000, minimum_samples=8):
        """Return local weekday/hour availability evidence without prediction claims.

        Each cell represents observations made in that UTC weekday/hour.  The
        UI labels sparse data as insufficient rather than inventing a schedule.
        """
        rows = self.recent(server_id, limit)
        buckets = {(day, hour): [] for day in range(7) for hour in range(24)}
        for row in rows:
            try:
                stamp = _dt.datetime.fromisoformat(row["observed_at"])
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=_dt.timezone.utc)
                buckets[(stamp.weekday(), stamp.hour)].append(row)
            except (TypeError, ValueError):
                continue
        cells = []
        for (day, hour), values in buckets.items():
            online = [item for item in values if item["online"]]
            with_capacity = [item for item in online if item["players"] is not None and item["max_players"]]
            cells.append({
                "weekday": day, "hour": hour, "samples": len(values),
                "availability": sum(1 for item in with_capacity if item["players"] < item["max_players"]) / max(1, len(values)),
                "players_low": min((item["players"] for item in online if item["players"] is not None), default=None),
                "players_high": max((item["players"] for item in online if item["players"] is not None), default=None),
            })
        return {"ready": len(rows) >= minimum_samples, "samples": len(rows), "timezone": "UTC", "cells": cells}

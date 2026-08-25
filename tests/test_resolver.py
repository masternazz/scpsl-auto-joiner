import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import resolver as resolver_mod


def test_parse_a2s_info_name():
    packet = b"\xff\xff\xff\xffI\x11Northwood Official Server - Canada #2\x00Facility\x00"
    assert resolver_mod._parse_a2s_info(packet) == "Northwood Official Server - Canada #2"


def test_parse_a2s_info_strips_rich_text_tags():
    packet = b"\xff\xff\xff\xffI\x11<color=red>King's</color>  Playground\x00Facility\x00"
    assert resolver_mod._parse_a2s_info(packet) == "King's Playground"


def test_parse_a2s_info_rejects_unrelated_packet():
    assert resolver_mod._parse_a2s_info(b"not an info response") is None


def test_resolve_returns_none_when_no_servers(tmp_path):
    path = str(tmp_path / "servers.json")
    assert resolver_mod.resolve("canada", path) is None


def test_remember_then_resolve_close_match(tmp_path):
    path = str(tmp_path / "servers.json")
    resolver_mod.remember_server("Northwood Canada 2", "1.2.3.4", 7777, path)
    result = resolver_mod.resolve("canada 2", path)
    assert result == ("Northwood Canada 2", "1.2.3.4", 7777)


def test_resolve_no_close_match_returns_none(tmp_path):
    path = str(tmp_path / "servers.json")
    resolver_mod.remember_server("Northwood Canada 2", "1.2.3.4", 7777, path)
    assert resolver_mod.resolve("totally unrelated xyz", path) is None


def test_remember_server_overwrites_same_name(tmp_path):
    path = str(tmp_path / "servers.json")
    resolver_mod.remember_server("Canada 2", "1.2.3.4", 7777, path)
    resolver_mod.remember_server("Canada 2", "5.6.7.8", 8888, path)
    result = resolver_mod.resolve("Canada 2", path)
    assert result == ("Canada 2", "5.6.7.8", 8888)


def test_forget_server_removes_only_selected_name(tmp_path):
    path = str(tmp_path / "servers.json")
    resolver_mod.remember_server("Canada 2", "1.2.3.4", 7777, path)
    resolver_mod.remember_server("Canada 3", "5.6.7.8", 7778, path)

    assert resolver_mod.forget_server("Canada 2", path) is True
    assert resolver_mod.load_servers(path) == {
        "Canada 3": {"ip": "5.6.7.8", "port": 7778},
    }
    assert resolver_mod.forget_server("Missing", path) is False


def test_query_server_parses_a2s_info_metadata(tmp_path, monkeypatch):
    del tmp_path
    packet = (
        b"\xff\xff\xff\xffI\x11Name\x00Map\x00Folder\x00Game\x00"
        + b"\x01\x00\x05\x32\x10\x64\x00\x01\x01\x01.2.3.4\x00"
    )
    class FakeSocket:
        def settimeout(self, value):
            self.timeout = value
        def sendto(self, data, address):
            self.address = address
        def recvfrom(self, size):
            return packet, ("1.2.3.4", 7777)
        def close(self):
            pass
    monkeypatch.setattr(resolver_mod.socket, "socket", lambda *args: FakeSocket())
    result = resolver_mod.query_server("1.2.3.4", 7777)
    assert result["name"] == "Name"
    assert result["map"] == "Map"
    assert result["players"] == 5
    assert result["max_players"] == 50
    assert result["available"] is True
    assert "latency_ms" in result


def test_query_server_handles_split_challenge(tmp_path, monkeypatch):
    del tmp_path
    challenge = b"\xff\xff\xff\xffA\x01\x02\x03\x04"
    info = b"\xff\xff\xff\xffI\x11Name\x00Map\x00Folder\x00Game\x00\x01\x00\x01\x10\x00\x10\x20\x01\x00"
    class FakeSocket:
        def __init__(self):
            self.sent = []
        def settimeout(self, value):
            pass
        def sendto(self, data, address):
            self.sent.append(data)
        def recvfrom(self, size):
            return (challenge if len(self.sent) == 1 else info), ("1.2.3.4", 7777)
        def close(self):
            pass
    sock = FakeSocket()
    monkeypatch.setattr(resolver_mod.socket, "socket", lambda *args: sock)
    assert resolver_mod.query_server("1.2.3.4", 7777)["name"] == "Name"
    assert sock.sent[1].endswith(b"\x01\x02\x03\x04")


def test_query_server_returns_none_on_timeout(monkeypatch):
    class FakeSocket:
        def settimeout(self, value):
            pass
        def sendto(self, data, address):
            pass
        def recvfrom(self, size):
            raise TimeoutError()
        def close(self):
            pass
    monkeypatch.setattr(resolver_mod.socket, "socket", lambda *args: FakeSocket())
    assert resolver_mod.query_server("1.2.3.4", 7777) is None

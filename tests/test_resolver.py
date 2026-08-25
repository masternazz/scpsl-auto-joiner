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

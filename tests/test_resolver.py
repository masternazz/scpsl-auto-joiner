import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import resolver as resolver_mod


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

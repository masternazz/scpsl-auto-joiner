import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from logwatch import classify_log_text, CONNECTING_IP_RE


def test_success_signature():
    text = "Some noise\nScene Manager: Loaded scene 'Facility' [Assets/_Scenes/Facility.unity]\n"
    assert classify_log_text(text) == "success"


def test_rejected_signature():
    text = (
        "Connecting to 1.2.3.4!\n"
        "Connection has been delayed by 1 seconds.\n"
        "NullReferenceException: Object reference not set to an instance of an object.\n"
        "  at Mirror.LiteNetLib4Mirror.LiteNetLib4MirrorClient+<>c__DisplayClass8_0."
        "<OnPeerDisconnected>b__0 () [0x00000] in <00000000000000000000000000000000>:0 \n"
    )
    assert classify_log_text(text) == "rejected"


def test_cancelled_signature():
    text = (
        "Connecting to 1.2.3.4!\n"
        "Connection IP set to 1.2.3.4, port: 7777\n"
        "Connection Failed\n"
        "IP: 1.2.3.4\n"
        "Port: 7777\n"
    )
    assert classify_log_text(text) == "cancelled"


def test_connecting_only_is_not_terminal():
    text = "Connecting to 1.2.3.4!\nConnection IP set to 1.2.3.4, port: 7777\n"
    assert classify_log_text(text) == "connecting"


def test_unrelated_noise_is_none():
    text = "PollingLoop started\nLoading IPHistory\n"
    assert classify_log_text(text) is None


def test_success_wins_even_after_a_prior_rejection_in_the_same_buffer():
    text = (
        "Connection has been delayed by 1 seconds.\n"
        "...OnPeerDisconnected...\n"
        "Scene Manager: Loaded scene 'Facility'\n"
    )
    assert classify_log_text(text) == "success"


def test_connecting_ip_regex_captures_ip_and_port():
    m = CONNECTING_IP_RE.search("Connection IP set to 158.69.52.5, port: 7777\n")
    assert m is not None
    assert m.group(1) == "158.69.52.5"
    assert m.group(2) == "7777"

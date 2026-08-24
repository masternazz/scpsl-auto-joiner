import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from logwatch import classify_log_text, CONNECTING_IP_RE, LogWatcher, MENU_MARK


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


# LogWatcher integration tests with real temp files
def test_logwatcher_wait_for_outcome_success(tmp_path):
    """wait_for_outcome finds and returns 'success' when success signature appears."""
    log_file = tmp_path / "test.log"
    log_file.write_text("")

    watcher = LogWatcher(path=str(log_file))

    def write_success():
        time.sleep(0.1)
        log_file.write_text(log_file.read_text() + "Scene Manager: Loaded scene 'Facility'\n")

    t = threading.Thread(target=write_success)
    t.start()
    result = watcher.wait_for_outcome(timeout_s=2.0)
    t.join()
    watcher.close()

    assert result == "success"


def test_logwatcher_wait_for_outcome_rejected(tmp_path):
    """wait_for_outcome finds and returns 'rejected' when rejection signature appears."""
    log_file = tmp_path / "test.log"
    log_file.write_text("")

    watcher = LogWatcher(path=str(log_file))

    def write_rejected():
        time.sleep(0.1)
        log_file.write_text(
            log_file.read_text() +
            "Connection has been delayed by 1 seconds.\n...OnPeerDisconnected...\n"
        )

    t = threading.Thread(target=write_rejected)
    t.start()
    result = watcher.wait_for_outcome(timeout_s=2.0)
    t.join()
    watcher.close()

    assert result == "rejected"


def test_logwatcher_wait_for_outcome_timeout(tmp_path):
    """wait_for_outcome returns 'timeout' when no outcome found within timeout."""
    log_file = tmp_path / "test.log"
    log_file.write_text("")

    watcher = LogWatcher(path=str(log_file))
    result = watcher.wait_for_outcome(timeout_s=0.2)
    watcher.close()

    assert result == "timeout"


def test_logwatcher_wait_for_outcome_stop_on_connecting(tmp_path):
    """wait_for_outcome with stop_on_connecting=True returns 'connecting' early."""
    log_file = tmp_path / "test.log"
    log_file.write_text("")

    watcher = LogWatcher(path=str(log_file))

    def write_connecting():
        time.sleep(0.05)
        log_file.write_text(log_file.read_text() + "Connecting to 1.2.3.4!\n")

    t = threading.Thread(target=write_connecting)
    t.start()
    start = time.monotonic()
    result = watcher.wait_for_outcome(timeout_s=2.0, stop_on_connecting=True)
    elapsed = time.monotonic() - start
    t.join()
    watcher.close()

    assert result == "connecting"
    assert elapsed < 1.0


def test_logwatcher_wait_for_marker_found(tmp_path):
    """wait_for_marker returns True when marker is found."""
    log_file = tmp_path / "test.log"
    log_file.write_text("")

    watcher = LogWatcher(path=str(log_file))

    def write_marker():
        time.sleep(0.1)
        log_file.write_text(log_file.read_text() + "Scene Manager: Loaded scene 'NewMainMenu'\n")

    t = threading.Thread(target=write_marker)
    t.start()
    result = watcher.wait_for_marker(MENU_MARK, timeout_s=2.0)
    t.join()
    watcher.close()

    assert result is True


def test_logwatcher_wait_for_marker_timeout(tmp_path):
    """wait_for_marker returns False when marker is not found within timeout."""
    log_file = tmp_path / "test.log"
    log_file.write_text("")

    watcher = LogWatcher(path=str(log_file))
    result = watcher.wait_for_marker("NonexistentMarker", timeout_s=0.2)
    watcher.close()

    assert result is False


def test_logwatcher_wait_for_regex_found(tmp_path):
    """wait_for_regex returns a match when pattern is found."""
    log_file = tmp_path / "test.log"
    log_file.write_text("")

    watcher = LogWatcher(path=str(log_file))

    def write_content():
        time.sleep(0.1)
        log_file.write_text(log_file.read_text() + "Connection IP set to 192.168.1.1, port: 7777\n")

    t = threading.Thread(target=write_content)
    t.start()
    result = watcher.wait_for_regex(CONNECTING_IP_RE, timeout_s=2.0)
    t.join()
    watcher.close()

    assert result is not None
    assert result.group(1) == "192.168.1.1"
    assert result.group(2) == "7777"


def test_logwatcher_wait_for_regex_timeout(tmp_path):
    """wait_for_regex returns None when pattern is not found within timeout."""
    log_file = tmp_path / "test.log"
    log_file.write_text("")

    watcher = LogWatcher(path=str(log_file))
    result = watcher.wait_for_regex(CONNECTING_IP_RE, timeout_s=0.2)
    watcher.close()

    assert result is None

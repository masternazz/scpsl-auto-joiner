"""Pure watch-mode decisions; network and GUI work stay outside this module."""


class SlotConfirmation:
    def __init__(self, required_samples=2):
        self.required_samples = max(1, int(required_samples))
        self.samples = 0

    def accepts(self, status):
        available = bool(status and status.get("available"))
        players = int(status.get("players") or 0) if status else 0
        maximum = int(status.get("max_players") or 0) if status else 0
        if not available or maximum <= players:
            self.samples = 0
            return False
        self.samples += 1
        return self.samples >= self.required_samples


class QueryFailureTracker:
    """Track consecutive resolver failures without treating them as full servers."""

    def __init__(self, fallback_after=3):
        self.fallback_after = max(1, int(fallback_after))
        self.consecutive = 0

    def observe(self, status):
        if status is None:
            self.consecutive += 1
        else:
            self.consecutive = 0
        return self.consecutive >= self.fallback_after


def eligible(status, minimum_players=0, maximum_fill_percent=100):
    if not status or not status.get("available"):
        return False
    maximum = int(status.get("max_players") or 0)
    players = int(status.get("players") or 0)
    if maximum <= 0:
        return False
    return players >= int(minimum_players) and players / maximum * 100 <= float(maximum_fill_percent)


def select_candidate(statuses, policy=None):
    policy = dict(policy or {})
    options = [s for s in statuses if eligible(s, policy.get("minimum_players", 0), policy.get("maximum_fill_percent", 100))]
    if not options:
        return None
    strategy = policy.get("strategy", "ordered_retry")
    if strategy == "lowest_latency":
        return min(options, key=lambda s: float(s.get("latency_ms") if s.get("latency_ms") is not None else 10**9))
    if strategy == "first_available":
        return options[0]
    return options[0]

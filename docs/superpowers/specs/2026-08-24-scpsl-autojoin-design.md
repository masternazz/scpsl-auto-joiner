# SCP:SL Auto-Joiner — Design

## Problem

Popular official SCP:SL servers are frequently full. Manually mashing "connect"
until a slot opens is tedious. Build a small Windows tool: type/pick a server
name, it resolves the server, repeatedly attempts to join, and notifies you
(toast) once it's in or once it gives up.

## Non-goals

- No OCR / screen-reading / template matching anywhere in the normal path.
- No memory reading, no packet manipulation, no anti-cheat interaction — this
  only automates clicks/keystrokes a human could do, against the game's own
  official server-list API and its own Direct Connect UI.
- Multi-monitor, non-Windows, and games other than SCP:SL are out of scope.

## Ground truth (verified live against the real client, 2026-08-24)

- Server identity: `https://api.scpslgame.com/lobbylist.php?format=json`
  (no API key needed for a basic read). Refreshes ~30s server-side, is **not**
  reliable for capacity ("24/25" can already be full) — used only to resolve a
  typed name to an IP:port, never to gate whether to attempt a join.
- `Player.log` (`%USERPROFILE%\AppData\LocalLow\Northwood\SCPSL\Player.log`)
  gives a clean, immediate outcome for every join attempt:

  | Outcome | Signature (grep, case-sensitive substrings) |
  |---|---|
  | **Success** | `Scene Manager: Loaded scene 'Facility'` |
  | **Rejected** (full, kicked, etc.) | `Connection has been delayed by` followed by `OnPeerDisconnected` |
  | **User/tool cancelled** | `Connection Failed` with no `OnPeerDisconnected` nearby |

  The client doesn't log *why* a rejection happened (full vs. banned vs.
  server down) — same signature for all of them. Not distinguished
  programmatically; see Error handling.
- The "DISCONNECTED / Server is full" overlay appears **on top of the server
  browser**, not a full menu reload — so a retry is just: dismiss the overlay,
  click Direct Connect's Connect button again. No re-navigation needed.
- Direct Connect (Servers → Internet → Direct Connect) is a small static
  dialog with a fixed IP:port field — not the scrolling server list. Coordinates
  for it are stable for a given window size/position, so they're captured once
  via a manual calibration step rather than located via OCR each time.

## Architecture

```
config.json ──┐
              ▼
  [resolver] ──(name, fuzzy match)──► lobbylist.php ──► ip, port
              │
              ▼
  [gui] ──(server name typed)──► [driver loop] ◄──tail──[log watcher]
              ▲                        │
              │                        ▼
        [toast notifier] ◄── success / gave-up / ambiguous
```

1. **GUI** (tkinter — stdlib): one text field (server name) + Join button +
   status line. Blocking network/automation work runs on a background thread
   so the window stays responsive.
2. **Resolver** (`resolver.py`): fetch `lobbylist.php`, `difflib.get_close_matches`
   the typed name against the returned server names (stdlib only), return
   `(name, ip, port)` of the best match.
3. **Input driver** (`winput.py`): adapted from FAFE's `capture.py` — just the
   pieces needed: DPI awareness (`SetProcessDpiAwarenessContext`, from Halo's
   `common.py` pattern), `find_game_window("SCP: Secret Laboratory")`,
   `focus_window`, SendInput-based `mouse_click`, SendInput-based key tap
   (Enter / Esc / typed characters for the IP:port field). Pure `ctypes`, no
   new dependency.
4. **Calibration** (`calibrate.py`, run once per machine/resolution): walks you
   through opening Direct Connect yourself, then you click the IP field and the
   Connect button while the tool is watching the cursor; it saves those two
   physical-pixel coordinates to `config.json`. Re-run any time the window
   moves/resizes.
5. **Log watcher** (`logwatch.py`): opens `Player.log`, seeks to end, then on
   each attempt reads new lines and classifies them against the three
   signatures above, with a timeout (default 20s) if none appear.
6. **Driver loop** (`joiner.py`): the orchestration —
   - type the resolved `ip:port` into the calibrated field, click Connect
     (or just click Connect again if the field already holds it from a
     previous attempt)
   - wait on the log watcher
   - **Success** → toast "Joined <name>", stop.
   - **Rejected** → press Esc (dismiss overlay), sleep `retry_interval`
     (default 6s, comfortably above the ~5s server cooldown), loop.
   - **Timeout / cancelled / anything unrecognized** → count as one "unclear"
     attempt; after `max_unclear` in a row (default 3), stop and notify with a
     toast telling you to check the game yourself — this is the "something
     else happened" catch-all from the original ask, without building a
     brittle classifier for it.
   - Hard cap: `max_attempts` (default 100) or `max_minutes` (default 30),
     whichever first — stop and notify "gave up" either way.
7. **Toast notifier** (`notify.py`): thin wrapper around `win11toast`.

## Config (`config.json`)

```json
{
  "retry_interval_s": 6,
  "attempt_timeout_s": 20,
  "max_unclear": 3,
  "max_attempts": 100,
  "max_minutes": 30,
  "direct_connect_ip_field": [0, 0],
  "direct_connect_connect_button": [0, 0]
}
```

The two coordinate fields are `[0, 0]` until `calibrate.py` has been run once.

## Error handling

- Game window not found (not running) → GUI shows an error, doesn't start the
  loop.
- Calibration coordinates still `[0, 0]` → GUI refuses to start, tells you to
  run calibration first.
- Server name matches nothing in the API response → GUI shows "no server
  found," doesn't start.
- Any unexpected exception in the driver loop → caught, logged to a local
  file, surfaced as a toast ("auto-joiner crashed, check log") rather than
  dying silently.

## Testing

Given this is log-parsing + a small state machine (the part with actual
branching logic), it gets one runnable check: `test_logwatch.py` — feeds the
three known signatures (plus an unrelated noise line) through the classifier
as fixture text and asserts the right outcome for each. Not testing the
GUI/click/network glue — that's exercised by hand against the real game during
build-out (there's no sandboxed SCP:SL server to integration-test against).

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
  for it, and for the menu buttons leading to it, are stable for a given window
  size/position, so they're captured once via a manual calibration step rather
  than located via OCR each time.

## Scope decisions

- **Fully automatic**: the tool launches SCP:SL itself if it isn't already
  running (`os.startfile("steam://rungameid/700330")` — stdlib, no dependency)
  and clicks through Play → Servers → Internet → Direct Connect on its own.
  Calibration therefore records a *sequence* of named click points, not just
  the two Direct Connect fields — see Calibration below.
- **Background clicking**: input is sent via `PostMessage` (not `SendInput`),
  so it doesn't steal window focus and you can keep using other windows while
  it retries — same technique your Forza project (`capture.py`) already uses
  for menu clicks there. Unverified against SCP:SL specifically until built;
  see the fallback in the Driver loop below.

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
   `common.py` pattern), `find_game_window("SCP: Secret Laboratory")`, and
   PostMessage-based `post_click` / `post_key` (background, focus-preserving —
   FAFE's proven pattern) for both mouse clicks and key taps (Enter / Esc /
   typed IP:port characters). Also keeps `focus_window` + SendInput
   `mouse_click`/key-tap as a fallback path (see Driver loop). Pure `ctypes`,
   no new dependency.
4. **Calibration** (`calibrate.py`, run once per machine/resolution): walks you
   through a named sequence of click points — Play, Servers tab, Internet tab,
   Direct Connect, the IP field, the Connect button — prompting you to click
   each once while the tool watches the cursor; saves them as physical-pixel
   coordinates to `config.json`, keyed by name. Re-run any time the window
   moves/resizes or the menu layout changes.
5. **Log watcher** (`logwatch.py`): opens `Player.log`, seeks to end, then on
   each attempt reads new lines and classifies them against the three outcome
   signatures above, plus `Connecting to` (used only to confirm a click
   actually registered — see fallback below), with a timeout (default 20s) if
   nothing relevant appears.
6. **Driver loop** (`joiner.py`): the orchestration —
   - if the game isn't running, launch it and wait (via the log watcher, for
     `Scene Manager: Loaded scene 'NewMainMenu'`) before doing anything else
   - click the calibrated menu sequence to Direct Connect (first run only;
     skipped once already there), type the resolved `ip:port`, click Connect
   - **click-registration fallback**: if `Connecting to` doesn't show up
     within ~5s of a click, the PostMessage click didn't register — retry
     that one click via `focus_window` + SendInput instead (briefly stealing
     focus), then continue. Two failures in a row on the same click → stop,
     notify "clicks aren't registering, re-run calibration."
   - wait on the log watcher for an outcome
   - **Success** → toast "Joined <name>", stop.
   - **Rejected** → press Esc (dismiss overlay), sleep `retry_interval`
     (default 6s, comfortably above the ~5s server cooldown), click Connect
     again (IP:port field already holds the value), loop.
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
  "click_points": {
    "play": [0, 0],
    "servers_tab": [0, 0],
    "internet_tab": [0, 0],
    "direct_connect": [0, 0],
    "ip_field": [0, 0],
    "connect_button": [0, 0]
  }
}
```

`click_points` stays all-zero until `calibrate.py` has been run once.

## Error handling

- Game not running and can't be launched → GUI shows an error, doesn't start
  the loop.
- Calibration not yet run (`click_points` all zero) → GUI refuses to start,
  tells you to run calibration first.
- A click never registers twice in a row (see fallback above) → stop, notify,
  don't spin forever clicking nothing.
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

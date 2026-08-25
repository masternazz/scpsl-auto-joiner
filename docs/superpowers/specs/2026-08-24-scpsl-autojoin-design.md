# SCP:SL Auto-Joiner — Design

> **Approved product direction (2026-08-25):** reliability-first auto-join,
> a saved-server browser, ordered server groups, and a four-page UI. Public
> server role detection and schedules are intentionally out of scope for this
> release. Role detection may be added later through an optional LabAPI
> companion for servers the user controls.

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
- Schedules and timed rotation are out of scope. A server group may run until
  success, the configured attempt/runtime limit, or the user stops it.
- Universal role detection on arbitrary public servers is out of scope. The
  client does not provide a stable role event in `Player.log`.
- Scraping an unofficial third-party browser is out of scope.

## Ground truth (verified live against the real client, 2026-08-24)

- Server identity: **not** resolved via `api.scpslgame.com/lobbylist.php` —
  that endpoint is Cloudflare-protected (403 to any non-browser client, even
  from a residential IP) and the underlying data needs an API key requested
  from Northwood directly (per `support.scpslgame.com/article/63`). Not worth
  chasing for a personal tool. Instead: a local `servers.json` (name → ip,
  port), populated by a "remember this server" flow — see Resolver below. Live
  player counts were already known to be unreliable for gating anyway (see
  next point), so nothing about the retry logic depended on a live API.
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

## Approved feature design

### Reliability-first connection strategy

The driver should prefer the documented Steam/SCP:SL direct-connect path for
both cold launches and warm retries when it works with the running client. The
current calibrated UI path remains a compatibility fallback, not the primary
retry mechanism. Every attempt is confirmed through the log watcher rather than
assuming that launching a URI or sending a click succeeded.

The retry state machine must explicitly represent: resolving, launching,
waiting for menu, connecting, waiting for outcome, rejected/full/unclear,
retrying, joined, stopped, and failed. A rejected attempt should be retried
after the configured delay (default two seconds), while a timeout or unknown
state should produce a useful diagnostic and obey the unclear-attempt limit.
The loop must handle a running game, a cold game launch, the game already being
on the Servers page, a connection overlay, a minimized/borderless window, 4K
and DPI scaling, log rollover, and duplicate start requests without silently
starting a second join loop.

### Saved-server browser

The app will provide a local browser backed by the existing AppData store. Each
saved server contains a stable id, display name, endpoint, optional notes and
group membership, plus last-known query data. Refreshing a server queries its
endpoint with A2S_INFO and records player count, maximum players, reported
name, latency, availability and last refresh time. The UI supports search,
sorting, refresh, rename, edit endpoint, delete, and import/export.

This is deliberately a **known-server browser** rather than a fake copy of the
Internet tab. It gives reliable names and player counts for servers the user
has saved without depending on restricted Northwood LobbyList credentials.

### Ordered server groups

Users can create named groups containing saved servers in an explicit order.
Starting a group runs the same retry state machine against the first server,
then advances to the next server when the current one reaches a terminal
rejection, timeout policy, or per-server attempt limit. Success stops the group.
After the last server, the default behavior is to loop back to the first until
the user stops it or the global attempt/runtime limit is reached. The UI shows
the active group, current server, position in the group, attempt number, and
reason for advancing.

### Public connection/round status

For arbitrary public servers, the app exposes only statuses that can be
verified client-side: launching, connecting, rejected/full-or-unknown,
loading, joined, disconnected and stopped. The UI should avoid claiming that a
server is definitely full when the log only proves a rejection. A future
optional LabAPI companion can provide authoritative role and round data for a
server the user controls, but that integration is not required by this design.

### Four-page UI and onboarding

The main window is organized into four persistent pages:

1. **Auto-Join** — choose one server or a group, configure run limits, start/
   stop, and view the live stage timeline and activity log.
2. **Servers** — searchable saved-server cards/table, player counts and status,
   refresh, edit, delete, group management, and remember/import actions.
3. **Calibration & Diagnostics** — setup health, game detection, log path,
   connection-method test, calibration only when the fallback driver needs it,
   and a guided test that explains exactly what will happen before any input is
   sent.
4. **Settings** — retry delay, per-attempt timeout, maximum attempts/runtime
   (`0` means unlimited), preferred connection method, background-input policy,
   notifications, accent color and reset/export controls.

First launch should guide the user through: locating SCP:SL, checking the log,
adding one server, running a safe connection test, and optionally calibrating
the fallback. The primary path must not require placing the mouse over a
button. If calibration is needed, the app should clearly say that the game
window will be focused temporarily and show a visible step-by-step overlay.

## Architecture

```
servers.json ──┐
               ▼
  [resolver] ──(name, fuzzy match)──► ip, port
               │
               ▼
  [gui] ──(server name typed)──► [driver loop] ◄──tail──[log watcher]
    │         ▲                        │
    │         │                        ▼
    └─"remember this server"──►  [toast notifier] ◄── success / gave-up / ambiguous
```

1. **GUI** (tkinter — stdlib): a text field (server name) + Join button +
   status line, plus a "Remember a server" button. Blocking network/automation
   work runs on a background thread so the window stays responsive.
2. **Resolver** (`resolver.py`): loads `servers.json` (a flat
   `{"name": {"ip": ..., "port": ...}}` map next to `config.json`),
   `difflib.get_close_matches` the typed name against its keys (stdlib only),
   returns `(name, ip, port)` of the best match, or `None` if nothing is close
   enough.

   **Populating it** — "Remember a server": you click Play on a server
   yourself in the normal in-game browser, like always; the tool (log watcher
   already running) sees the resulting `Connecting to <ip>!` line, and the GUI
   prompts "What should I call this server?" — the name you type is saved to
   `servers.json` alongside that IP/port. One ordinary click, ever, per server
   you want to auto-join later; no file editing, no API, no key.
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
- Server name matches nothing in `servers.json` (or it's empty) → GUI shows
  "no server found — use Remember a server first," doesn't start.
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

# Architecture

## Runtime layers

The application is divided into three layers:

1. `webui/` contains the HTML, CSS, and browser-side interaction code.
2. `web_api.py` exposes a small bridge for the desktop UI and coordinates
   persistence, monitoring, joining, notifications, and optional integrations.
3. Focused Python modules implement storage and operations:
   `server_store.py`, `history.py`, `watch_mode.py`, `joiner.py`, `logwatch.py`,
   `resolver.py`, `calibration_profiles.py`, `translation_packs.py`,
   `translation_updates.py`, `theme_manager.py`, and `companion_client.py`.

`app_web.py` starts the production pywebview shell. `gui.py` is retained as an
explicit legacy interface and is selected only with `--legacy-ui`.

## Data flow

Saved servers and groups are read from local AppData. A direct join observes
SCP:SL's normal log output and uses the configured input path for the short
GUI interaction. Watch Mode queries known endpoints first, confirms capacity
with consecutive samples, and only then asks the joiner to connect. History
records query observations locally.

The browser receives structured state and event data through the bridge. It
does not read files or execute imported content directly. Translation packs
are validated and copied into SCP:SL's translation directory; custom CSS is
sanitized and scoped before it is applied.

## Optional services

Tray controls, audio muting, Discord presence, destination sharing, and the
LabAPI companion are isolated from the core join path. If an optional service
is unavailable, the core application should continue with a clear status
message. The companion is a separately built server plugin and is never
installed automatically.

## Persistence and compatibility

User data belongs in `%LOCALAPPDATA%\\SCP-SL-Auto-Joiner`. Updates must preserve
that directory. Store migrations must accept older versions, quarantine
malformed data instead of overwriting it, and retain built-in SCP:SL files.

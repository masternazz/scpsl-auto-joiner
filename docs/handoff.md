# Maintainer handoff

This is the shortest complete path for taking over SCP:SL Auto-Joiner. It
describes the current production system rather than the sequence of experiments
that produced it.

## Current source of truth

- Production entry point: `app_web.py`
- Explicit legacy fallback: `py -3.13 app_web.py --legacy-ui`
- Desktop/backend API: `web_api.py`
- Browser UI: `webui/`
- Current public release line: `v0.3.34`
- User data root: `%LOCALAPPDATA%\SCP-SL-Auto-Joiner`
- Release identity: the Inno Setup `AppId` in `installer.iss`; never change it
  for a normal upgrade.

Use `git describe --tags --always` and `git status --short` before starting.
The latest tag is the released baseline; commits after it are unreleased work.
Do not infer release state from a screenshot or a stale build directory.

## First 15 minutes

```powershell
py -3.13 -m pip install -r requirements-dev.txt
py -3.13 -m playwright install chromium
py -3.13 app_web.py
```

Then run the automated layers in separate processes:

```powershell
py -3.13 -m pytest tests --ignore=tests/test_gui_flow.py -q
py -3.13 -m pytest tests/test_gui_flow.py -q
```

The first command includes the WebView bridge and Playwright UI tests. The
second isolates the legacy Qt tests, which use a different Qt process setup.
Tests must use temporary data directories and mocks; never point them at a
maintainer's real AppData or a public SCP:SL server.

## Runtime map

| Area | Source | Responsibility |
| --- | --- | --- |
| Desktop shell | `app_web.py` | Single-instance startup, WebView2 window, narrow bridge, file pickers, tray lifecycle, startup diagnostics |
| Browser UI | `webui/index.html`, `styles.css`, `app.js`, `ui-refresh.js`, `roadmap.js` | Rendering, navigation, settings, feature views, structured command calls and event handling |
| Application service | `web_api.py` | JSON-safe bridge commands, state coordination, background workers, persistence and optional services |
| Join flow | `joiner.py`, `logwatch.py`, `winput.py`, `calibrate.py` | SCP:SL detection, client-relative GUI interaction, connection-result observation, calibration |
| Saved destinations | `server_store.py`, `resolver.py`, `transport.py` | Servers, groups, profiles, A2S status and endpoint/name resolution |
| Watch/history | `watch_mode.py`, `monitoring.py`, `history.py` | Query-first slot detection, smart selection, bounded background monitoring, local observations |
| Appearance and packs | `theme_manager.py`, `translation_packs.py`, `translation_updates.py` | Sanitized themes, import/backup/activation, user-requested pack updates |
| Optional integrations | `tray.py`, `audio_control.py`, `discord_presence.py`, `destinations.py`, `instance_forward.py` | Tray controls, temporary mute, opt-in presence, local Discord Join dispatches, and previewed destination sharing |
| Owned-server companion | `companion-plugin/`, `companion_client.py`, `companion_server.py`, `secret_store.py` | Separately installed LabAPI status source with HTTPS and protected-token boundaries |
| Distribution | `build_exe.ps1`, `build_release.ps1`, `installer.iss`, `updater*.py` | PyInstaller onedir app, updater, portable ZIP, installer and checksums |

## Important contracts

### WebView bridge

Only deliberate command methods belong on `app_web.Bridge`. pywebview inspects
public attributes recursively. Exposing native windows, managers, paths, or
threads can make startup appear frozen before the JavaScript API is ready.
Every bridge value must be JSON serializable. New commands need backend tests
and a Playwright test covering success and failure states.

### Joining and input

Watch Mode is the preferred no-input path: it queries a saved endpoint and does
not interact with SCP:SL until capacity is confirmed. Immediate Auto-Join uses
short client-relative GUI interaction. Foreground compatibility input must
restore the previous foreground window and cursor. Background-only mode must
never call cursor, keyboard, or foreground-focus APIs.

The join state machine distinguishes confirmed full/rejected, disconnected,
timeout, joined, and unclear outcomes. Retries reuse an open Direct Connect
dialog when possible. Do not restore coordinate fallbacks that can reach the
Rent a Server link, and do not test joining against public servers.

### Persistence and upgrades

Servers, groups, config, history, calibration profiles, themes, translation
metadata/backups, reports, and protected companion tokens live under the local
AppData root. Tests use isolated roots. Migrations must preserve older valid
data, quarantine malformed stores, and never delete built-in SCP:SL
translations. Installer upgrades must keep the same `AppId` and must not remove
AppData.

### External and private systems

A2S data is advisory. Discord, destination sharing, background monitoring, and
the companion are opt-in. The companion is only for owned or authorized
servers and is never installed automatically.

The public repository does not grant access to the private SCP:SL acceptance
server. An authorized maintainer needs a separate private runbook containing:

- the SSH alias or management route;
- the Pelican panel URL and server identifier;
- the game/query ports and expected test-server name;
- where the test-only full/rejection configuration or plugin is stored;
- how to start, stop, and verify the server;
- companion endpoint/token setup, if that optional test is required.

Do not copy those values into commits, issues, screenshots, logs, destination
bundles, or bug reports. The public procedure is in
[`private-server-acceptance.md`](private-server-acceptance.md).

## Feature invariants

- The app remains local-first, account-free, and free of telemetry.
- It does not use injection, OCR, memory inspection, packet manipulation, or
  anti-cheat bypasses.
- Saved-server browsing is not a restricted global Northwood server browser.
- Public-server role detection is unsupported; personal role data requires the
  explicitly authorized companion.
- Imported CSS is styling data: reject imports, external URLs, scripts,
  expressions, and event-handler selectors before applying it.
- Translation updates are user-initiated, validated, backed up, and confirmed
  before replacement or activation.
- Discord server names and Join requests require per-server permission; player
  counts additionally require the global player-count permission. Raw endpoints
  are never visible Rich Presence text and Discord Join always opens an import
  preview before anything is saved or joined.
- Windows reduced-motion overrides the selected motion preset.

## Verification matrix

| Change | Minimum verification |
| --- | --- |
| Storage/domain module | Focused unit tests plus migration/corruption case |
| Bridge command/event | Backend API test and Playwright success/error flow |
| Web UI/layout | Keyboard path, no console errors, no horizontal overflow, 1280×720 and 1920×1080; include 4K for layout-wide changes |
| Join/input/calibration | Mocked regression tests, packaged startup, then authorized private-server acceptance when behavior changed |
| Installer/updater | Portable inspection, setup compile, checksum, upgrade over previous release, AppData survival |
| Companion | Desktop protocol tests plus a separately built plugin against matching LabAPI assemblies |

## Known risks

- WebView2 initialization differs across Windows installations. Startup must
  fail visibly with diagnostics rather than silently falling back or waiting
  indefinitely.
- SCP:SL Unity UI layout and input behavior can change after game updates.
  Recheck geometry immediately before interaction and warn on stale calibration.
- A2S responses can be absent or stale. Preserve the distinction between query
  failure and a confirmed full server.
- `webui/app.js`, `ui-refresh.js`, and `roadmap.js` are layered historical
  frontend files. Keep behavior changes focused and test the final composed
  page; do not assume one file owns an entire page.

## Before handing off again

Update this guide when an entry point, data location, bridge contract, build
command, release identity, or private-infrastructure boundary changes. Update
the feature matrix and latest release notes for shipped behavior. Never commit
raw captures, build output, dependency directories, local test state, or
private operational material.

# SCP:SL Auto-Joiner Reliability, Browser, and Server Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing SCP:SL Auto-Joiner reliable across normal Windows display setups, add a local searchable server browser and ordered server groups, and finish the four-page onboarding/UI flow.

**Architecture:** Keep the existing log-driven design and AppData storage. Add a small server-query layer for known endpoints, a group-aware orchestration layer around the existing join state machine, and use the installed-game direct-connect launch path as the preferred transport with the current background/foreground UI path as an explicit fallback.

**Tech Stack:** Python 3.11+, PySide6/Qt GUI already used by the project, stdlib `ctypes`/`socket`/`json`/`threading`, existing `pytest` suite, Windows 10 x64 support.

**Spec:** `docs/superpowers/specs/2026-08-24-scpsl-autojoin-design.md`

## Global Constraints

- No schedules, timed rotation, OCR, screen-reading, memory reading, packet manipulation, or anti-cheat interaction.
- Public servers expose only client-verifiable connection states; role detection is deferred to a future optional LabAPI companion.
- The full Internet browser is not implemented through Northwood’s restricted LobbyList API; the shipped browser queries saved endpoints only.
- Existing AppData data must migrate without losing saved servers, settings, calibration, update preferences, or accent customization.
- `max_attempts=0` and `max_minutes=0` each disable that individual limit; both zero means run until success or manual stop.
- Default retry delay is 2 seconds, and every retry must be cancellable through the existing stop event.
- The app must remain usable on Windows 10 and must not require the user’s physical mouse or keyboard during background retries.

## File Map

- Modify `resolver.py`: preserve saved-server compatibility, add structured server metadata, A2S_INFO player/status queries, search, and group persistence.
- Create `server_store.py`: focused AppData repository for servers and ordered groups, with migration and atomic writes.
- Modify `logwatch.py`: expose explicit connection, rejection, menu, loading, disconnect, and log-rollover observations without claiming unsupported role data.
- Create `transport.py`: direct-connect launch/retry strategies and testable transport selection; keep OS-specific process calls behind small functions.
- Modify `joiner.py`: use the transport strategy, explicit states, per-server attempt budgets, and ordered group rotation.
- Modify `config.py`: add connection strategy, browser refresh, group-loop, and onboarding settings with versioned migration.
- Modify `gui.py`: implement the Auto-Join, Servers, Calibration/Diagnostics, and Settings pages using the existing Qt style system.
- Modify `tests/test_resolver.py`, `tests/test_logwatch.py`, `tests/test_joiner_flow.py`, `tests/test_config.py`, and `tests/test_gui_flow.py`: add deterministic coverage for every new branch.
- Create `tests/test_server_store.py` and `tests/test_transport.py`.
- Modify `README.md` and add `docs/server-groups.md`: explain the saved-server browser, group behavior, direct-connect fallback, and AppData location.

---

### Task 1: Add a versioned local server/group store

**Files:**
- Create: `server_store.py`
- Modify: `resolver.py`
- Modify: `config.py`
- Test: `tests/test_server_store.py`, `tests/test_resolver.py`, `tests/test_config.py`

**Interfaces:**
- `server_store.load_store(path=None) -> dict`
- `server_store.save_store(store, path=None) -> None`
- `server_store.upsert_server(name, ip, port, path=None) -> dict`
- `server_store.delete_server(server_id, path=None) -> bool`
- `server_store.create_group(name, server_ids, path=None) -> dict`
- `server_store.update_group(group_id, server_ids, path=None) -> dict`
- `server_store.delete_group(group_id, path=None) -> bool`
- `server_store.search_servers(query, path=None) -> list[dict]`
- `resolver.query_server(ip, port, timeout=1.5) -> dict | None`
- Existing `resolver.resolve()` and `remember_server()` continue to work for old name-keyed files.

- [ ] **Step 1: Write failing migration and CRUD tests.** Assert old `{name: {ip, port}}` files load as stable server records, missing files create `{version: 1, servers: [], groups: []}`, IDs remain stable, group order is preserved, duplicate IDs are rejected, delete removes group membership, and writes are atomic.
- [ ] **Step 2: Run `python -m pytest tests/test_server_store.py tests/test_resolver.py tests/test_config.py -q` and verify the new tests fail.**
- [ ] **Step 3: Implement the store with a temporary file plus `os.replace`, deterministic UUIDs for migrated records, validation for IP/hostname and ports, and a one-time migration marker.** Keep the existing AppData directory from `app_paths.app_dir()`.
- [ ] **Step 4: Add A2S_INFO parsing for name, map, player count, max players, visibility/mod flags when present, and query latency.** Preserve the existing split-packet challenge response handling.
- [ ] **Step 5: Run the focused tests and then `python -m pytest tests -q`; expected result is all existing tests plus the new store/query tests passing.**
- [ ] **Step 6: Commit with `feat: add local saved-server and group storage`.**

### Task 2: Make log outcomes explicit and rollover-safe

**Files:**
- Modify: `logwatch.py`
- Test: `tests/test_logwatch.py`

**Interfaces:**
- `logwatch.classify_log_text(text) -> str | None`
- `logwatch.LogWatcher.wait_for_outcome(timeout_s, poll_interval=0.25, stop_event=None) -> str`
- `logwatch.LogWatcher.read_new() -> str`
- `logwatch.LogWatcher.reset_if_replaced() -> None`
- `logwatch.LogWatcher.last_endpoint -> tuple[str, int] | None`

- [ ] **Step 1: Add failing tests for connection-start, menu-ready, loading, rejected, disconnected, success, timeout, stop-event cancellation, and a replaced/truncated Player.log.** Assert rejection is reported as `rejected_or_unknown`, not definitively `full`.
- [ ] **Step 2: Run `python -m pytest tests/test_logwatch.py -q` and verify the new cases fail.**
- [ ] **Step 3: Implement marker ordering and file identity/size checks so a log rollover reopens from the new end without replaying stale data.** Keep existing signatures backward compatible where current joiner tests depend on them.
- [ ] **Step 4: Run `python -m pytest tests/test_logwatch.py tests/test_joiner_flow.py -q`; expected result is PASS.**
- [ ] **Step 5: Commit with `fix: harden log outcome tracking and rollover handling`.**

### Task 3: Add direct-connect transport selection

**Files:**
- Create: `transport.py`
- Modify: `joiner.py`
- Modify: `config.py`
- Test: `tests/test_transport.py`, `tests/test_joiner_flow.py`

**Interfaces:**
- `transport.ConnectionMethod = Literal["direct", "background", "foreground"]`
- `transport.launch_direct(executable, ip, port) -> subprocess.Popen`
- `transport.build_direct_args(executable, ip, port) -> list[str]`
- `transport.choose_method(config, game_running) -> ConnectionMethod`
- `transport.connect_with_fallback(ctx) -> None`
- `joiner.JoinState` values: `resolving`, `launching`, `menu_ready`, `connecting`, `waiting`, `rejected_or_unknown`, `retrying`, `joined`, `stopped`, `failed`.

- [ ] **Step 1: Add tests for exact `SCPSL.exe -steam +connect ip:port` arguments, automatic mode choosing direct launch only for a cold start, background-first warm retries, foreground fallback after missing `Connecting to`, and no second process when SCP:SL is already running.**
- [ ] **Step 2: Run `python -m pytest tests/test_transport.py tests/test_joiner_flow.py -q` and verify the new tests fail.**
- [ ] **Step 3: Move process launching and strategy choice out of `joiner.py` into `transport.py`; keep subprocess creation injectable for tests.**
- [ ] **Step 4: Refactor `joiner.connect_once()` to confirm the attempt with `Player.log` after every method, dismiss overlays once per rejection, and use a stop-aware delay helper.**
- [ ] **Step 5: Make both attempt and runtime limits independently unlimited at zero, and prevent concurrent runs with a single guarded run handle.**
- [ ] **Step 6: Run the focused tests and the full suite; expected result is PASS.**
- [ ] **Step 7: Commit with `feat: use reliable direct-connect transport with fallback`.**

### Task 4: Add ordered server-group orchestration

**Files:**
- Modify: `joiner.py`
- Modify: `server_store.py`
- Test: `tests/test_joiner_flow.py`, `tests/test_server_store.py`

**Interfaces:**
- `joiner.run(server_name, on_status=None, stop_event=None) -> str` remains compatible.
- `joiner.run_group(group_id, on_status=None, stop_event=None) -> str`
- `joiner.GroupProgress(group_id, server_id, index, total, attempt, state)` is an immutable progress record.
- `joiner.resolve_target(target_type, target_id) -> list[dict]`

- [ ] **Step 1: Add failing tests for one-server success, advancing after rejection, preserving explicit order, looping after the final server, stopping on success, stopping on global limits, and stopping immediately when the user requests stop.**
- [ ] **Step 2: Run `python -m pytest tests/test_joiner_flow.py -q` and verify the group tests fail.**
- [ ] **Step 3: Implement `run_group()` as a thin coordinator over the existing single-server attempt function; reset per-server unclear counters while retaining global attempt/runtime limits.**
- [ ] **Step 4: Emit progress messages containing group name, `server N of M`, endpoint-independent display name, attempt number, and the reason for advancing.**
- [ ] **Step 5: Run the focused tests and full suite; expected result is PASS.**
- [ ] **Step 6: Commit with `feat: add ordered server-group auto-join`.**

### Task 5: Build the Servers page and browser refresh flow

**Files:**
- Modify: `gui.py`
- Modify: `resolver.py`
- Modify: `server_store.py`
- Test: `tests/test_gui_flow.py`

**Interfaces:**
- `MainWindow.refresh_server_cards() -> None`
- `MainWindow.refresh_selected_server() -> None`
- `MainWindow.save_server_from_form() -> None`
- `MainWindow.delete_selected_server() -> None`
- `MainWindow.create_or_update_group() -> None`

- [ ] **Step 1: Add GUI-level tests using the existing Qt test helpers for search filtering, selecting a server, refreshing its query data through an injected resolver, rename/edit, delete confirmation, and group reorder.**
- [ ] **Step 2: Run `python -m pytest tests/test_gui_flow.py -q` and verify the new cases fail.**
- [ ] **Step 3: Replace the fragile editable combo-only picker with a searchable server list/card view that displays display name, endpoint, player count, availability, latency, and last refresh time.**
- [ ] **Step 4: Add group creation, rename, reorder, delete, and “start group” controls; keep a single-server quick-start path.**
- [ ] **Step 5: Run GUI tests and manually verify at 100%, 125%, 150%, and 200% Windows scaling that all controls remain reachable and the browser scrolls.**
- [ ] **Step 6: Commit with `feat: add saved-server browser and group management UI`.**

### Task 6: Finish onboarding, diagnostics, and settings

**Files:**
- Modify: `gui.py`
- Modify: `config.py`
- Modify: `README.md`
- Create: `docs/server-groups.md`
- Test: `tests/test_config.py`, `tests/test_gui_flow.py`

**Interfaces:**
- Config keys: `connection_method`, `group_loop`, `browser_refresh_timeout_s`, `onboarding_complete`, existing retry limits, `accent`, and calibration fields.
- `MainWindow.show_onboarding() -> None`
- `MainWindow.run_diagnostics() -> None`
- `MainWindow.set_connection_method(method) -> None`

- [ ] **Step 1: Add migration tests for the new config keys and assert existing v3 configs retain their settings.**
- [ ] **Step 2: Run the config tests and verify the new migration cases fail.**
- [ ] **Step 3: Add the four persistent pages: Auto-Join, Servers, Calibration/Diagnostics, and Settings.**
- [ ] **Step 4: Add first-run onboarding that checks the game executable, Player.log, AppData storage, one saved server, and direct-connect test before offering optional fallback calibration.**
- [ ] **Step 5: Make diagnostics explain exactly which connection method is active, whether the game is detected, whether the log is writable, and why calibration is or is not needed.**
- [ ] **Step 6: Add settings for direct/background/foreground preference, group looping, retry/timeout/attempt/runtime values, notifications, accent color, storage reset/export, and a clear `0 = unlimited` explanation.**
- [ ] **Step 7: Run the GUI/config tests and manually verify the app at 1920x1080 and 3840x2160 borderless; expected result is no clipped controls and no mandatory mouse capture on the primary path.**
- [ ] **Step 8: Commit with `feat: polish onboarding diagnostics and settings`.**

### Task 7: Documentation, packaging, and release verification

**Files:**
- Modify: `README.md`
- Create: `docs/server-groups.md`
- Modify: `build_release.ps1`, `installer.iss` only if the new modules/assets require packaging changes.
- Test: full test suite and packaging smoke checks.

- [ ] **Step 1: Document saved-server versus Internet-browser scope, A2S_INFO refresh behavior, group ordering/looping, public rejection wording, background-input limitations, and optional future LabAPI role integration.**
- [ ] **Step 2: Run `python -m pytest tests -q`; expected result is all tests passing.**
- [ ] **Step 3: Run the existing portable and installer build scripts and verify the executable starts from a clean extracted folder with its `_internal` files.**
- [ ] **Step 4: Run a manual matrix: game closed, game open on News, game open on Servers, full/rejected endpoint, successful endpoint, 4K borderless, Windows 10, stop during retry, infinite mode, and a two-server group.**
- [ ] **Step 5: Inspect the packaged AppData path, updater behavior, logs, and release contents for secrets or unexpected files.**
- [ ] **Step 6: Commit with `docs: document browser and server-group behavior`.**

## Self-review checklist

- Reliability: Tasks 2–4 cover direct launch, warm fallback, log confirmation, overlay dismissal, duplicate-run prevention, stop behavior, 4K/DPI, and zero-limit semantics.
- Browser: Tasks 1 and 5 cover names, player counts, search, sorting, refresh, latency, edit, rename, delete, and local AppData storage without restricted LobbyList access.
- Groups: Tasks 1 and 4–5 cover ordered membership, sequential attempts, looping, progress, and global limits.
- UI/onboarding: Task 6 covers all four pages, diagnostics, optional calibration, responsive scrolling, settings, and customization.
- Scope: role detection and schedules are explicitly excluded; no task silently adds them.
- Compatibility: existing resolver/config APIs and current tests remain supported through migration and focused regression tests.

Plan complete and saved to `docs/superpowers/plans/2026-08-25-reliability-browser-groups.md`.

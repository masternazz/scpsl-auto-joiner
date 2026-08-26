# SCP:SL Auto-Joiner Complete Product Plan

> **For agentic workers:** Execute this plan task-by-task with tests and review checkpoints. Do not claim a feature works until it has been tested in the packaged app as well as the source tree.

**Goal:** Deliver a polished Windows 10/11 SCP:SL Auto-Joiner that reliably retries saved servers in the background, supports ordered server groups, shows live server information, stores user data safely in AppData, packages correctly as portable and installer releases, and clearly explains every action.

**Baseline:** Continue from the current implementation and preserve the working pieces: Qt GUI, AppData storage, A2S_INFO saved-server queries, log watching, update helper, toast notifications, 0 = unlimited settings, and existing release scripts.

**Explicitly out of scope:** schedules/timed rotation, OCR as the normal path, memory reading, gameplay packet manipulation, anti-cheat interaction, and universal public-server role detection. A future LabAPI companion may provide authoritative roles on servers the user controls, but this release should not pretend the client log exposes roles.

## Required user experience

### Auto-join behavior

- A user can select one saved server or an ordered server group.
- On the first warm attempt, the app navigates from the current game menu to Servers and then Direct Connect.
- On retries, it skips Servers and goes directly to Direct Connect.
- A cold start uses the installed `SCPSL.exe -steam +connect IP:Port` path.
- A warm retry prefers the supported Steam `steam://connect/IP:Port` request when it works; it must not move the physical cursor or steal foreground focus.
- If a UI fallback is necessary, automatic mode uses targeted background messages only. Foreground `SendInput` is opt-in through Settings, never an automatic fallback.
- The app confirms connection attempts and outcomes from `Player.log` rather than assuming a click worked.
- Rejections are described as “rejected/full-or-unknown”; the app must not claim a server is definitely full when the log only proves rejection.
- Default retry delay is 2 seconds.
- `0` for maximum attempts or maximum runtime disables that individual limit. Both zero means run until success or manual stop.
- Stop must interrupt connection waits and retry delays promptly.
- Only one auto-join run may be active at once.

### Server browser and saved data

- The Servers page shows actual saved server names, never storage keys such as `version`, `servers`, or `groups`.
- Each server displays display name, endpoint, player count, maximum players, availability, latency, last refresh time, and optional notes.
- Search and sorting work locally without a network request.
- Refresh queries only saved endpoints using standard read-only A2S_INFO, including challenge-response where required.
- Users can add/remember, rename, edit, delete, refresh, import, and export saved servers.
- Groups support create, rename, delete, reorder, and explicit membership.
- Deleting a server removes it from all groups without corrupting the store.
- Data is stored under the user’s local AppData directory with atomic writes and migration from old name-keyed `servers.json` files.

### Server groups

- A group tries servers in the saved order.
- It advances after a terminal rejection, timeout policy, or per-server attempt policy.
- It stops immediately after success.
- After the last server, it loops to the first by default until stopped or globally limited.
- The live status shows group name, server position, server name, attempt number, current stage, and reason for advancing.

### UI and onboarding

The Qt app has four persistent pages:

1. **Auto-Join:** server/group selector, start/stop, limits, stage timeline, live log, and notification state.
2. **Servers:** scrollable searchable cards/list, refresh/status data, edit/delete, groups, import/export.
3. **Calibration & Diagnostics:** game detection, Player.log path/writability, connection-method test, fallback calibration, and clear explanations. Calibration must be optional for the primary direct-connect path and must never require clicking while the calibration dialog is covering the game.
4. **Settings:** connection method, background/foreground policy, retry/timeout/attempt/runtime values, group loop, notifications/toasts, accent color, storage reset/export, updater preferences, and `0 = unlimited` help text.

The primary layout must scroll and remain usable at 100%, 125%, 150%, and 200% Windows scaling, 1080p and 4K, borderless/fullscreen game layouts, and Windows 10.

### Packaging and updates

- Portable ZIP includes the executable and required `_internal` files.
- Setup installer installs the executable and its required runtime files.
- Inno Setup must never use `SCP:SL` as a Windows folder or shortcut filename because `:` is invalid there; keep the branded colon in display text only and use a safe filesystem name such as `SCP-SL Auto-Joiner`.
- Build and test both portable and setup outputs.
- The app checks releases, prompts the user, and if accepted performs the update itself without requiring the user to manually rerun an installer.
- Update downloads must verify SHA-256 and use the existing safe helper; no arbitrary shell commands or untrusted paths.
- Windows toast notifications must be optional and failure-safe.

## Execution order

### Phase 1 — Stabilize the connection state machine

1. Fix warm navigation so only attempt 1 opens Servers; attempts 2+ open Direct Connect directly, including group runs.
2. Correct the automatic Direct Connect point. Based on the supplied 2048×1152 SCP:SL screenshot, use approximately `(0.525, 0.193)` as the normalized Direct Connect center and add a regression test preventing the old Rent/Re-join coordinate.
3. Add a warm Steam URI transport behind an injectable function and test it without SCP:SL.
4. Make automatic mode direct/background-only. Remove automatic foreground clicks, cursor movement, focus activation, and foreground Escape. Keep foreground SendInput only when the user explicitly selects it.
5. Add fake full/rejection simulations verifying 2-second retry, correct log state, no unwanted focus/input calls, and direct-to-Direct-Connect retry navigation.
6. Run the existing log, transport, joiner, and group tests plus the complete suite.

### Phase 2 — Repair data/UI compatibility

1. Ensure the versioned store and legacy resolver projection cannot expose `version`, `servers`, or `groups` as selectable server names.
2. Add a regression test using the exact migrated store shape.
3. Verify group membership survives rename/edit and deletion cleanup.
4. Verify server refresh remains off the UI thread.

### Phase 3 — Finish onboarding, diagnostics, and settings

1. Complete the four-page navigation and scroll behavior.
2. Explain the preferred direct-connect path, background limitations, optional calibration, log evidence, rejection wording, and group looping.
3. Add first-run checks and a safe diagnostic mode that does not send input until the user confirms.
4. Preserve accent customization, help, toast settings, updater settings, AppData controls, and Windows 10 support.

### Phase 4 — Package and security verification

1. Build the portable distribution.
2. Compile the Inno Setup installer with a clean safe folder/shortcut name.
3. Install into a temporary per-user location and launch the installed app.
4. Test updater prompt, accepted update, checksum failure, cancellation, and no-update paths.
5. Verify the package contains only expected executable/runtime/assets and no secrets, source logs, test fixtures, or arbitrary scripts.
6. Run a security review covering subprocess arguments, URI handling, file paths, archive extraction, update URLs, SHA-256 verification, and AppData permissions.

## Required verification matrix

Automated:

- Full pytest suite.
- Compileall for changed Python modules.
- Fake server success, rejection/full-or-unknown, timeout, disconnect, loop, stop, and infinite-limit cases.
- Dropdown migration regression.
- Navigation-attempt regression.
- No-foreground-input regression.
- Installer script compilation.
- Portable and installed startup smoke tests.

Manual or visible desktop:

- Game closed, first cold join.
- Game open on News, first warm join.
- Game already on Servers, first warm join.
- Second retry from Direct Connect without reopening Servers.
- Full/rejected server and 2-second retry.
- Successful server.
- Single server and ordered group.
- Stop during connection and during retry delay.
- 0 attempts/runtime unlimited mode.
- 1080p and 4K borderless.
- Windows scaling 100%, 125%, 150%, and 200%.
- TikTok/another foreground application remains active during automatic retries; physical cursor and foreground window remain unchanged.
- Portable ZIP launch and installed setup launch.

## Acceptance criteria

The release is complete only when the dropdown shows real saved names, retries do not reopen Servers after the first attempt, automatic mode does not control the user’s mouse or foreground application, the installer no longer throws the invalid-folder-character error, the package launches from both distribution formats, and all automated plus required visible checks are recorded.

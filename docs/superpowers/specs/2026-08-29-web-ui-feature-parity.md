# Web UI feature-parity rebuild

## Goal

Make the Web UI a complete, first-class client for the existing Auto-Joiner
backend. No core capability may be hidden in post-render injection code or be
available only in the retired Qt interface.

## Information architecture

- **Auto-Join:** choose a saved server or a saved ordered group; show the
  selected target, start/stop controls, live status, retry state, and the
  current input mode.
- **Servers:** add, select, rename, refresh, and delete saved endpoints;
  start/stop remembering a normal SCP:SL connection; create, edit, reorder,
  start, and delete groups.
- **Diagnostics:** step-by-step calibration with capture, target preview,
  saved display metadata, reset/recalibrate, and input diagnostic output.
- **Settings:** retry limits, timeout, unclear-result limit, input method,
  navigation mode, notifications, group looping, audio muting, updates,
  appearance, AppData, export, and reset.
- **Text Packs:** folder/ZIP import, link import, GitHub search, activate,
  default, open, restore backup, and delete.

## Data flow

The existing `WebApi` remains the only persistence and automation authority.
The frontend holds a small display state copied from `get_app_state()` and
updates it only from structured bridge responses or events. Selection is
represented as `{type: "server" | "group", id}` so a group cannot be mistaken
for a server during `start_join`.

## UI rules

- Controls are rendered by their owning page, not appended by a second script
  after rendering.
- All editing uses the in-app modal form; no browser `prompt` or `confirm`.
- Destructive actions use the in-app confirmation modal.
- An unavailable option is shown with a reason instead of silently omitted.
- Server-group order has visible move-up/move-down controls and is the exact
  order sent to `save_group`.

## Acceptance contract

Automated UI tests must demonstrate each of the following through the WebView
bridge mock: add/rename/delete/refresh server; remember connection; select and
start server; create/edit/reorder/start/delete group; calibration capture/save
and diagnostics; every editable timing/input setting; mute toggle; AppData
export/reset; all text-pack lifecycle controls; theme/update controls.

The packaged application smoke test must reach the Auto-Join page, report the
bridge lifecycle markers, and remain responsive. Existing user data in AppData
must not be reset or migrated destructively.

## Legacy data contract

The Web UI and legacy Qt UI share `%LOCALAPPDATA%\\SCP-SL-Auto-Joiner`.
`servers.json` carries saved servers and ordered groups; `config.json` carries
calibration points, physical-DPI metadata, retry/input settings, audio mute,
and appearance. The existing flat server-list and portable-config migrations
remain active. The Web UI must show imported data immediately and display a
non-destructive migration notice when it upgraded a legacy store.

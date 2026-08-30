# Web UI Feature-Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore every user-facing Auto-Joiner capability that matters from the legacy Qt app in a cohesive Web UI, while preserving all existing AppData data.

**Architecture:** `WebApi` remains the deep module and single persistence/automation interface. `webui/app.js` becomes the only page renderer and interaction owner; `parity.js` is removed after its surviving workflows are incorporated directly. A typed display target `{type, id}` prevents groups and servers being confused when starting a join.

**Tech Stack:** Python 3.13, pywebview with Qt WebEngine, HTML/CSS/vanilla JavaScript, Pytest, Playwright, PyInstaller, Inno Setup.

**Spec:** `docs/superpowers/specs/2026-08-29-web-ui-feature-parity.md`

## Global Constraints

- Preserve `%LOCALAPPDATA%\\SCP-SL-Auto-Joiner\\servers.json` and `config.json` without destructive migration.
- Do not restore legacy Qt as the production UI; retain it only as `--legacy-ui` fallback.
- Use in-app modal forms and confirmation dialogs only; no browser prompts or native confirmation dialogs.
- Reuse the existing Python joiner, server store, calibration, updater, audio, and translation-pack modules.
- Do not connect to public SCP:SL servers during tests.

---

## Audited feature decision matrix

| Legacy capability | Current Web status | Decision |
|---|---|---|
| Saved server add/select/rename/delete/refresh | Partly rendered; some controls injected later | Keep; make first-class |
| Remember current SCP:SL connection | Hidden late-added control | Keep; make first-class |
| Ordered groups, looping, edit, start | Editor is hidden and does not reorder visibly | Keep; rebuild |
| Start/stop auto-join and activity log | Server-only selection, static state timeline | Keep; rebuild target model |
| Guided calibration and target preview | Raw point picker only | Keep; restore guided workflow |
| Retry, limits, input mode, mute, notifications | Split across injected settings | Keep; render in Settings |
| A2S player/latency refresh | Present in rows | Keep; add clear status/error state |
| Text pack import/link/search/activate/restore/delete | Partly injected | Keep; first-class |
| Theme, custom CSS, light presets | Present but layered | Keep; consolidate |
| Export/reset/AppData/updater/bug report | Partly injected | Keep; first-class |
| Qt-only onboarding dialogs | Missing | Replace with Web onboarding state |
| Qt widget styling/layout code | Host-specific | Drop from production UI |

### Task 1: Make legacy-data migration visible and regression-tested

**Files:**
- Modify: `web_api.py`, `webui/app.js`
- Modify: `tests/test_web_api.py`, `tests/test_webui_playwright.py`

**Interfaces:**
- Consumes: `server_store.load_store(path)`, `config.load_config(path)`
- Produces: `get_app_state()` includes `storage.migrated` and `storage.paths`

- [ ] **Step 1: Write failing migration contract tests**

```python
def test_app_state_exposes_legacy_saved_servers_and_calibration(tmp_path):
    # Seed old flat servers.json and portable-style config.json.
    api = WebApi(data_dir=tmp_path)
    state = api.get_app_state()
    assert state["servers"][0]["name"] == "Old server"
    assert state["calibration"]["points"]["servers_tab"] == [100, 200]
```

- [ ] **Step 2: Run the focused test and confirm it fails because storage metadata is absent**

Run: `py -3.13 -m pytest tests/test_web_api.py -k legacy -q`

- [ ] **Step 3: Add non-destructive storage metadata to `WebApi._state`**

Return canonical paths and a migration flag; do not copy, delete, or overwrite
files beyond the existing validated migrations.

- [ ] **Step 4: Render a compact migration/storage notice in Settings and test it in Playwright**

```python
def test_webui_shows_existing_appdata_servers(playwright_page):
    # Bridge state contains a migrated server and calibration.
    assert playwright_page.locator("text=Imported from existing local data").count() == 1
```

- [ ] **Step 5: Run focused Python and Playwright tests, then commit**

### Task 2: Rebuild the Auto-Join target and live-state page

**Files:**
- Modify: `webui/app.js`, `webui/styles.css`
- Modify: `tests/test_webui_playwright.py`

**Interfaces:**
- Consumes: `start_join(target, target_type)`, `stop_join()`, `get_join_status()`
- Produces: selected target `{type: "server" | "group", id}` and visible run state

- [ ] **Step 1: Write failing UI tests for selecting and starting a server and group**

```python
def test_webui_starts_selected_group_with_group_target(page):
    page.locator("#targetType").select_option("group")
    page.locator("#targetSelect").select_option("group-1")
    page.locator("#start").click()
    page.wait_for_function("window.startCalls[0].type === 'group'")
```

- [ ] **Step 2: Run the test and confirm the current server-only target view fails**

- [ ] **Step 3: Implement target selector, group/server summary, start/stop state, and event-driven timeline**

The timeline is derived from structured `status_changed`, `join_retrying`,
`join_succeeded`, and `join_failed` events; it must not be a static decoration.

- [ ] **Step 4: Run focused tests and commit**

### Task 3: Rebuild saved-server and ordered-group management

**Files:**
- Modify: `webui/app.js`, `webui/styles.css`
- Modify: `tests/test_webui_playwright.py`, `tests/test_web_api.py`

**Interfaces:**
- Consumes: `save_server`, `rename_server`, `delete_server`, `refresh_server_status`, `start_remember`, `remember_server`, `save_group`, `delete_group`
- Produces: explicit server modal, detected-server modal, group editor with ordered IDs

- [ ] **Step 1: Write failing tests for group reorder and saved order**

```python
def test_group_editor_saves_visible_member_order(page):
    page.locator("[data-group-move-down='server-a']").click()
    page.locator("#saveGroup").click()
    page.wait_for_function("window.groupCalls[0].ids.join(',') === 'server-b,server-a'")
```

- [ ] **Step 2: Confirm the test fails because the old editor only has checkboxes**

- [ ] **Step 3: Implement add/edit server forms, A2S refresh feedback, remember watcher, detected-server save dialog, and ordered group editor**

Each group member row exposes Move up/Move down and Remove. The exact displayed
array is passed to `save_group`; no sorting is allowed.

- [ ] **Step 4: Test add, rename, refresh, delete, remember, create, edit, order, start, and delete flows; commit**

### Task 4: Restore the calibration and diagnostics workflow

**Files:**
- Modify: `webui/app.js`, `webui/styles.css`
- Modify: `tests/test_webui_playwright.py`, `tests/test_web_api.py`

**Interfaces:**
- Consumes: `get_calibration_state`, `capture_calibration_point`, `save_calibration`, `run_input_diagnostic`
- Produces: four-step guided calibration with preview, saved metadata, and reset/recalibrate action

- [ ] **Step 1: Write a failing test for the four-step wizard**

```python
def test_calibration_wizard_captures_controls_in_required_order(page):
    for control in ["servers_tab", "direct_connect", "ip_field", "connect_button"]:
        page.locator("#captureCalibration").click()
        page.wait_for_function(f"window.captureCalls.includes('{control}')")
```

- [ ] **Step 2: Confirm it fails against the raw select control**

- [ ] **Step 3: Implement guided progress, target metadata preview, save, reset, and diagnostic output**

- [ ] **Step 4: Run focused tests and commit**

### Task 5: Consolidate Settings, Text Packs, Help, and onboarding

**Files:**
- Modify: `webui/app.js`, `webui/styles.css`, `webui/index.html`
- Modify: `tests/test_webui_playwright.py`

**Interfaces:**
- Consumes: `save_setting`, `get_update_status`, `install_update`, `export_local_data`, `reset_local_storage`, `open_data_folder`, translation-pack lifecycle methods
- Produces: a page-owned settings form and page-owned text-pack controls

- [ ] **Step 1: Write failing tests for every currently injected capability**

Test input mode, retry delay, attempt/runtime zero-unlimited behavior, mute,
notifications, looping, AppData/export/reset, update check, CSS/theme controls,
folder/ZIP/link/search pack import, activate/default/open/restore/delete.

- [ ] **Step 2: Confirm failures when `parity.js` is removed from the test page**

- [ ] **Step 3: Move each control into the owning page renderer in `app.js`; delete `parity.js` and its script tag**

- [ ] **Step 4: Restore a Web onboarding panel that reports game/log/storage/server readiness without launching or connecting**

- [ ] **Step 5: Run focused tests and commit**

### Task 6: Parity gate, packaged verification, and release

**Files:**
- Modify: `tests/test_webui_playwright.py`, `tests/test_app_web.py`
- Modify: `docs/release-notes-v0.3.24.md`, version files only after gates pass

**Interfaces:**
- Consumes: all previous page tests and `app_web.Bridge`
- Produces: one explicit feature-parity gate and a packaged v0.3.24 only if it passes

- [ ] **Step 1: Add a parity-gate test that enumerates every command used by the UI and asserts a visible workflow**

- [ ] **Step 2: Run `py -3.13 -m pytest tests --ignore=tests/test_gui_flow.py -q`**

- [ ] **Step 3: Launch the packaged EXE, verify `webview api ready` and `webview loaded`, and interact with the core server/group/calibration pages**

- [ ] **Step 4: Build the portable ZIP and setup installer, verify ZIP contents and installer compilation**

- [ ] **Step 5: Commit, push, and publish v0.3.24 without rewriting v0.3.23**

## Plan self-review

- Spec coverage: each retained legacy workflow maps to Tasks 1-5; packaging and regression protection map to Task 6.
- No destructive migration: enforced in Task 1 and global constraints.
- No placeholders: every task has file targets, interfaces, an expected failing test, and a verification gate.
- Type consistency: the target model is fixed as `{type, id}`; `WebApi.start_join(target, target_type)` remains unchanged.

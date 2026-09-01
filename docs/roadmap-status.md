# Feature roadmap and release matrix

This page maps the cumulative roadmap to implementation and release artifacts.
Each release keeps the same installer identity and local AppData store. The
publicly released baseline is v0.3.34; v0.3.35 is a local candidate, not a
published GitHub release.

| Release | Delivered capability | Main implementation | Verification |
| --- | --- | --- | --- |
| v0.3.25 | Watch Mode, tray controls, audio restore, server profiles | `watch_mode.py`, `tray.py`, `web_api.py` | automated suite and packaged startup |
| v0.3.26 | History, insights, background monitoring | `history.py`, `monitoring.py` | retention, corruption, cap, and API tests |
| v0.3.27 | Smart group policies and bounded queries | `server_store.py`, `watch_mode.py` | policy/filter tests and group coverage |
| v0.3.28 | Destination bundles, import preview, protocol forwarding | `destinations.py`, `instance_forward.py` | schema, privacy, malformed-link, and landing-page tests |
| v0.3.29 | Optional Discord Rich Presence | `discord_presence.py` | disabled-state, frame, permission, preview-only Join, and live Watch Mode tests |
| v0.3.30 | Named calibration profiles and health | `calibration_profiles.py` | migration, fingerprint, rename, duplicate, and corruption tests |
| v0.3.31 | User-initiated translation updates | `translation_updates.py`, `translation_packs.py` | repository/release metadata and staged replacement tests |
| v0.3.32 | Separate owned-server LabAPI companion | `companion-plugin/`, `companion_client.py`, `companion_server.py` | protocol, token, HTTPS, rate-limit, and fallback tests |
| v0.3.33 | WebView Auto-Join saved-server routing fix | `web_api.py` | bridge regression test and private-server acceptance test |
| v0.3.34 | Discord IPC startup, update, and shutdown reliability | `discord_presence.py` | stalled pipe, write, close, and live Discord IPC checks |
| v0.3.35 candidate | Decision explanations, recovery guidance, setup checks, target map, sanitized support bundles | `web_api.py`, `webui/product-expansion.js` | 227 non-Qt tests, 20 Qt tests, packaged startup, and an authorized private A2S check; GUI acceptance remains pending |
| v0.3.36 planned | Private tags, notes, collections, heatmap, accessibility preferences, tray status | `server_store.py`, `history.py`, `tray.py` | migration, history, and responsive UI tests |
| v0.3.37 planned | Opt-in actionable slot alerts, safe backup/restore, share-card privacy | `notify.py`, `instance_forward.py`, `web_api.py` | command validation, backup round trip, redaction, and rollback tests |
| v0.3.38 planned | Owner-only companion setup/dashboard integration | `companion-plugin/`, `companion_client.py`, `web_api.py` | target-matched companion source build succeeded; deployment/token/desktop fallback acceptance remains pending |

## Verification boundaries

- The automated suite covers local behavior and uses mocks for external services.
- A2S status is advisory; Watch Mode confirms a one-slot candidate with consecutive samples.
- The companion plugin must be built with compatible assemblies from the authorized server installation. It is not bundled into the desktop app and is never installed automatically.
- No public SCP:SL server is used for acceptance testing. A real success/failure run requires the owner's private server and game session.
- The app does not use restricted Northwood APIs, process injection, memory inspection, packet manipulation, or anti-cheat bypasses.

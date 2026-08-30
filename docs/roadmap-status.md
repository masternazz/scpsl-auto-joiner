# Feature roadmap and release matrix

This page maps the cumulative roadmap to the implementation and release artifacts. Each release keeps the same installer identity and local AppData store.

| Release | Delivered capability | Main implementation | Verification |
| --- | --- | --- | --- |
| v0.3.25 | Watch Mode, tray controls, audio restore, server profiles | `watch_mode.py`, `tray.py`, `web_api.py` | automated suite and packaged startup |
| v0.3.26 | History, insights, background monitoring | `history.py`, `monitoring.py` | retention, corruption, cap, and API tests |
| v0.3.27 | Smart group policies and bounded queries | `server_store.py`, `watch_mode.py` | policy/filter tests and group coverage |
| v0.3.28 | Destination bundles, import preview, protocol forwarding | `destinations.py`, `instance_forward.py` | schema, privacy, malformed-link, and landing-page tests |
| v0.3.29 | Optional Discord Rich Presence | `discord_presence.py` | disabled-state, frame, and permission tests |
| v0.3.30 | Named calibration profiles and health | `calibration_profiles.py` | migration, fingerprint, rename, duplicate, and corruption tests |
| v0.3.31 | User-initiated translation updates | `translation_updates.py`, `translation_packs.py` | repository/release metadata and staged replacement tests |
| v0.3.32 | Separate owned-server LabAPI companion | `companion-plugin/`, `companion_client.py`, `companion_server.py` | protocol, token, HTTPS, rate-limit, and fallback tests |
| v0.3.33 | WebView Auto-Join saved-server routing fix | `web_api.py` | bridge regression test and private-server acceptance test |

## Verification boundaries

- The automated suite covers local behavior and uses mocks for external services.
- A2S status is advisory; Watch Mode confirms a one-slot candidate with consecutive samples.
- The companion plugin must be built with the compatible LabAPI assembly from the authorized server installation. It is not bundled into the desktop app and is never installed automatically.
- No public SCP:SL server is used for acceptance testing. A real success/failure run requires the owner's private server and game session.
- The app does not use restricted Northwood APIs, process injection, memory inspection, packet manipulation, or anti-cheat bypasses.

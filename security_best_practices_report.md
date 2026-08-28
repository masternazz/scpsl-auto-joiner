# Security review

Scope: `app_web.py`, `web_api.py`, `theme_manager.py`, `translation_packs.py`, updater, and the WebView UI.

## Controls implemented

- The bridge returns structured JSON values and structured event envelopes; it does not evaluate user-provided JavaScript.
- Imported CSS is scoped to `.app-theme` and rejects imports, external URLs, scripts, expressions, and event-handler content.
- Translation ZIP extraction rejects path traversal and imported files are copied, not executed or loaded as Python code.
- Update downloads require HTTPS GitHub URLs and a SHA-256 digest before installation.
- Server persistence validates hostnames, ports, IDs, and group membership.

## Remaining operational risks

- GitHub search and update checks are external network requests and can be unavailable or rate limited.
- A user can intentionally install a malicious translation pack; the manager does not execute it, but SCP:SL itself may read installed translation files.
- The application controls SCP:SL input in foreground compatibility mode, so users should only run it with trusted saved destinations.

No high-severity code issue was identified in the reviewed WebView bridge path. This report is not a malware guarantee for third-party packs or releases.

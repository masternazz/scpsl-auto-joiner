# SCP:SL Auto-Joiner v0.3.10

## Reliability patch

- WebView bridge validation now returns clear in-app errors for invalid server, group, and timing inputs instead of allowing malformed requests to raise across the UI boundary.
- Invalid retry and timeout values are rejected before they can affect an auto-join run.
- Missing server and group records now produce actionable errors rather than an unhandled exception.
- Includes the v0.3.9 WebView2 interface, server browser, ordered groups, text packs, themes, diagnostics, updater, and game-audio mute controls.

## Known limitation

SCP:SL client behavior can vary by game version, display scaling, and window mode. If something fails, include the generated app report, SCP:SL version, resolution, DPI scale, and relevant activity log lines when reporting an issue.

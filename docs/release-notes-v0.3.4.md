# SCP:SL Auto-Joiner v0.3.4

## Background GUI compatibility patch

- Background GUI actions now send a non-focus activation hint before clicks,
  keys, and text.
- Automatic mode still never moves the cursor, sends global `SendInput`, or
  changes the foreground window.
- The error shown when SCP:SL ignores background input now accurately explains
  that Foreground mode is an explicit opt-in.

SCP:SL Unity client behavior can vary by version. If this release still cannot
accept background GUI messages, report the app log, SCP:SL version, Windows
version, resolution, DPI scale, and window mode. Do not test against public
servers while troubleshooting.

# SCP:SL Auto-Joiner v0.3.12

## UI dialog safety patch

- The legacy renderer can no longer open native browser `prompt()` or `confirm()` dialogs.
- The production WebView continues to use the clear in-app forms and confirmation modal.
- Prevents the raw `127.0.0.1 says` dialogs from returning if the parity script is delayed or unavailable.

## Known limitation

SCP:SL client behavior can vary by game version, display scaling, and window mode. If something fails, include the generated app report, SCP:SL version, resolution, DPI scale, and relevant activity log lines when reporting an issue.

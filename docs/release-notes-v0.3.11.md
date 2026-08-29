# SCP:SL Auto-Joiner v0.3.11

## Bridge stability patch

- Invalid theme and translation-pack actions now return structured errors instead of raising through the WebView bridge.
- Restore and delete operations now report whether the requested record actually existed.
- Keeps the full v0.3.10 feature set and packaging format.

## Known limitation

SCP:SL client behavior can vary by game version, display scaling, and window mode. If something fails, include the generated app report, SCP:SL version, resolution, DPI scale, and relevant activity log lines when reporting an issue.

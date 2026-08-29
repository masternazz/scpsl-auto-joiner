# SCP:SL Auto-Joiner v0.3.13

## Settings persistence patch

- Custom accent colors now persist across restarts and version updates.
- Configuration writes are atomic, reducing the chance of a damaged settings file if the app closes during a save.
- Preset and custom accent values are validated at the WebView bridge.
- Includes the native-dialog safety and bridge-stability fixes from v0.3.10–v0.3.12.

## Known limitation

SCP:SL client behavior can vary by game version, display scaling, and window mode. If something fails, include the generated app report, SCP:SL version, resolution, DPI scale, and relevant activity log lines when reporting an issue.

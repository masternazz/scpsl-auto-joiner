# SCP:SL Auto-Joiner v0.3.14

## Reliability fix

- WebView API instances now consistently use their configured AppData directory for saved servers, groups, settings, calibration, exports, and reset operations.
- Added regression coverage preventing isolated diagnostics, tests, or migration flows from reading or writing another storage location.

This release retains the v0.3.13 settings persistence and custom accent-color fixes.

## Known limitation

SCP:SL client behavior can vary by game version and display configuration. If something fails, include the app bug report and display configuration when reporting an issue. Test the auto-joiner with a private server you control before relying on it.

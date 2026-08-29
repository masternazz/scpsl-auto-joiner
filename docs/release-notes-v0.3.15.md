# SCP:SL Auto-Joiner v0.3.15

## Startup recovery hardening

- Malformed or interrupted `config.json` files are preserved as `.corrupt` backups and replaced with valid defaults.
- Malformed or interrupted `servers.json` files are preserved as `.corrupt` backups and replaced with an empty valid store.
- Added regression coverage for recovery without losing the original damaged data.

This release retains the v0.3.14 WebView storage-isolation fix and earlier UI, updater, server, group, calibration, and translation-pack features.

## Known limitation

SCP:SL client behavior can vary by game version and display configuration. If something fails, include the app bug report and display configuration when reporting an issue. Test the auto-joiner with a private server you control before relying on it.

# SCP:SL Auto-Joiner v0.3.17

## Translation-pack path hardening

- Managed translation-pack paths are now constrained to SCP:SL's `Translations` directory.
- Restore, delete, import, and open-folder operations reject traversal or absolute-path metadata.
- Added regression coverage proving an invalid pack record cannot reach or remove files outside the managed directory.

This release retains the v0.3.16 metadata recovery, v0.3.15 corrupt config/server recovery, and all earlier features.

## Known limitation

SCP:SL client behavior can vary by game version and display configuration. If something fails, include the app bug report and display configuration when reporting an issue. Test the auto-joiner with a private server you control before relying on it.

# SCP:SL Auto-Joiner v0.3.16

## Startup recovery hardening

- Corrupt theme metadata is preserved as a `.corrupt` backup and rebuilt with the default violet theme.
- Corrupt translation-pack metadata is preserved as a `.corrupt` backup and rebuilt as an empty pack store.
- The complete app-state bridge now remains usable when either optional metadata store is damaged.

This release retains the v0.3.15 recovery for config/server data and all earlier features.

## Known limitation

SCP:SL client behavior can vary by game version and display configuration. If something fails, include the app bug report and display configuration when reporting an issue. Test the auto-joiner with a private server you control before relying on it.

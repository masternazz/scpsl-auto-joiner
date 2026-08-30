# SCP:SL Auto-Joiner v0.3.25

## Watch Mode

- Watches saved servers using local A2S status before starting game input.
- Requires two consecutive samples when only one slot is available.
- Records local status samples in `history.sqlite3`.
- Adds a Watch for a slot action to the Auto-Join page.
- Offers normal Auto-Join as a fallback after repeated server-query failures
  instead of misclassifying an unavailable query as a full server.
- Adds editable per-server retry, timeout, monitoring, mute, and Discord-sharing profiles.
- Restores the Discord preference on startup and clears presence when a run stops.
- Validates group strategy, population filters, and loop overrides before saving.
- Adds a structured destination-bundle format for future sharing workflows.
- Adds privacy-safe share-link export with clipboard fallback and import preview.
- Adds isolated calibration-profile, Discord-presence, and owned-server companion primitives.

This release is a development build. A2S status can be stale and Unity/client behavior can vary by SCP:SL version. Report issues with the app log, SCP:SL version, display resolution, DPI scale, and window mode.

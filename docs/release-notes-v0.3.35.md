# SCP:SL Auto-Joiner v0.3.35 candidate

> This is an unreleased candidate. The current public GitHub release remains
> v0.3.34 until the remaining private-server desktop acceptance checks pass and
> the candidate is committed, pushed, and published.

## Explain, recover, and validate

- Added **Why didn't it join?** with evidence and safe next actions.
- Added recovery guidance for full servers, pending single-slot confirmation, query failures, timeouts, stale calibration, and GUI recovery.
- Added **Test my setup**, a voluntary saved-server A2S check, a client-relative target map, and a sanitized support-bundle ZIP.
- Added private tags, notes, collections, local history heatmaps, compact cards, high contrast, and larger text.
- Added opt-in slot alerts, optional native actions, safe backup/restore with rollback, and a private-data warning on share links.
- Added owner-only companion setup/status surfaces. The companion remains a separately built LabAPI plugin and is never installed into the game client.

## Notes

- Backups exclude Discord settings, companion tokens, credentials, and active audio state.
- Support bundles redact endpoints and token-like values.
- The companion source now compiles against matching authorized-server
  assemblies. It remains a separate owner-server artifact and has not yet been
  deployed or included in the desktop package.

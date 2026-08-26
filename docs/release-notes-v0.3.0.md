# SCP:SL Auto-Joiner v0.3.0

## Verified warm-join path

- Automatic mode now uses the tested SCP:SL GUI input path for warm joins because this client ignores background window messages.
- Each operation restores the user's previous cursor position and foreground window.
- Retry overlay dismissal uses the same selected input mode, preventing stale background/foreground mixing.
- Background-only remains available when absolute hands-off input is required, with a clear warning that SCP:SL may ignore it.

This build was verified against the local SCP:SL client controls at 3840×2160. The private server endpoint was unavailable during this run, so no public server was used for validation. Please report issues with the app log and exact display setup.

# SCP:SL Auto-Joiner v0.2.5

### Warm retry compatibility

- Tries focus-preserving background input first when SCP:SL is already open.
- If Unity ignores the background window messages, automatically retries the same attempt through the reliable GUI input path.
- Restores the user's cursor and previous foreground window after compatibility input.
- Prevents repeated missed connection markers from ending the run prematurely.

### Disclaimer

This is an early Windows build and has **not** been tested on every SCP:SL server, Windows configuration, monitor resolution, DPI setting, or game layout. Please [report issues on GitHub](https://github.com/masternazz/scpsl-auto-joiner/issues) with your Windows version, display setup, reproduction steps, and app log.

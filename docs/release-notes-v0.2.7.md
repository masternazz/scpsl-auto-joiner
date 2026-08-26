# SCP:SL Auto-Joiner v0.2.7

### Automatic input behavior

- Automatic mode tries focus-preserving background input first.
- If SCP:SL ignores the background message, it now uses the reliable GUI compatibility path for that attempt instead of retrying indefinitely without doing anything.
- The GUI path uses client-relative coordinates and restores the user's cursor and previous foreground window after each action.
- Background-only mode remains available when the app must never activate SCP:SL.

### Disclaimer

This is an early Windows build and has **not** been tested on every SCP:SL server, Windows configuration, monitor resolution, DPI setting, or game layout. Please [report issues on GitHub](https://github.com/masternazz/scpsl-auto-joiner/issues) with your Windows version, display setup, reproduction steps, and app log.

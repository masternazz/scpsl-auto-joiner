# SCP:SL Auto-Joiner v0.2.6

### Coordinate and input safety

- Uses the SCP:SL client rectangle for automatic click scaling, avoiding title-bar and window-frame offsets.
- New calibration captures client-relative points so moving or resizing the game window does not invalidate the calibration.
- Automatic mode is strictly background-only and never moves the physical cursor or injects keyboard input.
- Foreground input remains available only as an explicit Settings choice.
- Reports when SCP:SL ignores background input instead of silently taking control.

### Disclaimer

This is an early Windows build and has **not** been tested on every SCP:SL server, Windows configuration, monitor resolution, DPI setting, or game layout. Please [report issues on GitHub](https://github.com/masternazz/scpsl-auto-joiner/issues) with your Windows version, display setup, reproduction steps, and app log.

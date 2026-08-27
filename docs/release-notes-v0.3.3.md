# SCP:SL Auto-Joiner v0.3.3

## Background-safe Automatic mode

- Automatic mode now uses targeted background window messages like the
  background mode in Full Auto Forza Edition.
- Automatic mode never calls `SetCursorPos`, `SendInput`, or foreground-focus
  APIs, so the user's mouse, keyboard, and active app remain available while
  waiting.
- Foreground input remains available only when explicitly selected in Settings
  for SCP:SL client builds that ignore background messages.

This remains an early Windows build. Compatibility depends on the SCP:SL
Unity client accepting window messages. Report issues with the app log,
Windows version, display resolution, DPI scaling, and window mode.

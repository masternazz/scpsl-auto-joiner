# SCP:SL Auto-Joiner v0.3.1

Patch release for retry reliability.

## Fixed

- Automatic retries now dismiss SCP:SL's full/disconnected overlay using the
  same verified foreground input path as the connection attempt.
- Prevents the next retry from clicking through an uncleared overlay and
  landing on the wrong Servers-page control.
- Legacy configurations that omit `connection_method` continue to use the
  background-compatible retry path.

## Verification

- 117 automated tests pass.
- Includes a regression test for automatic retry overlay dismissal.

This remains an early Windows build. It has not been tested on every SCP:SL
server, monitor resolution, DPI setting, or Windows configuration. Please
report issues with your Windows version, display setup, reproduction steps,
and the app log.

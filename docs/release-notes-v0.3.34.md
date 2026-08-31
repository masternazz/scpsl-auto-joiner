# SCP:SL Auto-Joiner v0.3.34

## Fixed

- Discord Rich Presence no longer performs named-pipe connection, activity
  writes, or pipe shutdown on the desktop/UI thread. A slow, unavailable, or
  closing Discord client cannot freeze SCP:SL Auto-Joiner.
- The most recent presence state is retained while Discord connects in the
  background, then sent when the local Discord IPC connection is ready.

## Discord setup

- Rich Presence remains optional and disabled by default.
- The desktop app uses the registered public Discord application ID stored in
  local settings. No client secret, bot token, server endpoint, or account data
  is stored in the repository.

## Verification

- 213 non-Qt automated tests passed.
- 20 isolated legacy Qt tests passed.
- Discord IPC regression tests cover stalled connect, write, and close paths.
- A live local Discord IPC probe connected, sent a presence state, and cleared
  it without blocking.

## Known limitation

SCP:SL/Unity input and server-query behavior can change with game updates. If
an interaction fails, generate a bug report and include the app log, display
resolution, DPI scale, window mode, and SCP:SL version. Private-server live
acceptance remains required for any change to join or calibration behavior.

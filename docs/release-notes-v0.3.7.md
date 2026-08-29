# SCP:SL Auto-Joiner v0.3.7

## Startup reliability patch

This release fixes an intermittent startup race in the WebView2 interface. The frontend now waits for the pywebview bridge before requesting application state, so a slow WebView2 initialization no longer leaves the window open but unresponsive.

### Changes

- Added a visible startup/loading state.
- Waits for `pywebviewready` before initializing the application UI.
- Added a retryable startup error if the local bridge does not respond.
- Added regression coverage for delayed bridge initialization.
- Restored saved-server add/rename, ordered group editing, local data export/reset, translation link actions, and themed in-app confirmations.
- Restored “Remember current connection” using the SCP:SL `Player.log` endpoint watcher and server-name lookup.
- Added optional game-only audio muting during active runs; the previous mute state is restored afterward.
- Rebuilt the portable package and setup installer.

### Known limitations

Unity/client behavior can vary by SCP:SL version, display configuration, and Windows setup. Please report issues with the app log, Windows version, display resolution/DPI, and reproduction steps.

### Downloads

- `SCP-SL-Auto-Joiner-v0.3.7-win-x64-portable.zip`
- `SCP-SL-Auto-Joiner-v0.3.7-win-x64-setup.exe`

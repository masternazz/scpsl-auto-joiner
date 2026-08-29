# SCP:SL Auto-Joiner v0.3.22

## Startup and WebView2 reliability

- Prevents duplicate app instances from competing for the WebView2 session.
- Uses an isolated private WebView2 session; application data remains in AppData.
- Makes bridge startup resilient to both early and delayed WebView2 handshakes.
- Replaces the misleading startup timeout message with a direct bridge diagnostic.
- Removes the stale pre-bridge version placeholder from the shell.

This is a maintenance patch. SCP:SL client behavior can vary by game version; report issues with the app log, display resolution, DPI scale, and window mode.

# SCP:SL Auto-Joiner v0.3.23

## Startup reliability

- Fixes a WebView bridge startup hang caused by exposing native window objects
  to pywebview's JavaScript API scanner.
- Limits the browser bridge to explicit app commands only.
- Adds lifecycle markers to `startup-trace.log` for WebView page load and API
  readiness.
- Keeps duplicate launches focused on the existing app window.

If startup still fails, attach `startup-trace.log`, `startup-error.log`, and
your Windows/WebView2 version to an issue.

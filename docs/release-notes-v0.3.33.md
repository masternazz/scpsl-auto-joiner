# SCP:SL Auto-Joiner v0.3.33

## Fixed

- Fixed the WebView Auto-Join action passing an internal saved-server ID to the
  legacy join runner. The runner now receives the selected server name, so
  starting Auto-Join from the new interface reaches the saved destination.

## Verification

- Full automated suite passed when the Qt GUI tests were run in isolated
  processes.
- WebView browser tests passed.
- Private-server acceptance testing covered a live query, a controlled
  full-server rejection, and a successful connection. No public server was
  used.

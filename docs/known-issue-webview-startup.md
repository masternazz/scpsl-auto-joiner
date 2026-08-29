# Known issue: WebView2 startup and local bridge

Status: open investigation

Affected area: the WebView production shell (`app_web.py`, `webui/app.js`) in the v0.3.x line.

## User-visible symptom

The window opens and the static shell is visible, but after waiting it can show:

> Could not connect to the app
>
> The local WebView bridge did not respond.

In other cases the process remains alive while the page is stuck on “Checking game” or the user sees a Windows message saying that another SCP:SL Auto-Joiner instance is already running.

This is a startup/bridge problem. It is not a server-full response and it is not caused by SCP:SL navigation or calibration.

## Reproduction

1. Close every SCP:SL Auto-Joiner window.
2. Open the packaged `SCP-SL-Auto-Joiner.exe`.
3. Wait 15 seconds without starting auto-join.
4. Record whether the app reaches the Auto-Join page or remains on the boot/error state.
5. Launch the same executable a second time and record whether the original window is visible and responsive.

Do not use a public SCP:SL server while reproducing this issue. The game does not need to be running.

## Evidence to collect

Collect these files immediately after reproducing the problem:

```text
%LOCALAPPDATA%\SCP-SL-Auto-Joiner\startup-trace.log
%LOCALAPPDATA%\SCP-SL-Auto-Joiner\startup-error.log
%LOCALAPPDATA%\SCP-SL-Auto-Joiner\app.log
```

Also record:

- Windows version and build
- WebView2 Runtime version from Installed apps
- Whether the app came from the portable ZIP or installer
- The exact executable path
- Whether another app window was already open
- Display resolution, DPI scale, and number of monitors
- Whether the first window was responsive or frozen

PowerShell process check:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like 'SCP-SL-Auto-Joiner*' } |
  Select-Object ProcessId, ExecutablePath, CommandLine
```

## Current implementation

- `app_web.py` starts pywebview with the EdgeChromium backend.
- The Python `Bridge` object is passed as `js_api`.
- The frontend waits for `window.pywebview.api`, then calls `get_app_state()`.
- Backend data is stored in AppData; the WebView session is private so a stale or locked browser profile cannot prevent the backend from starting.
- A named Windows mutex prevents two copies from competing. A duplicate launch should focus the existing window and exit.

## Investigation checklist

1. Confirm the executable being tested is the newly built executable, not an old desktop shortcut or an older installed copy.
2. Confirm there is only one process and that its main window is responding.
3. Check whether `startup-trace.log` reaches `creating webview window`.
4. Check for `webview start failed` or a WebView2 initialization error.
5. Verify the WebView2 Runtime is installed and repair it if the packaged shell cannot initialize.
6. Test with the existing WebView profile left untouched; the application must not require deleting user data.
7. Test a clean Windows user profile if the issue cannot be reproduced on the development machine.
8. Use a debug build or temporary pywebview logging to confirm whether `finish.js` is injected and whether `pywebviewready` fires.
9. Do not “fix” this by adding a long timeout or silently switching to the legacy Qt UI. A failure must be visible and diagnosable.

## Acceptance criteria for closing

- A fresh portable launch reaches Auto-Join without a bridge error on Windows 10 and Windows 11.
- The setup-installed copy reaches the same state.
- Launching the shortcut twice focuses the existing window without showing a false crash.
- Settings and server data remain in AppData.
- The app reports a useful error if WebView2 is missing or initialization genuinely fails.
- Automated Playwright coverage includes both an already-ready bridge and a delayed bridge.
- A packaged EXE smoke test is repeated after every change to the startup shell.

## Important limitation

The development smoke test can prove that the packaged process starts and stays alive, but it cannot prove that every installed WebView2 runtime on every Windows machine injects the bridge correctly. Reports should include the files and environment details above.

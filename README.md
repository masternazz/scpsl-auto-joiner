![SCP:SL // Containment](assets/generated/github-banner-purple.png)

# SCP:SL // CONTAINMENT

A quiet Windows utility that keeps trying to join a saved SCP: Secret Laboratory server while you do something else.

## What it does

- Resolves and remembers friendly server names instead of forcing you to identify servers by IP.
- Starts SCP:SL directly when it is closed and navigates the client when it is already open.
- Detects accepted and rejected connections from SCP:SL's `Player.log`, including full-server rejection.
- Retries rejected attempts after a configurable delay; `0` means unlimited attempts or runtime.
- Uses resolution-scaled controls for different monitors, with optional per-computer calibration.
- Stores server data and settings in the normal Windows AppData location.
- Keeps interaction scoped to the SCP:SL window; a short compatibility fallback is used only when the game's Unity input layer ignores background messages.

The tool does not read or modify game memory, inject into the client, or require OCR for ordinary operation.

## Quick start

1. Download the packaged Windows build from the Releases page.
2. Launch `SCP-SL-Auto-Joiner.exe`.
3. Add or select a server, then start auto-join.
4. Open Calibration from the sidebar only if automatic navigation misses a control after a display or game-layout change.

The executable name remains stable for straightforward updates; the product UI and icon use the new Containment identity.

## Development

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 -m pytest -q
./build_exe.ps1
```

This is a personal desktop utility for Windows, Steam, and SCP:SL. Keep server credentials and local configuration out of source control.

# SCP:SL Auto-Joiner

A Windows utility that keeps trying to join a configured SCP: Secret Laboratory server until a slot opens.

![SCP:SL Auto-Joiner](assets/generated/github-banner-purple.png)

![Auto-join demo](assets/generated/auto-join-demo.gif)

[Open the full-size MP4 demo](assets/generated/auto-join-demo.mp4)

## Download

Download the latest Windows build from the [Releases page](https://github.com/masternazz/scpsl-auto-joiner/releases). Extract the ZIP, then run `SCP-SL-Auto-Joiner.exe`.

The current release is a portable Windows x64 build. It does not install SCP: Secret Laboratory, Steam, or any third-party game files.

## What it does

- Remembers server names and endpoints in a local server list
- Detects the endpoint from SCP:SL’s `Player.log` when you join normally
- Looks up a friendly server name through the server’s normal query response
- Launches SCP:SL when it is closed
- Opens Direct Connect and submits the saved endpoint
- Detects accepted, rejected, full, cancelled, and timed-out attempts from `Player.log`
- Retries rejected or full servers using the configured delay
- Runs with no attempt or runtime limit when either limit is set to `0`
- Supports automatic resolution-relative controls and optional per-computer calibration
- Lets you delete saved servers and stop a running join at any time

## Requirements

- Windows 10 or Windows 11
- SCP: Secret Laboratory installed through Steam
- Permission to join the selected server
- Borderless or windowed SCP:SL is recommended for the most reliable background interaction

The app does not use OCR, read game memory, inject into the game, manipulate packets, or bypass anti-cheat. It uses Steam launch parameters, targeted Windows input, and SCP:SL’s own log file.

## Quick start

1. Start the app.
2. Open **Remember a server**.
3. Join the target server normally in SCP:SL.
4. When the app detects the endpoint, give it a friendly name and save it.
5. Select the saved server and choose **Start auto-join**.

The app can launch SCP:SL automatically. On the first run, open **Calibration** if automatic controls do not match your game layout. Move the pointer over each named control and capture it without clicking the game. Calibration is stored per computer and should be repeated after changing display scaling, resolution, or the game window layout.

## Settings

The app exposes these controls:

- **Navigation mode**: Use automatic resolution-relative controls or saved calibration
- **Retry delay**: Seconds between rejected attempts; `2` is the default
- **Connection timeout**: Maximum time allowed for one attempt
- **Maximum attempts**: Stop after this many attempts; `0` means unlimited
- **Maximum runtime**: Stop after this many minutes; `0` means unlimited

When both limits are `0`, auto-join continues until the server accepts the connection or you press **Stop**.

## How results are detected

SCP:SL writes connection events to `Player.log`. The app watches new log entries and classifies each attempt as connecting, accepted, rejected, cancelled, full, or timed out. This keeps join-state detection independent of monitor resolution.

The app normally sends input to the SCP:SL window so you can use other applications while it waits. Some Unity builds do not accept background input. In that case, the compatibility path briefly activates the game, sends the input, then restores the previous foreground window and cursor position.

## Local data

The app stores its data in:

```text
%LOCALAPPDATA%\SCP-SL-Auto-Joiner
```

This folder contains saved servers, settings, calibration, and error logs. Use **Open data folder** in the app to inspect it.

SCP:SL’s log remains in its normal location:

```text
%USERPROFILE%\AppData\LocalLow\Northwood\SCPSL\Player.log
```

## Troubleshooting

### The app cannot detect a server

Confirm that SCP:SL has written a connection attempt to `Player.log`, then start **Remember a server** before joining. You can also add a server manually if you already know its host and port.

### A retry misses a control

Use **Calibration**, capture the requested controls in order, and switch Settings to **Use saved calibration**. Borderless or windowed mode gives the automation a stable game window.

### The game opens when it is already running

The app uses the supported direct-connect launch path for a cold start. Close duplicate SCP:SL processes, then start the join again with one game window open.

### The app stops too soon

Set **Maximum attempts** and **Maximum runtime** to `0` for unlimited operation. Set **Retry delay** to `2` for the normal full-server retry interval.

## Build and test

Install Python 3.13, then run:

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 -m pytest -q
./build_exe.ps1
```

The packaged executable is created at `dist\SCP-SL-Auto-Joiner\SCP-SL-Auto-Joiner.exe`.

The repository also includes the source renderer for the README walkthrough at `assets\brand\render_demo.py`.

## Project documentation

- [Design specification](docs/superpowers/specs/2026-08-24-scpsl-autojoin-design.md)
- [Implementation plan](docs/superpowers/plans/2026-08-24-scpsl-autojoin.md)
- [Server name resolution research](docs/research/server-name-resolution.md)
- [SCP:SL client and server browser research](docs/research/scpsl-client-server-browser.md)
- [Background automation research](docs/background-automation-research.md)

## License

No license has been selected yet. Until the repository gains a license, all rights remain with the copyright holder.

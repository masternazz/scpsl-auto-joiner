# Security review

Review date: 2026-08-25

This review covers the source tree, the `v0.2.0` Windows build, and the Python dependencies listed in `requirements.txt`. It is a focused application review, not a formal penetration test or a guarantee that third-party binaries are safe.

## Findings

No high or medium-risk findings were identified in the reviewed code.

The only network request is the update check. It sends a `GET` request over HTTPS to the project’s GitHub Releases API. It does not send saved servers, game logs, calibration, or other local data. The displayed update link is accepted only when it points to this project’s GitHub Releases path.

The game launch path starts the SCP:SL executable found in Steam libraries with fixed arguments. It does not execute a server-provided command, shell command, script, or downloaded file.

The Steam launch path opens the fixed `steam://rungameid/700330` URI. The input path uses Windows window messages and `SendInput` only to control SCP:SL. It does not read process memory, inject code, manipulate packets, or bypass anti-cheat.

The app writes configuration, saved servers, and logs under `%LOCALAPPDATA%\SCP-SL-Auto-Joiner`. It does not create startup entries, scheduled tasks, registry autoruns, services, or persistence outside that data folder.

The dependency audit reported no known vulnerabilities:

```text
py -3.13 -m pip_audit -r requirements.txt
No known vulnerabilities found
```

## Packaging notes

The portable ZIP and setup installer contain a PyInstaller `onedir` build. The `_internal` directory contains Python, Qt, and runtime libraries required by the executable. Removing it breaks the application.

The Windows packages are not code-signed. Windows SmartScreen or antivirus software may show a reputation warning for an unsigned PyInstaller application. Verify the SHA-256 checksum published with each release before running a downloaded package.

## Safe-use boundaries

- Download packages only from this repository’s Releases page
- Keep Steam and SCP:SL updated from their official sources
- Do not replace files inside the package with untrusted DLLs or scripts
- Treat the saved server and log folders as local user data

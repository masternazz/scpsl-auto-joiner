# Development guide

## Set up

Use Python 3.13 on Windows 10 version 1809 or newer. Install dependencies with:

```powershell
py -3.13 -m pip install -r requirements.txt
```

Start the development shell with:

```powershell
py -3.13 app_web.py
```

Use `py -3.13 app_web.py --legacy-ui` only when checking the compatibility
interface. WebView2 is required by the production shell.

## Test the right layer

- Storage and domain behavior: the focused `tests/test_*.py` modules.
- Legacy Qt behavior: `tests/test_gui_flow.py`.
- Web bridge and browser behavior: `tests/test_app_web.py`,
  `tests/test_web_api.py`, and `tests/test_webui_playwright.py`.
- Packaging: `build_release.ps1`, followed by startup and archive inspection.

Use temporary stores in tests. Never point a test at a user's real AppData
files or at a public game server.

## Build artifacts

`build_release.ps1 -Version x.y.z` creates the onedir application, portable ZIP,
installer when Inno Setup is installed, and checksum file. The release version
is passed through `SCP_SL_APP_VERSION`; do not hard-code a new version in only
one component.

Before publishing, verify the executable starts, the archive contains the
WebView resources and updater, the installer preserves AppData, and the
release notes describe known limitations.

# Release process

Releases are immutable and sequential. Never rewrite an older GitHub release or
move an existing version tag.

## 1. Prepare

1. Start from a clean, reviewed commit on the intended release branch.
2. Choose the next version and create `docs/release-notes-vX.Y.Z.md`.
3. Confirm the version passed to the build is the same version shown by the app,
   updater, installer filename, release notes, and Git tag.
4. Preserve the installer `AppId` and AppData path.

## 2. Verify source

```powershell
py -3.13 -m pip install -r requirements-dev.txt
py -3.13 -m playwright install chromium
py -3.13 -m pytest tests --ignore=tests/test_gui_flow.py -q
py -3.13 -m pytest tests/test_gui_flow.py -q
```

For join, input, calibration, Watch Mode, or companion behavior, complete the
authorized checks in [private-server-acceptance.md](private-server-acceptance.md).
Do not substitute a public server.

## 3. Build

```powershell
.\build_release.ps1 -Version X.Y.Z
```

This builds the PyInstaller onedir application and updater, creates the portable
ZIP, compiles the Inno Setup installer when ISCC is available, and writes SHA-256
checksums when both packages exist.

Expected release assets:

```text
SCP-SL-Auto-Joiner-vX.Y.Z-win-x64-portable.zip
SCP-SL-Auto-Joiner-vX.Y.Z-win-x64-setup.exe
SCP-SL-Auto-Joiner-vX.Y.Z-SHA256SUMS.txt
```

## 4. Smoke-test packages

- Start the packaged EXE repeatedly and confirm it reaches Auto-Join without a
  false bridge error or frozen window.
- Launch a duplicate and confirm the existing instance is focused.
- Inspect the portable ZIP for `webui`, assets, the updater, and `_internal`.
- Install over the previous version and confirm servers, groups, settings,
  history, calibration profiles, themes, translation packs, and tokens remain.
- Confirm uninstalling the application does not delete user AppData.
- Verify the displayed version and updater comparison from the packaged app.

## 5. Publish

```powershell
git tag vX.Y.Z
git push origin HEAD
git push origin vX.Y.Z
gh release create vX.Y.Z `
  .\dist\SCP-SL-Auto-Joiner-vX.Y.Z-win-x64-portable.zip `
  .\dist\SCP-SL-Auto-Joiner-vX.Y.Z-win-x64-setup.exe `
  .\dist\SCP-SL-Auto-Joiner-vX.Y.Z-SHA256SUMS.txt `
  --title "SCP:SL Auto-Joiner vX.Y.Z" `
  --notes-file .\docs\release-notes-vX.Y.Z.md
```

Publishing is an explicit maintainer action. Confirm the repository, branch,
tag, notes, and artifact hashes before running it. After publishing, download
the public assets once and verify their checksums and installer startup.

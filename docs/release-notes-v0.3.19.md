# SCP:SL Auto-Joiner v0.3.19

## Bug fixes

- Added native WebView2 file and folder pickers for translation packs.
- Removed the Electron-only reliance on `File.path`; selected ZIPs and folders now reach the backend as real local paths.
- Drag-and-drop remains supported when the host supplies a local path, with a clear picker instruction when WebView2 hides it.

## Verification

- 154 automated tests pass.
- JavaScript/Python compilation checks pass.
- Dependency vulnerability audit passes.
- Packaged EXE and isolated installer smoke tests pass.

SCP:SL client behavior can vary by game version and display configuration. When reporting an issue, include the app bug report, activity log, SCP:SL version, window mode, resolution, and DPI scale.

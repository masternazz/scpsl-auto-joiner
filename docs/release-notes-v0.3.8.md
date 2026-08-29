# SCP:SL Auto-Joiner v0.3.8

## WebView theme startup patch

This patch fixes a fast-startup race where a saved light theme or custom CSS could be missed if the local bridge became ready before the parity layer finished loading.

### Changes

- Apply persisted preset and sanitized custom CSS on every startup path.
- Add regression coverage for immediate WebView bridge initialization.
- Rebuilt the portable package and setup installer.

### Known limitations

Unity/client behavior can vary by SCP:SL version, display configuration, and Windows setup. Please report issues with the app log, Windows version, display resolution/DPI, and reproduction steps.

### Downloads

- `SCP-SL-Auto-Joiner-v0.3.8-win-x64-portable.zip`
- `SCP-SL-Auto-Joiner-v0.3.8-win-x64-setup.exe`

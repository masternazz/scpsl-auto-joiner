# SCP:SL Auto-Joiner v0.3.18

## Bug fixes

- Fixed the Servers page refresh action so it never selects the row or navigates away from the server browser.
- Updated refresh results in place to avoid an asynchronous page-render race while the user is interacting with the browser.
- Light, warm-light, and slate-light appearance presets now persist through the application bridge and remain selected after reopening the app.

## Verification

- 153 automated tests pass.
- Packaged EXE and installer smoke tests are run before publishing.

SCP:SL client behavior can vary by game version and display configuration. When reporting an issue, include the app bug report, activity log, SCP:SL version, window mode, resolution, and DPI scale.

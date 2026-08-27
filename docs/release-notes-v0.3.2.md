# SCP:SL Auto-Joiner v0.3.2

## Retry and 4K reliability patch

- Automatic mode follows the recorded SCP:SL menu flow on a cold start.
- Failed/full attempts reuse the existing Direct Connect dialog first.
- Direct Connect is reopened only when SCP:SL did not accept the reused-dialog action.
- Retry recovery never clicks the Servers page or Rent a Server control.
- Status updates identify the UI phase, confirmed disconnect/full response,
  retry delay, and unclear results.
- Automatic targets continue to use the live SCP:SL client rectangle; guided
  calibration now records client size, window position, and available DPI data.
- Setup diagnostics can preview the exact native-pixel targets without sending input.

## Verification

- 119 automated tests pass locally.
- Portable and setup packaging are produced as separate v0.3.2 assets.

This release is an early Windows build and has not been tested against every
SCP:SL version, display configuration, or third-party server. Test against a
private server first and report issues with the app log, Windows version,
resolution, DPI scaling, window mode, and reproduction steps.

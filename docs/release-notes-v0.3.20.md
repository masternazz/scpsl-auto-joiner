# SCP:SL Auto-Joiner v0.3.20

## Fixed

- Made the sidebar collapse chevron, mobile navigation icon, and bridge boot ellipsis encoding-safe so they render correctly in WebView2 and packaged builds.
- Added a regression test covering the navigation and boot symbols.

## Verification

- Full automated suite: 155 passed.
- JavaScript syntax checks, Python compilation, and diff validation passed.

Live SCP:SL acceptance testing still requires the private test server to be reachable. Report issues with the generated app report, SCP:SL version, display resolution, DPI scale, and window mode.

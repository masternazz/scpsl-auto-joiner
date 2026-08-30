# Implementation notes

The production shell is Python with a pywebview/WebView2 interface. The
legacy Qt interface remains available with `--legacy-ui` for compatibility.

Core operations are local: saved-server storage, log observation, A2S queries
for known endpoints, retry groups, calibration profiles, translation-pack
management, optional watch mode, and optional integrations. Portable and
installer builds include the application resources and updater required by
their distribution modes.

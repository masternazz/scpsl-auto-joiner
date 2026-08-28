# SCP:SL Auto-Joiner threat model

## Scope and assets

The desktop process, WebView2 frontend, Python bridge, AppData stores, SCP:SL log, imported translation packs, and GitHub update/search requests are in scope. Assets are saved server data, calibration/settings, local logs, installed pack files, and release integrity.

## Trust boundaries

1. WebView JavaScript to Python bridge: untrusted UI strings cross into local filesystem, process, and network operations.
2. GitHub to local pack/update storage: remote content crosses into downloaded archives and installers.
3. SCP:SL process/log to the joiner: game output determines retry state.

## Main abuse paths and mitigations

- Crafted CSS could execute or load remote content. Mitigation: CSS sanitizer rejects imports, URLs, scripts, expressions, and event handlers and scopes selectors.
- Crafted ZIP could overwrite files outside staging. Mitigation: absolute-path/common-path validation before extraction.
- Tampered update could replace the application. Mitigation: HTTPS GitHub allowlist and SHA-256 digest verification.
- Malicious bridge input could alter arbitrary settings or endpoints. Mitigation: editable-setting allowlist and server-store validation.
- Log poisoning could create misleading status. Mitigation: logs are informational and do not grant privileges; unclear results stop after configured limits.

## Assumptions

The application is a local desktop utility with no listening network service and no authentication requirement. Users may intentionally install third-party translation packs. Public server connections are user-selected and are not used for automated acceptance testing.

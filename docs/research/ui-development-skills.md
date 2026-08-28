# UI Development Skills Research

## Recommended skills for this project

- `frontend-design` is already available locally and is the best fit for creating a distinctive production UI rather than a generic dashboard.
- `web-design-guidelines` is already available locally and should be used to review keyboard access, responsive behavior, labels, focus states, and interaction clarity.
- `playwright` and `playwright-interactive` are already available locally for deterministic browser/Electron-style interaction testing.
- `ui-test` from Browserbase was installed for adversarial UI review. It specifically covers rapid clicks, empty states, keyboard-only use, accessibility checks, responsive viewport sweeps, console errors, broken assets, and screenshot-backed failures. [UI Test skill](https://github.com/browserbase/skills/tree/main/skills/ui-test)
- `security-best-practices` and `security-threat-model` were installed for reviewing the Python/WebView bridge, downloaded pack handling, updater, and external links.

## External research

- Microsoft's navigation guidance favors simple, clear navigation and recommends left navigation for apps with roughly 5–10 top-level destinations. [Windows navigation basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics)
- Microsoft's settings guidance recommends a dedicated scrollable settings page with a constrained readable width around 1000–1100 px. [Windows app settings guidance](https://learn.microsoft.com/en-us/windows/apps/design/app-settings/guidelines-for-app-settings)
- FAFE's public source demonstrates the exact Python/WebView architecture we want: pywebview hosting HTML/CSS/JS, a Python API bridge, WebView2 on Windows, PyInstaller packaging, and Inno Setup distribution. [FAFE UI bridge](https://raw.githubusercontent.com/Leoncrispybacon/Full-Auto-Forza-Edition/main/app_web.py), [FAFE build script](https://raw.githubusercontent.com/Leoncrispybacon/Full-Auto-Forza-Edition/main/build_app_paid.bat)
- Reddit users report that pywebview is attractive when the backend is already Python and the UI needs modern web layout, but they also flag packaging/runtime distribution as the main production concern. This is secondary community evidence, not a substitute for official documentation. [r/learnpython discussion](https://www.reddit.com/r/learnpython/comments/1s2dtax/desktop_apps_with_pywebview_library/), [r/Python discussion](https://www.reddit.com/r/Python/comments/1ltktz1/a_pythonpowered_desktop_app_framework_using_html/)

## How we will apply the skills

1. Use `frontend-design` while rebuilding the visual system and page layouts.
2. Use `web-design-guidelines` after the first implementation pass for accessibility and responsive review.
3. Use `ui-test` and Playwright for startup, navigation, form, dropdown, drag/drop, and viewport regression checks.
4. Use the security skills before packaging to review the pywebview bridge, updater, GitHub requests, translation imports, and installer behavior.

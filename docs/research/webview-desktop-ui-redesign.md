# SCP:SL Auto-Joiner WebView UI Research

## Recommendation

Rebuild the production shell with Python + pywebview + HTML/CSS/JavaScript. Keep the existing Python automation and persistence modules behind a small JavaScript API bridge, and make the WebView page the primary user interface.

## Findings

- FAFE uses `pywebview` to host an Edge WebView2 window, exposing a Python API to HTML/JavaScript through `pywebview.api`. Its automation backend remains Python. [FAFE UI bridge](https://raw.githubusercontent.com/Leoncrispybacon/Full-Auto-Forza-Edition/main/app_web.py)
- FAFE's public build script packages the application with PyInstaller, includes the WebUI as data, and builds its Windows installer with Inno Setup. [FAFE build script](https://raw.githubusercontent.com/Leoncrispybacon/Full-Auto-Forza-Edition/main/build_app_paid.bat), [FAFE installer script](https://raw.githubusercontent.com/Leoncrispybacon/Full-Auto-Forza-Edition/main/build_installer.iss)
- Microsoft's Windows guidance recommends left navigation for roughly 5–10 equally important top-level destinations, adaptive compact navigation for smaller windows, and a flat structure when pages are peers. [Windows navigation basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics), [NavigationView](https://learn.microsoft.com/en-us/windows/apps/design/controls/navigationview)
- Microsoft's settings guidance recommends a dedicated, scrollable settings page with a constrained readable width around 1000–1100 px and grouped settings cards. [Windows app settings guidelines](https://learn.microsoft.com/en-us/windows/apps/design/app-settings/guidelines-for-app-settings)
- Microsoft's desktop app structure guidance combines a custom title bar, left navigation, transparent content surfaces, and persistent InfoBar-style status messaging. [Modern Windows app structure](https://learn.microsoft.com/en-us/windows/apps/develop/ui/windows-app-sdk-app-structure)

## Proposed visual system

Use an industrial-containment identity rather than game-dashboard decoration:

- Near-black charcoal base, warm off-white text, restrained containment violet, and small amber/green status accents.
- One type family for normal UI and a monospace face only for endpoints, timestamps, and diagnostics.
- Solid surfaces, thin borders, compact labels, and deliberate spacing; no gradients, neon glow, fake 3D panels, or oversized decorative graphics.
- All colors exposed as CSS custom properties so custom themes can override the palette without changing markup.
- Responsive layout targets: 1280×720, 1920×1080, 2560×1440, and 3840×2160; content stays readable with a max-width rather than stretching indefinitely.

## Proposed information architecture

1. **Auto-Join** — selected destination, start/stop action, state timeline, live log, and current retry details.
2. **Servers** — searchable saved-server list, player/status refresh, server details, groups in a separate subview, and clear rename/delete actions.
3. **Text Packs** — import/drop area, GitHub discovery, installed packs, activation, default-language switch, backup restore, and deletion.
4. **Diagnostics** — calibration wizard, calculated target preview, display/DPI metadata, input-mode test, and bug-report export.
5. **Settings** — grouped behavior, timing, input mode, audio, updates, appearance, and data-location controls.
6. **Help** — short task-oriented instructions and troubleshooting links, available from the sidebar footer or help button.

The server page uses a list/detail pattern so browsing and editing do not compete for the same crowded form. Groups are a secondary view inside Servers, not another top-level item.

## Interaction rules

- Every page has one clear primary action.
- Destructive actions use an explicit confirmation and never share a small icon-only control with safe actions.
- Run status is visible in the shell header and the Auto-Join page; errors use an inline status bar rather than unexpected modal windows.
- Settings are scrollable and retain their section headings while the user works.
- Keyboard focus, visible focus rings, semantic labels, reduced-motion support, and sufficient contrast are required.
- A compact navigation mode is used on narrow windows; no page should require horizontal scrolling.

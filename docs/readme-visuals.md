# README visual maintenance

The README visuals are generated from `assets/brand/render_readme_assets.py`.
It creates an S-mark product hero, sanitized WebView screenshots, and the
README walkthrough without reading personal app data or contacting a server.

```powershell
py -3.13 assets/brand/render_readme_assets.py
```

The script exports both MP4 and GIF versions. Product screenshots are captured
at 4K from a high-DPI WebView. The focused live-app MP4 preserves 2880x1620
detail; its 1080px GIF uses a two-pass palette for sharp inline GitHub viewing.
The `demo-webview` capture drives the shipped WebView with fictional structured
events and records its real CSS transitions.

`demo-webview.gif` is the README demo because it shows the real shipped UI
driven with fictional data. It focuses on Auto-Join so Watch Mode state changes
remain readable at GitHub's inline size. Review the generated images and video
before publishing a change.
Do not commit raw frame directories, recordings, private endpoints, tokens,
local paths, or personal Discord details.

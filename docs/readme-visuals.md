# README visual maintenance

The README visuals are generated from `assets/brand/render_readme_assets.py`.
It creates a containment-style hero, sanitized WebView screenshots, and two
demo candidates without reading personal app data or contacting a server.

```powershell
py -3.13 assets/brand/render_readme_assets.py
```

The script exports both MP4 and GIF versions. Product screenshots are captured
at 4K from a high-DPI WebView. The focused live-app MP4 preserves 2880x1620
detail; its 1080px GIF uses a two-pass palette for sharp inline GitHub viewing. The
`demo-rendered` candidate is fully deterministic. The `demo-webview` candidate
captures the shipped WebView UI using fictional data.

`demo-webview.gif` is the current README demo because it shows the real shipped
UI driven with fictional data. Its labeled status rail makes each staged Watch
Mode state visible even at GitHub's inline size. `demo-rendered.gif` remains a
deterministic storyboard alternative. Review generated images and both GIFs
before changing that choice.
Do not commit raw frame directories, recordings, private endpoints, tokens,
local paths, or personal Discord details.

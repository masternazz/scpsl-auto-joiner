# README visual maintenance

The README visuals are generated from `assets/brand/render_readme_assets.py`.
It creates a containment-style hero, sanitized WebView screenshots, and two
demo candidates without reading personal app data or contacting a server.

```powershell
py -3.13 assets/brand/render_readme_assets.py
```

The script exports both MP4 and GIF versions. The MP4 files preserve 1080p
detail; the 720px GIFs use a two-pass palette and are intended for inline
GitHub viewing. The `demo-rendered` candidate is fully deterministic. The
`demo-webview` candidate captures the shipped WebView UI using fictional data.

`demo-rendered.gif` is the current README hero because it is deterministic and
easy to review. `demo-webview.gif` remains a staged, real-UI alternative for a
future swap. Review generated images and both GIFs before changing that choice.
Do not commit raw frame directories, recordings, private endpoints, tokens,
local paths, or personal Discord details.

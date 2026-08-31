# README visual maintenance

The README visuals are generated from `assets/brand/render_readme_assets.py`.
It creates an S-mark product hero, sanitized WebView screenshots, a Remotion
Watch Mode explainer, and a rendered storyboard without reading personal app
data or contacting a server.

```powershell
cd assets/brand/remotion
npm install
cd ../../..
py -3.13 assets/brand/render_readme_assets.py
```

The script exports both MP4 and GIF versions. Product screenshots are captured
at 4K from a high-DPI WebView. The 960px inline walkthrough is authored in
`assets/brand/remotion/` and rendered with Remotion, then converted with a
two-pass palette for GitHub. The `demo-rendered` candidate is a deterministic
storyboard; the Remotion walkthrough is a product explainer using fictional data.

`demo-watch-mode.gif` is the current README demo. It animates Watch Mode states
with the same terminology and state progression used in the application. Review
generated images and both GIFs before changing that choice.
Do not commit raw frame directories, recordings, private endpoints, tokens,
local paths, or personal Discord details.

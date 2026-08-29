import inspect

from app_web import Bridge


def test_webview_bridge_exposes_only_command_methods():
    """pywebview must never recursively inspect its own Window or managers."""
    bridge = Bridge()
    public = {name for name in dir(bridge) if not name.startswith("_")}

    assert "window" not in public
    assert "pack_manager" not in public
    assert "theme_manager" not in public
    assert "data_dir" not in public
    assert "get_app_state" in public
    assert "pick_translation_source" in public
    assert all(inspect.ismethod(getattr(bridge, name)) for name in public)


def test_native_window_stays_private_after_attachment():
    """Attaching the native window must not change pywebview's API graph."""
    bridge = Bridge()
    bridge._attach_window(object())
    public = {name for name in dir(bridge) if not name.startswith("_")}

    assert "window" not in public
    assert "attach_window" not in public
    assert all(inspect.ismethod(getattr(bridge, name)) for name in public)

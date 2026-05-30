import src.code_ai.desktop.app as app_mod


def test_app_module_imports_without_webview():
    # app.py must be importable with no [desktop] extra installed:
    # webview is imported only inside run_gui().
    assert hasattr(app_mod, "run_gui")


def test_ui_assets_are_packaged():
    # Anchor on the module's own location (robust regardless of how the
    # editable install registers subpackages); reads the real source tree.
    from pathlib import Path
    ui = Path(app_mod.__file__).parent / "ui"
    assert (ui / "index.html").is_file()
    assert (ui / "style.css").is_file()
    assert (ui / "app.js").is_file()


def test_ui_url_is_file_uri():
    # pywebview must receive a file:// URI (not a bare OS path) so the window
    # actually renders and relative asset links resolve.
    url = app_mod._ui_url()
    assert url.startswith("file://")
    assert url.endswith("/index.html")

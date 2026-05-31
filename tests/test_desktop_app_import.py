import inspect
import sys
import types

import src.code_ai.desktop.app as app_mod
from src.code_ai.desktop.platforms.base import AppStatus


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


def _pywebview_exposed_functions(obj):
    exposed_objects = []
    functions = set()

    def walk(current, base_name=""):
        obj_id = id(current)
        if obj_id in exposed_objects:
            return
        exposed_objects.append(obj_id)

        for name in dir(current):
            if name.startswith("_"):
                continue
            full_name = f"{base_name}.{name}" if base_name else name
            attr = getattr(current, name)
            if not getattr(attr, "_serializable", True):
                continue
            if inspect.ismethod(attr) or inspect.isfunction(attr):
                functions.add(full_name)
            elif inspect.isclass(attr) or (
                isinstance(attr, object) and not callable(attr) and hasattr(attr, "__module__")
            ):
                walk(attr, full_name)

    walk(obj)
    return functions


class _FakeBackend:
    def detect(self, app, override):
        return AppStatus(app.id, found=True, direct=False, launch_target="t", match_root="r")

    def launch(self, status, env):
        pass

    def is_running(self, status):
        return False

    def stop(self, status):
        pass

    def proxy_enabled(self):
        return True

    def pick_path_filter(self):
        return ("*",)


class _FakeWindow:
    class _Event:
        def __init__(self):
            self.items = []

        def __iadd__(self, item):
            self.items.append(item)
            return self

    def __init__(self):
        self.events = types.SimpleNamespace(shown=self._Event())

    def create_file_dialog(self, *args, **kwargs):
        return []


def test_run_gui_exposes_only_js_api_methods_to_pywebview(monkeypatch, tmp_path):
    captured = {}
    fake_window = _FakeWindow()

    def create_window(_title, url, js_api, width, height):
        captured["js_api"] = js_api
        return fake_window

    fake_webview = types.SimpleNamespace(
        OPEN_DIALOG=20,
        create_window=create_window,
        start=lambda **kwargs: captured.update(start_kwargs=kwargs),
    )

    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setattr(app_mod, "get_backend", lambda: _FakeBackend())
    monkeypatch.setattr(
        "src.code_ai.desktop.config.DESKTOP_CONFIG_FILE",
        tmp_path / "desktop.yaml",
    )
    monkeypatch.setattr(app_mod.sys, "platform", "win32")

    app_mod.run_gui()

    assert captured["start_kwargs"]["icon"].endswith("icon.ico")
    assert len(fake_window.events.shown.items) == 1
    assert _pywebview_exposed_functions(captured["js_api"]) == {
        "get_app_settings",
        "get_settings",
        "launch_app",
        "list_apps",
        "pick_app_path",
        "save_app_settings",
        "save_settings",
        "stop_app",
    }

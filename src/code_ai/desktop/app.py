import pathlib
import sys

from .apps import APP_REGISTRY
from .bridge import LauncherBridge
from .platforms import get_backend


def _ui_asset_path(name: str) -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent / "ui" / name


def _ui_url() -> str:
    # Resolve the UI relative to this module's own file so it works whether the
    # package is installed as a wheel, run from source, or used in a worktree
    # (importlib.resources("code_ai.desktop") can resolve to a different installed
    # copy that lacks the desktop subpackage — the source-vs-installed gotcha).
    # Return a file:// URI so pywebview renders the page and resolves the relative
    # style.css / app.js links across platforms.
    index = _ui_asset_path("index.html")
    return index.as_uri()


def _window_icon_path() -> str:
    if sys.platform == "win32":
        return str(_ui_asset_path("icon.ico"))
    return str(_ui_asset_path("icon.png"))


def run_gui():
    """Open the launcher window. Imports webview lazily (optional [desktop] extra)."""
    backend = get_backend()
    if backend is None:
        print("code-ai desktop is supported on Windows and macOS only.")
        return

    import webview  # lazy: only needed to actually show the GUI

    bridge = LauncherBridge(backend, APP_REGISTRY)
    window = webview.create_window(
        "AI Launcher", url=_ui_url(), js_api=bridge, width=760, height=560,
    )
    bridge._attach_window(window, webview.OPEN_DIALOG)
    webview.start(icon=_window_icon_path())

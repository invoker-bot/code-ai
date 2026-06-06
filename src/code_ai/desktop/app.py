import json
import pathlib
import sys
import threading
import time

from .apps import APP_REGISTRY
from .bridge import LauncherBridge
from .platforms import get_backend

POLL_SECONDS = 1.5


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

    def poll():
        while True:
            time.sleep(POLL_SECONDS)
            try:
                payload = json.dumps(bridge._statuses())
                window.evaluate_js(f"window.updateStatus({payload})")
            except Exception:
                break

    threading.Thread(target=poll, daemon=True).start()
    webview.start(icon=_window_icon_path())

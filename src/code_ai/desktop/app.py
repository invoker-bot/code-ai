import importlib.resources
import json
import threading
import time

from .apps import APP_REGISTRY
from .bridge import LauncherBridge
from .platforms import get_backend

POLL_SECONDS = 1.5


def _ui_url() -> str:
    index = importlib.resources.files("code_ai.desktop").joinpath("ui", "index.html")
    return str(index)


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
    bridge.window = window
    bridge.open_dialog = webview.OPEN_DIALOG

    def poll():
        while True:
            time.sleep(POLL_SECONDS)
            try:
                payload = json.dumps(bridge.statuses())
                window.evaluate_js(f"window.updateStatus({payload})")
            except Exception:
                break

    threading.Thread(target=poll, daemon=True).start()
    webview.start()

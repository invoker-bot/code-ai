import os

from .apps import APP_REGISTRY, get_app
from . import config as cfg
from .env import merge_env


class LauncherBridge:
    """pywebview js_api. Pure-Python and headless-testable.

    The GUI layer (app.py) attaches the pywebview window after creation.
    Runtime handles stay private so pywebview does not recursively expose
    native window objects as JS API members.
    """

    def __init__(self, backend, apps=APP_REGISTRY):
        self._backend = backend
        self._apps = apps
        self._window = None
        self._open_dialog = 20  # pywebview OPEN_DIALOG; overridden in app.py
        self._status = {}
        self._refresh_detection()

    def _attach_window(self, window, open_dialog):
        self._window = window
        self._open_dialog = open_dialog

    # ---- detection cache ----
    def _refresh_detection(self):
        data = cfg.load_desktop_config()
        for app in self._apps:
            override = cfg.get_app_path(data, app.id)
            self._status[app.id] = self._backend.detect(app, override)

    def _running(self, app_id):
        st = self._status.get(app_id)
        if not st or not st.found:
            return False
        try:
            return bool(self._backend.is_running(st))
        except Exception:
            return False

    def _statuses(self):
        return {a.id: self._running(a.id) for a in self._apps}

    # ---- queries exposed to JS ----
    def list_apps(self):
        return [
            {"id": a.id, "display": a.display,
             "found": self._status[a.id].found, "running": self._running(a.id)}
            for a in self._apps
        ]

    # ---- actions ----
    def launch_app(self, app_id):
        data = cfg.load_desktop_config()
        if cfg.get_check_system_proxy(data) and not self._backend.proxy_enabled():
            return {"ok": False, "error": "系统代理未开启，已取消启动"}
        app = get_app(app_id)
        override = cfg.get_app_path(data, app_id)
        status = self._backend.detect(app, override)
        self._status[app_id] = status
        if not status.found:
            return {"ok": False, "error": "未检测到应用，请先配置路径"}
        env = merge_env(os.environ,
                        cfg.get_common_env(data),
                        cfg.get_app_env(data, app_id))
        try:
            self._backend.launch(status, env)
        except Exception as exc:
            return {"ok": False, "error": f"启动失败: {exc}"}
        return {"ok": True}

    def stop_app(self, app_id):
        status = self._status.get(app_id)
        if not status or not status.found:
            return {"ok": False, "error": "未检测到应用"}
        try:
            self._backend.stop(status)
        except Exception as exc:
            return {"ok": False, "error": f"中止失败: {exc}"}
        return {"ok": True}

    # ---- settings ----
    def get_settings(self):
        data = cfg.load_desktop_config()
        return {"check_system_proxy": cfg.get_check_system_proxy(data),
                "env_vars": cfg.get_common_env(data)}

    def save_settings(self, payload):
        data = cfg.load_desktop_config()
        cfg.set_check_system_proxy(data, bool(payload.get("check_system_proxy", True)))
        cfg.set_common_env(data, dict(payload.get("env_vars", {})))
        cfg.save_desktop_config(data)
        return {"ok": True}

    def get_app_settings(self, app_id):
        data = cfg.load_desktop_config()
        return {"env_vars": cfg.get_app_env(data, app_id),
                "path": cfg.get_app_path(data, app_id) or ""}

    def save_app_settings(self, app_id, payload):
        data = cfg.load_desktop_config()
        cfg.set_app_env(data, app_id, dict(payload.get("env_vars", {})))
        cfg.save_desktop_config(data)
        return {"ok": True}

    def pick_app_path(self, app_id):
        if self._window is None:
            return {"ok": False}
        file_types = self._backend.pick_path_filter()
        result = self._window.create_file_dialog(self._open_dialog, file_types=file_types)
        if not result:
            return {"ok": False}
        path = result[0]
        data = cfg.load_desktop_config()
        cfg.set_app_path(data, app_id, path)
        cfg.save_desktop_config(data)
        self._refresh_detection()
        return {"ok": True, "path": path}

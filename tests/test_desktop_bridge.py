from contextlib import contextmanager
from pathlib import Path
import shutil
from unittest.mock import patch
from uuid import uuid4

from src.code_ai.desktop.apps import APP_REGISTRY
from src.code_ai.desktop.bridge import LauncherBridge
from src.code_ai.desktop.platforms.base import AppStatus


@contextmanager
def temp_desktop_config():
    root = Path.cwd() / ".test-artifacts" / str(uuid4())
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root / "desktop.yaml"
    finally:
        shutil.rmtree(root, ignore_errors=True)


class FakeBackend:
    def __init__(self, found=True, proxy=True, running=False):
        self.found = found
        self.proxy = proxy
        self.running = running
        self.launched = None
        self.stopped = None
        self.calls = []

    def detect(self, app, override):
        return AppStatus(app.id, found=self.found, direct=False,
                         launch_target="t", match_root="r")

    def launch(self, status, env):
        self.calls.append("launch")
        self.launched = (status, env)

    def is_running(self, status):
        return self.running

    def stop(self, status):
        self.calls.append("stop")
        self.stopped = status

    def proxy_enabled(self):
        return self.proxy

    def pick_path_filter(self):
        return ("*",)

    def create_shortcut(self):
        return "x"

    def remove_shortcut(self):
        return []


def test_list_apps_reports_three(monkeypatch):
    with temp_desktop_config() as f:
        with patch("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f):
            b = LauncherBridge(FakeBackend(found=True), APP_REGISTRY)
            apps = b.list_apps()
            assert [a["id"] for a in apps] == ["claude", "chatgpt", "codex"]
            assert all(a["found"] for a in apps)
            assert all(a["running"] is False for a in apps)


def test_launch_blocked_when_proxy_off():
    with temp_desktop_config() as f:
        with patch("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f):
            be = FakeBackend(found=True, proxy=False)
            b = LauncherBridge(be, APP_REGISTRY)
            result = b.launch_app("claude")
            assert result["ok"] is False
            assert "系统代理" in result["error"]
            assert be.launched is None


def test_launch_blocked_when_not_found():
    with temp_desktop_config() as f:
        with patch("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f):
            be = FakeBackend(found=False, proxy=True)
            b = LauncherBridge(be, APP_REGISTRY)
            result = b.launch_app("claude")
            assert result["ok"] is False
            assert be.launched is None


def test_launch_merges_env_with_per_app_winning():
    with temp_desktop_config() as f:
        with patch("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f):
            from src.code_ai.desktop import config as cfg
            data = cfg.load_desktop_config()
            cfg.set_common_env(data, {"SHARED": "common", "C_ONLY": "1"})
            cfg.set_app_env(data, "claude", {"SHARED": "app", "A_ONLY": "2"})
            cfg.save_desktop_config(data)

            be = FakeBackend(found=True, proxy=True)
            b = LauncherBridge(be, APP_REGISTRY)
            result = b.launch_app("claude")
            assert result["ok"] is True
            _status, env = be.launched
            assert env["SHARED"] == "app"     # 专有 wins
            assert env["C_ONLY"] == "1"
            assert env["A_ONLY"] == "2"


def test_launch_stops_running_app_before_starting():
    with temp_desktop_config() as f:
        with patch("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f):
            be = FakeBackend(found=True, proxy=True, running=True)
            b = LauncherBridge(be, APP_REGISTRY)
            result = b.launch_app("claude")
            assert result["ok"] is True
            assert be.calls == ["stop", "launch"]
            assert be.stopped is not None
            assert be.launched is not None


def test_stop_app_not_found_returns_error():
    with temp_desktop_config() as f:
        with patch("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f):
            b = LauncherBridge(FakeBackend(found=False), APP_REGISTRY)
            assert b.stop_app("claude")["ok"] is False


def test_settings_round_trip():
    with temp_desktop_config() as f:
        with patch("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f):
            b = LauncherBridge(FakeBackend(), APP_REGISTRY)
            b.save_settings({"check_system_proxy": False, "env_vars": {"K": "V"}})
            s = b.get_settings()
            assert s["check_system_proxy"] is False
            assert s["env_vars"] == {"K": "V"}
            b.save_app_settings("codex", {"env_vars": {"X": "Y"}})
            a = b.get_app_settings("codex")
            assert a["env_vars"] == {"X": "Y"}

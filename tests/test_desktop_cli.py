from contextlib import contextmanager
from pathlib import Path
import shutil
from uuid import uuid4

from typer.testing import CliRunner

from src.code_ai.cli import app

runner = CliRunner()


@contextmanager
def temp_desktop_config():
    root = Path.cwd() / ".test-artifacts" / str(uuid4())
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root / "desktop.yaml"
    finally:
        shutil.rmtree(root, ignore_errors=True)


class FakeBackend:
    def __init__(self):
        self.removed = ["/path/AI Launcher.lnk"]

    def create_shortcut(self):
        return "/path/AI Launcher.lnk"

    def remove_shortcut(self):
        return self.removed


def test_install_creates_shortcut(monkeypatch):
    monkeypatch.setattr("src.code_ai.desktop.platforms.get_backend", lambda: FakeBackend())
    result = runner.invoke(app, ["desktop", "install"])
    assert result.exit_code == 0
    assert "AI Launcher.lnk" in result.output


def test_install_unsupported_platform(monkeypatch):
    monkeypatch.setattr("src.code_ai.desktop.platforms.get_backend", lambda: None)
    result = runner.invoke(app, ["desktop", "install"])
    assert result.exit_code == 1
    assert "Windows and macOS only" in result.output


def test_uninstall_removes_shortcut_and_keeps_config(monkeypatch):
    with temp_desktop_config() as f:
        f.write_text("check_system_proxy: true\n")
        monkeypatch.setattr("src.code_ai.desktop.platforms.get_backend", lambda: FakeBackend())
        monkeypatch.setattr("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f)
        result = runner.invoke(app, ["desktop", "uninstall", "--keep-config"])
        assert result.exit_code == 0
        assert "Removed" in result.output
        assert f.exists()


def test_uninstall_purge_deletes_config(monkeypatch):
    with temp_desktop_config() as f:
        f.write_text("check_system_proxy: true\n")
        monkeypatch.setattr("src.code_ai.desktop.platforms.get_backend", lambda: FakeBackend())
        monkeypatch.setattr("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f)
        result = runner.invoke(app, ["desktop", "uninstall", "--purge"])
        assert result.exit_code == 0
        assert not f.exists()


def test_uninstall_nothing_to_remove(monkeypatch):
    class EmptyBackend(FakeBackend):
        def remove_shortcut(self):
            return []

    with temp_desktop_config() as f:
        monkeypatch.setattr("src.code_ai.desktop.platforms.get_backend", lambda: EmptyBackend())
        monkeypatch.setattr("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f)
        result = runner.invoke(app, ["desktop", "uninstall", "--keep-config"])
        assert result.exit_code == 0
        assert "nothing to remove" in result.output


def test_run_missing_extra_prints_hint(monkeypatch):
    monkeypatch.setattr("src.code_ai.desktop.platforms.get_backend", lambda: FakeBackend())
    # Force the optional-extra import check to fail.
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "webview":
            raise ImportError("no webview")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = runner.invoke(app, ["desktop", "run"])
    assert result.exit_code == 1
    assert "ai-code-switcher[desktop]" in result.output

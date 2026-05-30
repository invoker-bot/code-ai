import os

from src.code_ai.desktop.apps import get_app
from src.code_ai.desktop.platforms import windows


def test_detect_override_path_wins(tmp_path):
    exe = tmp_path / "Claude.exe"
    exe.write_text("x")
    be = windows.WindowsBackend()
    st = be.detect(get_app("claude"), str(exe))
    assert st.found is True
    assert st.direct is True
    assert st.launch_target == str(exe)
    assert st.match_root == str(exe)


def test_detect_brokered_by_package_family(monkeypatch):
    be = windows.WindowsBackend()
    monkeypatch.setattr(be, "_query_packages", lambda: [
        {"Name": "Claude", "PackageFamilyName": "Claude_pzs8sxrjxfjjc",
         "InstallLocation": r"C:\Program Files\WindowsApps\Claude_1.0_x64__pzs8sxrjxfjjc"},
    ])
    st = be.detect(get_app("claude"), None)
    assert st.found is True
    assert st.direct is False
    assert st.launch_target == "Claude_pzs8sxrjxfjjc!Claude"
    assert st.match_root == r"C:\Program Files\WindowsApps\Claude_1.0_x64__pzs8sxrjxfjjc"


def test_detect_not_found(monkeypatch):
    be = windows.WindowsBackend()
    monkeypatch.setattr(be, "_query_packages", lambda: [])
    st = be.detect(get_app("codex"), None)
    assert st.found is False


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"

    def __init__(self, value):
        self._value = value

    def OpenKey(self, root, sub):
        return "key"

    def QueryValueEx(self, key, name):
        return (self._value, 4)

    def CloseKey(self, key):
        pass


def test_proxy_enabled_true(monkeypatch):
    be = windows.WindowsBackend()
    monkeypatch.setattr(windows, "winreg", FakeWinreg(1))
    assert be.proxy_enabled() is True


def test_proxy_enabled_false_when_zero(monkeypatch):
    be = windows.WindowsBackend()
    monkeypatch.setattr(windows, "winreg", FakeWinreg(0))
    assert be.proxy_enabled() is False


def test_proxy_enabled_false_when_no_winreg(monkeypatch):
    be = windows.WindowsBackend()
    monkeypatch.setattr(windows, "winreg", None)
    assert be.proxy_enabled() is False


from src.code_ai.desktop.platforms import base as base_mod
from src.code_ai.desktop.platforms.base import AppStatus


def test_launch_brokered_uses_explorer_appsfolder(monkeypatch):
    calls = {}
    monkeypatch.setattr(windows.subprocess, "Popen",
                        lambda argv, env=None: calls.update(argv=argv, env=env))
    be = windows.WindowsBackend()
    st = AppStatus("claude", found=True, direct=False,
                   launch_target="Claude_pzs8sxrjxfjjc!Claude", match_root="C:\\x")
    be.launch(st, {"A": "1"})
    assert calls["argv"] == ["explorer.exe", "shell:AppsFolder\\Claude_pzs8sxrjxfjjc!Claude"]
    assert calls["env"] == {"A": "1"}


def test_launch_direct_runs_exe(monkeypatch):
    calls = {}
    monkeypatch.setattr(windows.subprocess, "Popen",
                        lambda argv, env=None: calls.update(argv=argv, env=env))
    be = windows.WindowsBackend()
    st = AppStatus("claude", found=True, direct=True,
                   launch_target=r"C:\Apps\Claude.exe", match_root=r"C:\Apps\Claude.exe")
    be.launch(st, {})
    assert calls["argv"] == [r"C:\Apps\Claude.exe"]


def test_is_running_and_stop_delegate_to_base(monkeypatch):
    seen = {}
    monkeypatch.setattr(base_mod, "any_process_under", lambda roots: seen.setdefault("run", roots) or True)
    monkeypatch.setattr(base_mod, "stop_processes_under", lambda roots: seen.setdefault("stop", roots))
    be = windows.WindowsBackend()
    st = AppStatus("claude", found=True, match_root=r"C:\Apps\Claude")
    assert be.is_running(st) is True
    be.stop(st)
    assert seen["run"] == [r"C:\Apps\Claude"]
    assert seen["stop"] == [r"C:\Apps\Claude"]


def test_create_shortcut_idempotent_when_exists(monkeypatch, tmp_path):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "AI Launcher.lnk").write_text("x")
    monkeypatch.setattr(windows.os.path, "expanduser", lambda p: str(tmp_path) if p == "~" else p)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))

    def boom(*a, **k):
        raise AssertionError("should not shell out when shortcut exists")
    monkeypatch.setattr(windows.subprocess, "run", boom)

    be = windows.WindowsBackend()
    path = be.create_shortcut()
    assert path == str(desktop / "AI Launcher.lnk")


def test_remove_shortcut_reports_paths(monkeypatch, tmp_path):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    lnk = desktop / "AI Launcher.lnk"
    lnk.write_text("x")
    monkeypatch.setattr(windows.os.path, "expanduser", lambda p: str(tmp_path) if p == "~" else p)
    monkeypatch.delenv("APPDATA", raising=False)

    be = windows.WindowsBackend()
    removed = be.remove_shortcut()
    assert str(lnk) in removed
    assert not lnk.exists()
    # second call: nothing to remove
    assert be.remove_shortcut() == []


def test_create_shortcut_quotes_paths_for_powershell(monkeypatch, tmp_path):
    # Fresh (non-existent) shortcut path with a PowerShell-hostile '$' in it:
    # the generated script must single-quote it, not double-quote it.
    home = tmp_path / "dev$x"
    home.mkdir()
    monkeypatch.setattr(windows.os.path, "expanduser",
                        lambda p: str(home) if p == "~" else p)
    monkeypatch.delenv("APPDATA", raising=False)
    # No icon on disk -> IconLocation line omitted.
    monkeypatch.setattr(windows.WindowsBackend, "_icon_path", lambda self: r"C:\nope\icon.ico")

    captured = {}
    monkeypatch.setattr(windows.subprocess, "run",
                        lambda argv, check=False: captured.update(argv=argv))

    be = windows.WindowsBackend()
    path = be.create_shortcut()

    expected_lnk = str(home / "Desktop" / "AI Launcher.lnk")
    assert path == expected_lnk
    script = captured["argv"][-1]
    # The hostile path is single-quoted (literal), never double-quoted.
    assert f"CreateShortcut('{expected_lnk}')" in script
    assert f'CreateShortcut("{expected_lnk}")' not in script
    assert "$s.TargetPath = '" in script

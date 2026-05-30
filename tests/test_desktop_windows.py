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

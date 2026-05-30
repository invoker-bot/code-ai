from src.code_ai.desktop.apps import get_app
from src.code_ai.desktop.platforms import macos


def test_parse_scutil_enabled():
    text = (
        "<dictionary> {\n"
        "  HTTPEnable : 1\n"
        "  HTTPProxy : 127.0.0.1\n"
        "}\n"
    )
    assert macos.MacBackend._parse_scutil(text) is True


def test_parse_scutil_https_only():
    text = "  HTTPEnable : 0\n  HTTPSEnable : 1\n"
    assert macos.MacBackend._parse_scutil(text) is True


def test_parse_scutil_disabled():
    text = "  HTTPEnable : 0\n  HTTPSEnable : 0\n"
    assert macos.MacBackend._parse_scutil(text) is False


def test_proxy_enabled_uses_scutil_output(monkeypatch):
    be = macos.MacBackend()
    monkeypatch.setattr(be, "_scutil_output", lambda: "HTTPEnable : 1\n")
    assert be.proxy_enabled() is True


def test_detect_brokered_via_find_bundle(monkeypatch):
    be = macos.MacBackend()
    monkeypatch.setattr(be, "_find_bundle", lambda app: "/Applications/Claude.app")
    st = be.detect(get_app("claude"), None)
    assert st.found is True
    assert st.direct is False
    assert st.launch_target == "/Applications/Claude.app"
    assert st.match_root == "/Applications/Claude.app"


def test_detect_not_found(monkeypatch):
    be = macos.MacBackend()
    monkeypatch.setattr(be, "_find_bundle", lambda app: "")
    st = be.detect(get_app("codex"), None)
    assert st.found is False


def test_detect_override_direct(monkeypatch, tmp_path):
    bundle = tmp_path / "Codex.app"
    bundle.mkdir()
    be = macos.MacBackend()
    monkeypatch.setattr(be, "_bundle_binary", lambda b: str(bundle / "Contents/MacOS/Codex"))
    st = be.detect(get_app("codex"), str(bundle))
    assert st.found is True
    assert st.direct is True
    assert st.launch_target == str(bundle / "Contents/MacOS/Codex")
    assert st.match_root == str(bundle)

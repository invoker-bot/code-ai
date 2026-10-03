import os
from types import SimpleNamespace

import pytest

from src.code_ai import cli
from src.code_ai.cli import UPGRADE_PACKAGES


def test_upgrade_packages_use_official_grok_cli_instead_of_gemini():
    assert "@xai-official/grok" in UPGRADE_PACKAGES
    assert "@google/gemini-cli" not in UPGRADE_PACKAGES


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_upgrade_refreshes_each_grok_login_home(monkeypatch, tmp_path, platform):
    homes = [str(tmp_path / "account-a"), str(tmp_path / "account-b")]
    monkeypatch.setattr(cli.sys, "platform", platform)
    monkeypatch.setenv("GROK_HOME", homes[0])
    monkeypatch.setattr(cli, "load_config", lambda: {
        "profiles": {
            "grok-a": {"type": "grok", "mode": "login", "credentials_path": homes[0]},
            "grok-b": {"type": "grok", "mode": "login", "credentials_path": homes[1]},
            "grok-api": {"type": "grok", "mode": "api"},
            "claude": {"type": "claude", "mode": "login", "credentials_path": str(tmp_path / "claude")},
        },
    })
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli.subprocess, "run", run)

    with pytest.raises(SystemExit) as exc:
        cli.upgrade()

    assert exc.value.code == 0
    assert len(calls) == 3
    assert "GROK_HOME" not in calls[0][1]["env"]
    assert [call[1]["env"]["GROK_HOME"] for call in calls[1:]] == homes
    if platform == "win32":
        assert calls[0][0] == "npm install -g " + " ".join(UPGRADE_PACKAGES)
        assert all(call[1]["shell"] for call in calls)
        assert [call[0] for call in calls[1:]] == ["npm rebuild -g @xai-official/grok"] * 2
    else:
        assert calls[0][0] == ["npm", "install", "-g"] + UPGRADE_PACKAGES
        assert [call[0] for call in calls[1:]] == [["npm", "rebuild", "-g", "@xai-official/grok"]] * 2
    assert os.environ["GROK_HOME"] == homes[0]


def test_upgrade_expands_and_deduplicates_grok_login_homes(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    home = str(tmp_path / "account-a")
    monkeypatch.setattr(cli, "load_config", lambda: {
        "profiles": {
            "grok-a": {"type": "grok", "mode": "login", "credentials_path": "~/account-a"},
            "grok-alias": {"type": "grok", "mode": "login", "credentials_path": home},
            "grok-default": {"type": "grok", "mode": "login", "credentials_path": "~/.grok"},
        },
    })
    calls = []

    def run(command, **kwargs):
        calls.append(kwargs["env"].get("GROK_HOME"))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli.subprocess, "run", run)

    with pytest.raises(SystemExit) as exc:
        cli.upgrade()

    assert exc.value.code == 0
    assert calls == [None, os.path.expanduser("~/account-a")]


def test_upgrade_without_grok_login_profiles_only_installs_packages(monkeypatch):
    monkeypatch.setattr(cli, "load_config", lambda: {"profiles": {}})
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli.subprocess, "run", run)

    with pytest.raises(SystemExit) as exc:
        cli.upgrade()

    assert exc.value.code == 0
    assert len(calls) == 1


def test_upgrade_stops_when_global_install_fails(monkeypatch):
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=7))

    def unexpected_load():
        pytest.fail("Profiles must not be refreshed after a failed package install")

    monkeypatch.setattr(cli, "load_config", unexpected_load)

    with pytest.raises(SystemExit) as exc:
        cli.upgrade()

    assert exc.value.code == 7


def test_upgrade_reports_grok_home_refresh_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "load_config", lambda: {
        "profiles": {
            "grok-a": {"type": "grok", "mode": "login", "credentials_path": str(tmp_path / "account-a")},
        },
    })
    results = iter([0, 9])
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=next(results)))

    with pytest.raises(SystemExit) as exc:
        cli.upgrade()

    assert exc.value.code == 9
    assert "grok-a" in capsys.readouterr().err

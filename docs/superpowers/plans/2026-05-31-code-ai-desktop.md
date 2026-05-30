# code-ai desktop (AI Launcher) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `code-ai desktop` command group that installs a double-click GUI launcher (pywebview) which starts and Steam-style babysits the Claude, ChatGPT, and Codex desktop apps on Windows and macOS.

**Architecture:** A new self-contained `src/code_ai/desktop/` package. All OS-specific work (detect / launch / monitor / proxy / shortcut) sits behind a `PlatformBackend` selected once by `get_backend()`; everything else (registry, config, env-merge, bridge, UI) is platform-agnostic. The CLI gains a `desktop` Typer sub-app with `install` / `run` / `uninstall`. Heavy deps (`pywebview`, `psutil`) are an optional `[desktop]` extra, lazily imported so `install`/`uninstall` and the whole test suite work without them.

**Tech Stack:** Python 3.9+, Typer, PyYAML (existing); pywebview + psutil (new, optional extra); psutil/winreg/PowerShell-COM on Windows, `open`/`mdfind`/`scutil`/`osacompile` on macOS.

**Reference spec:** `docs/superpowers/specs/2026-05-31-code-ai-desktop-design.md`

**Conventions to follow (from CLAUDE.md):**
- Tests import via the `src.` prefix: `from src.code_ai.desktop.X import Y`.
- Run all tests: `python -m pytest tests/ -q`. Run one: `python -m pytest tests/test_x.py::test_y -q`.
- No linter/formatter exists — do not add one.
- Commit frequently (one per task minimum).

**Import-safety rule (critical):** No module under `src/code_ai/desktop/` may import `psutil` or `webview` at module top level. `psutil` is reached through a cached lazy helper in `platforms/base.py`; `webview` is imported only inside `app.run_gui()` and inside the `cli desktop run` command. This is what keeps `install`/`uninstall` and the entire test suite runnable without the `[desktop]` extra installed.

---

## File Structure

**New package files:**
- `src/code_ai/desktop/__init__.py` — empty package marker.
- `src/code_ai/desktop/apps.py` — `AppSpec` dataclass + `APP_REGISTRY` (the 3 apps) + `get_app()`.
- `src/code_ai/desktop/config.py` — load/save `~/.code-ai/desktop.yaml` + typed getters/setters.
- `src/code_ai/desktop/env.py` — `merge_env()` (通用 + 专有, 专有 wins).
- `src/code_ai/desktop/platforms/__init__.py` — `get_backend()` selector.
- `src/code_ai/desktop/platforms/base.py` — `AppStatus`, `PlatformBackend` Protocol, shared psutil process helpers.
- `src/code_ai/desktop/platforms/windows.py` — `WindowsBackend`.
- `src/code_ai/desktop/platforms/macos.py` — `MacBackend`.
- `src/code_ai/desktop/bridge.py` — `LauncherBridge` (pywebview `js_api`, headless-testable).
- `src/code_ai/desktop/app.py` — `run_gui()`: builds window, wires bridge, status poll thread.
- `src/code_ai/desktop/ui/index.html`, `ui/app.js`, `ui/style.css` — the web UI.

> **Icons (`ui/icon.ico`, `ui/icon.icns`) are optional.** The shortcut code in Tasks 7 & 9 guards on `os.path.exists`, so a missing icon simply falls back to the default executable icon. Drop real icon files into `ui/` later if desired; the `package-data` glob `desktop/ui/*` ships whatever is present. No task creates them (they are binary assets).

**Modified files:**
- `src/code_ai/cli.py` — add the `desktop` Typer sub-app.
- `pyproject.toml` — `[project.optional-dependencies] desktop` + `package-data` for `ui/`.
- `README.md` — short `code-ai desktop` section.

**New test files:**
- `tests/test_desktop_apps.py`, `tests/test_desktop_config.py`, `tests/test_desktop_env.py`,
  `tests/test_desktop_base.py`, `tests/test_desktop_backend.py`, `tests/test_desktop_windows.py`,
  `tests/test_desktop_macos.py`, `tests/test_desktop_bridge.py`, `tests/test_desktop_app_import.py`,
  `tests/test_desktop_cli.py`.

---

## Task 1: Scaffold package + app registry

**Files:**
- Create: `src/code_ai/desktop/__init__.py`
- Create: `src/code_ai/desktop/apps.py`
- Test: `tests/test_desktop_apps.py`

- [ ] **Step 1: Create the empty package marker**

Create `src/code_ai/desktop/__init__.py` with a single line:

```python
"""code-ai desktop launcher package."""
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_desktop_apps.py`:

```python
import pytest

from src.code_ai.desktop.apps import AppSpec, APP_REGISTRY, get_app


def test_registry_has_three_known_apps():
    ids = [a.id for a in APP_REGISTRY]
    assert ids == ["claude", "chatgpt", "codex"]


def test_registry_entries_are_appspec_with_identifiers():
    claude = get_app("claude")
    assert isinstance(claude, AppSpec)
    assert claude.display == "Claude"
    assert claude.win_aumid == "Claude_pzs8sxrjxfjjc!Claude"
    assert claude.win_package_family == "Claude_pzs8sxrjxfjjc"
    assert claude.mac_bundle_name == "Claude.app"
    assert claude.mac_bundle_id == "com.anthropic.claudefordesktop"


def test_get_app_unknown_raises():
    with pytest.raises(KeyError):
        get_app("nope")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_desktop_apps.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.code_ai.desktop.apps'`.

- [ ] **Step 4: Write the implementation**

Create `src/code_ai/desktop/apps.py`:

```python
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AppSpec:
    """Platform-agnostic identity of a supported AI desktop app.

    Windows: launch by AUMID; detect/monitor by PackageFamilyName (version-proof).
    macOS:   launch/detect by .app bundle name + bundle id.
    """
    id: str
    display: str
    win_aumid: str
    win_package_family: str
    mac_bundle_name: str
    mac_bundle_id: str


APP_REGISTRY: List[AppSpec] = [
    AppSpec(
        id="claude",
        display="Claude",
        win_aumid="Claude_pzs8sxrjxfjjc!Claude",
        win_package_family="Claude_pzs8sxrjxfjjc",
        mac_bundle_name="Claude.app",
        mac_bundle_id="com.anthropic.claudefordesktop",
    ),
    AppSpec(
        id="chatgpt",
        display="ChatGPT",
        win_aumid="OpenAI.ChatGPT-Desktop_2p2nqsd0c76g0!ChatGPT",
        win_package_family="OpenAI.ChatGPT-Desktop_2p2nqsd0c76g0",
        mac_bundle_name="ChatGPT.app",
        mac_bundle_id="com.openai.chat",
    ),
    AppSpec(
        id="codex",
        display="Codex",
        win_aumid="OpenAI.Codex_2p2nqsd0c76g0!App",
        win_package_family="OpenAI.Codex_2p2nqsd0c76g0",
        mac_bundle_name="Codex.app",
        mac_bundle_id="com.openai.codex",
    ),
]

_BY_ID = {a.id: a for a in APP_REGISTRY}


def get_app(app_id: str) -> AppSpec:
    """Return the AppSpec for app_id, or raise KeyError if unknown."""
    return _BY_ID[app_id]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_desktop_apps.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add src/code_ai/desktop/__init__.py src/code_ai/desktop/apps.py tests/test_desktop_apps.py
git commit -m "feat(desktop): add app registry (AppSpec + APP_REGISTRY)"
```

---

## Task 2: Launcher config (desktop.yaml)

**Files:**
- Create: `src/code_ai/desktop/config.py`
- Test: `tests/test_desktop_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_desktop_config.py`:

```python
from contextlib import contextmanager
from pathlib import Path
import shutil
from unittest.mock import patch
from uuid import uuid4

from src.code_ai.desktop import config as cfg


@contextmanager
def temp_desktop_config():
    root = Path.cwd() / ".test-artifacts" / str(uuid4())
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root / "desktop.yaml"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_load_creates_defaults_when_missing():
    with temp_desktop_config() as f:
        with patch("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f):
            assert not f.exists()
            data = cfg.load_desktop_config()
            assert f.exists()
            assert data["check_system_proxy"] is True
            assert data["env_vars"] == {}
            assert data["apps"] == {}


def test_round_trip_common_and_app_settings():
    with temp_desktop_config() as f:
        with patch("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f):
            data = cfg.load_desktop_config()
            cfg.set_check_system_proxy(data, False)
            cfg.set_common_env(data, {"HTTP_PROXY": "http://127.0.0.1:7890"})
            cfg.set_app_env(data, "claude", {"ANTHROPIC_LOG": "debug"})
            cfg.set_app_path(data, "codex", "/Applications/Codex.app")
            cfg.save_desktop_config(data)

            reloaded = cfg.load_desktop_config()
            assert cfg.get_check_system_proxy(reloaded) is False
            assert cfg.get_common_env(reloaded) == {"HTTP_PROXY": "http://127.0.0.1:7890"}
            assert cfg.get_app_env(reloaded, "claude") == {"ANTHROPIC_LOG": "debug"}
            assert cfg.get_app_path(reloaded, "codex") == "/Applications/Codex.app"


def test_getters_default_for_unknown_app():
    with temp_desktop_config() as f:
        with patch("src.code_ai.desktop.config.DESKTOP_CONFIG_FILE", f):
            data = cfg.load_desktop_config()
            assert cfg.get_app_env(data, "ghost") == {}
            assert cfg.get_app_path(data, "ghost") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_desktop_config.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.code_ai.desktop.config'`.

- [ ] **Step 3: Write the implementation**

Create `src/code_ai/desktop/config.py`:

```python
from pathlib import Path

import yaml

DESKTOP_CONFIG_FILE = Path.home() / ".code-ai" / "desktop.yaml"

DEFAULTS = {
    "check_system_proxy": True,
    "env_vars": {},   # 通用 (common) — every app launch
    "apps": {},       # per-app: {<id>: {"path": str, "env_vars": {...}}}
}


def load_desktop_config() -> dict:
    """Load desktop.yaml, creating it with defaults on first use."""
    if not DESKTOP_CONFIG_FILE.exists():
        save_desktop_config({k: (dict(v) if isinstance(v, dict) else v)
                             for k, v in DEFAULTS.items()})
    with open(DESKTOP_CONFIG_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("check_system_proxy", True)
    data.setdefault("env_vars", {})
    data.setdefault("apps", {})
    return data


def save_desktop_config(data: dict) -> None:
    DESKTOP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DESKTOP_CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def get_check_system_proxy(data: dict) -> bool:
    return bool(data.get("check_system_proxy", True))


def set_check_system_proxy(data: dict, value: bool) -> None:
    data["check_system_proxy"] = bool(value)


def get_common_env(data: dict) -> dict:
    return dict(data.get("env_vars") or {})


def set_common_env(data: dict, env: dict) -> None:
    data["env_vars"] = dict(env)


def _app_block(data: dict, app_id: str) -> dict:
    return data.setdefault("apps", {}).setdefault(app_id, {})


def get_app_env(data: dict, app_id: str) -> dict:
    block = (data.get("apps") or {}).get(app_id) or {}
    return dict(block.get("env_vars") or {})


def set_app_env(data: dict, app_id: str, env: dict) -> None:
    _app_block(data, app_id)["env_vars"] = dict(env)


def get_app_path(data: dict, app_id: str):
    block = (data.get("apps") or {}).get(app_id) or {}
    return block.get("path")


def set_app_path(data: dict, app_id: str, path: str) -> None:
    _app_block(data, app_id)["path"] = path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_desktop_config.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/code_ai/desktop/config.py tests/test_desktop_config.py
git commit -m "feat(desktop): add desktop.yaml config with common/per-app settings"
```

---

## Task 3: Environment merge (通用 + 专有)

**Files:**
- Create: `src/code_ai/desktop/env.py`
- Test: `tests/test_desktop_env.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_desktop_env.py`:

```python
from src.code_ai.desktop.env import merge_env


def test_common_applied_and_base_preserved():
    base = {"PATH": "/bin"}
    out = merge_env(base, {"HTTP_PROXY": "http://p"}, {})
    assert out["PATH"] == "/bin"
    assert out["HTTP_PROXY"] == "http://p"


def test_per_app_overrides_common_on_shared_key():
    out = merge_env({}, {"K": "common", "ONLY_COMMON": "c"}, {"K": "app"})
    assert out["K"] == "app"            # 专有 wins
    assert out["ONLY_COMMON"] == "c"


def test_values_are_stringified():
    out = merge_env({}, {"N": 5}, {"B": True})
    assert out["N"] == "5"
    assert out["B"] == "True"


def test_none_inputs_are_safe():
    out = merge_env({"A": "1"}, None, None)
    assert out == {"A": "1"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_desktop_env.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.code_ai.desktop.env'`.

- [ ] **Step 3: Write the implementation**

Create `src/code_ai/desktop/env.py`:

```python
from typing import Dict, Mapping, Optional


def merge_env(
    base_env: Mapping[str, str],
    common: Optional[Mapping] = None,
    per_app: Optional[Mapping] = None,
) -> Dict[str, str]:
    """Build the effective launch environment.

    Layering (last writer wins): base OS env -> 通用 (common) -> 专有 (per-app).
    So a per-app key overrides a common key with the same name.
    All overlay values are coerced to str (YAML may yield ints/bools).
    """
    eff: Dict[str, str] = dict(base_env)
    for layer in (common, per_app):
        if not layer:
            continue
        for key, value in layer.items():
            eff[str(key)] = str(value)
    return eff
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_desktop_env.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/code_ai/desktop/env.py tests/test_desktop_env.py
git commit -m "feat(desktop): add env merge (per-app overrides common)"
```

---

## Task 4: Platform base — AppStatus, Protocol, shared process helpers

**Files:**
- Create: `src/code_ai/desktop/platforms/__init__.py` (empty for now; selector added in Task 5)
- Create: `src/code_ai/desktop/platforms/base.py`
- Test: `tests/test_desktop_base.py`

- [ ] **Step 1: Create the platforms package marker**

Create `src/code_ai/desktop/platforms/__init__.py`:

```python
"""Platform backends for the desktop launcher."""
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_desktop_base.py`:

```python
from src.code_ai.desktop.platforms import base


class FakeProc:
    def __init__(self, exe, children=None):
        self.info = {"exe": exe}
        self._children = children or []
        self.terminated = False
        self.killed = False

    def children(self, recursive=False):
        return list(self._children)

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class FakePsutil:
    """Minimal psutil stand-in. `dead_on_wait` controls wait_procs result."""
    def __init__(self, procs, dead_on_wait=True):
        self._procs = procs
        self._dead_on_wait = dead_on_wait

    def process_iter(self, attrs=None):
        return list(self._procs)

    def wait_procs(self, procs, timeout=None):
        if self._dead_on_wait:
            return (list(procs), [])
        return ([], list(procs))


def test_appstatus_display_state():
    assert base.AppStatus("x", found=False).display_state == "not_found"
    assert base.AppStatus("x", found=True, direct=False).display_state == "brokered"
    assert base.AppStatus("x", found=True, direct=True).display_state == "direct"


def test_any_process_under_matches_directory_prefix(monkeypatch):
    procs = [FakeProc(r"C:\Apps\Claude\app\Claude.exe"), FakeProc(r"C:\Other\thing.exe")]
    monkeypatch.setattr(base, "psutil", FakePsutil(procs))
    assert base.any_process_under([r"C:\Apps\Claude"]) is True
    assert base.any_process_under([r"C:\Nope"]) is False
    assert base.any_process_under([""]) is False


def test_stop_terminates_matches_and_children_not_others(monkeypatch):
    child = FakeProc(r"C:\Apps\Claude\helper.exe")
    match = FakeProc(r"C:\Apps\Claude\app\Claude.exe", children=[child])
    other = FakeProc(r"C:\Other\thing.exe")
    monkeypatch.setattr(base, "psutil", FakePsutil([match, other], dead_on_wait=True))

    base.stop_processes_under([r"C:\Apps\Claude"])

    assert match.terminated is True
    assert child.terminated is True
    assert other.terminated is False
    assert match.killed is False  # died on terminate, no kill needed


def test_stop_kills_stragglers(monkeypatch):
    match = FakeProc(r"C:\Apps\Claude\app\Claude.exe")
    monkeypatch.setattr(base, "psutil", FakePsutil([match], dead_on_wait=False))

    base.stop_processes_under([r"C:\Apps\Claude"])

    assert match.terminated is True
    assert match.killed is True
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_desktop_base.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.code_ai.desktop.platforms.base'`.

- [ ] **Step 4: Write the implementation**

Create `src/code_ai/desktop/platforms/base.py`:

```python
import os
from dataclasses import dataclass
from typing import List, Protocol, runtime_checkable

# Lazy, cached psutil handle. NEVER import psutil at module top — that would
# force the [desktop] extra on every code path (install/uninstall, tests).
# Tests override this attribute directly: monkeypatch.setattr(base, "psutil", fake)
psutil = None


def _psutil():
    global psutil
    if psutil is None:
        import psutil as _real
        psutil = _real
    return psutil


@dataclass
class AppStatus:
    """Resolved launch/monitor info for one app on the current OS."""
    app_id: str
    found: bool = False
    direct: bool = False        # True = custom path (reliable env); False = OS broker
    launch_target: str = ""     # AUMID (win broker) | bundle (mac broker) | binary (direct)
    match_root: str = ""        # path prefix used to identify this app's processes

    @property
    def display_state(self) -> str:
        if not self.found:
            return "not_found"
        return "direct" if self.direct else "brokered"


def _matches(exe: str, root: str) -> bool:
    if not exe or not root:
        return False
    e = os.path.normcase(os.path.abspath(exe))
    r = os.path.normcase(os.path.abspath(root))
    return e == r or e.startswith(r + os.sep)


def any_process_under(roots: List[str]) -> bool:
    """True if any running process's exe lives under one of `roots`."""
    p = _psutil()
    real_roots = [r for r in roots if r]
    if not real_roots:
        return False
    for proc in p.process_iter(["exe"]):
        exe = proc.info.get("exe") or ""
        if any(_matches(exe, r) for r in real_roots):
            return True
    return False


def stop_processes_under(roots: List[str], timeout: float = 3.0) -> int:
    """Terminate (then kill stragglers) every process under `roots` + children.

    Returns the number of processes targeted. Steam-style whole-app stop.
    """
    p = _psutil()
    real_roots = [r for r in roots if r]
    if not real_roots:
        return 0

    victims = []
    for proc in p.process_iter(["exe"]):
        exe = proc.info.get("exe") or ""
        if any(_matches(exe, r) for r in real_roots):
            victims.append(proc)

    targets = list(victims)
    for proc in victims:
        try:
            targets.extend(proc.children(recursive=True))
        except Exception:
            pass

    for proc in targets:
        try:
            proc.terminate()
        except Exception:
            pass

    _gone, alive = p.wait_procs(targets, timeout=timeout)
    for proc in alive:
        try:
            proc.kill()
        except Exception:
            pass
    return len(targets)


@runtime_checkable
class PlatformBackend(Protocol):
    """Cross-OS contract. One implementation per supported platform."""
    def detect(self, app, override_path):  # -> AppStatus
        ...

    def launch(self, status: AppStatus, env: dict) -> None:
        ...

    def is_running(self, status: AppStatus) -> bool:
        ...

    def stop(self, status: AppStatus) -> None:
        ...

    def proxy_enabled(self) -> bool:
        ...

    def pick_path_filter(self) -> tuple:
        ...

    def create_shortcut(self) -> str:
        ...

    def remove_shortcut(self) -> list:
        ...
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_desktop_base.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add src/code_ai/desktop/platforms/__init__.py src/code_ai/desktop/platforms/base.py tests/test_desktop_base.py
git commit -m "feat(desktop): add AppStatus, PlatformBackend protocol, shared psutil helpers"
```

---

## Task 5: Backend selector (get_backend)

**Files:**
- Modify: `src/code_ai/desktop/platforms/__init__.py`
- Test: `tests/test_desktop_backend.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_desktop_backend.py`:

```python
import sys

from src.code_ai.desktop.platforms import get_backend


def test_returns_windows_backend_on_win32(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    backend = get_backend()
    assert type(backend).__name__ == "WindowsBackend"


def test_returns_mac_backend_on_darwin(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    backend = get_backend()
    assert type(backend).__name__ == "MacBackend"


def test_returns_none_on_other(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert get_backend() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_desktop_backend.py -q`
Expected: FAIL with `ImportError: cannot import name 'get_backend'`.

- [ ] **Step 3: Write the implementation**

Replace the contents of `src/code_ai/desktop/platforms/__init__.py` with:

```python
"""Platform backends for the desktop launcher."""
import sys


def get_backend():
    """Return the PlatformBackend for the current OS, or None if unsupported.

    Backends are imported lazily so OS-only imports (e.g. winreg) never load on
    the wrong platform.
    """
    if sys.platform == "win32":
        from .windows import WindowsBackend
        return WindowsBackend()
    if sys.platform == "darwin":
        from .macos import MacBackend
        return MacBackend()
    return None
```

- [ ] **Step 4: Run test to verify it fails differently**

Run: `python -m pytest tests/test_desktop_backend.py -q`
Expected: FAIL — `get_backend` now imports `.windows` / `.macos`, which do not exist yet (`ModuleNotFoundError: ... 'windows'`). This confirms the selector is wired; Tasks 6–9 create the backends.

- [ ] **Step 5: Commit (selector only; tests pass after Task 9)**

```bash
git add src/code_ai/desktop/platforms/__init__.py tests/test_desktop_backend.py
git commit -m "feat(desktop): add get_backend platform selector"
```

---

## Task 6: Windows backend — detect + proxy

**Files:**
- Create: `src/code_ai/desktop/platforms/windows.py`
- Test: `tests/test_desktop_windows.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_desktop_windows.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_desktop_windows.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.code_ai.desktop.platforms.windows'`.

- [ ] **Step 3: Write the implementation**

Create `src/code_ai/desktop/platforms/windows.py`:

```python
import json
import os
import subprocess
import sys

from . import base
from .base import AppStatus

try:
    import winreg  # Windows-only; absent on macOS/Linux.
except ImportError:  # pragma: no cover - non-Windows import path
    winreg = None


class WindowsBackend:
    # ---- detection ----
    def detect(self, app, override_path=None) -> AppStatus:
        if override_path and os.path.exists(override_path):
            return AppStatus(app.id, found=True, direct=True,
                             launch_target=override_path, match_root=override_path)
        family = app.win_package_family.lower()
        for pkg in self._query_packages():
            if str(pkg.get("PackageFamilyName", "")).lower() == family:
                loc = pkg.get("InstallLocation") or ""
                return AppStatus(app.id, found=True, direct=False,
                                 launch_target=app.win_aumid, match_root=loc)
        return AppStatus(app.id, found=False)

    def _query_packages(self):
        ps = ("Get-AppxPackage | Select-Object Name,PackageFamilyName,"
              "InstallLocation | ConvertTo-Json -Compress")
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps],
                text=True, stderr=subprocess.DEVNULL,
            )
            data = json.loads(out)
        except Exception:
            return []
        if isinstance(data, dict):
            data = [data]
        return data if isinstance(data, list) else []

    # ---- proxy ----
    def proxy_enabled(self) -> bool:
        if winreg is None:
            return False
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            )
            value, _ = winreg.QueryValueEx(key, "ProxyEnable")
            winreg.CloseKey(key)
            return int(value) == 1
        except Exception:
            return False

    # ---- launch / monitor (filled in Task 7) ----
    def launch(self, status: AppStatus, env: dict) -> None:
        raise NotImplementedError

    def is_running(self, status: AppStatus) -> bool:
        raise NotImplementedError

    def stop(self, status: AppStatus) -> None:
        raise NotImplementedError

    # ---- file dialog filter ----
    def pick_path_filter(self) -> tuple:
        return ("Executable (*.exe)",)

    # ---- shortcut (filled in Task 7) ----
    def create_shortcut(self) -> str:
        raise NotImplementedError

    def remove_shortcut(self) -> list:
        raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_desktop_windows.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/code_ai/desktop/platforms/windows.py tests/test_desktop_windows.py
git commit -m "feat(desktop): Windows backend detect + system-proxy check"
```

---

## Task 7: Windows backend — launch, monitor, shortcut

**Files:**
- Modify: `src/code_ai/desktop/platforms/windows.py`
- Test: `tests/test_desktop_windows.py` (append)

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_desktop_windows.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_desktop_windows.py -q`
Expected: FAIL — `launch`/`is_running`/`stop`/`create_shortcut`/`remove_shortcut` raise `NotImplementedError`.

- [ ] **Step 3: Replace the placeholder methods**

In `src/code_ai/desktop/platforms/windows.py`, replace the four placeholder method bodies (`launch`, `is_running`, `stop`, `create_shortcut`, `remove_shortcut`) with real implementations. Also add `import importlib.resources` near the top imports.

Add to the top imports block:

```python
import importlib.resources
```

Replace the `# ---- launch / monitor (filled in Task 7) ----` block and the `# ---- shortcut (filled in Task 7) ----` block with:

```python
    # ---- launch / monitor ----
    def launch(self, status: AppStatus, env: dict) -> None:
        if status.direct:
            subprocess.Popen([status.launch_target], env=env)
        else:
            subprocess.Popen(
                ["explorer.exe", f"shell:AppsFolder\\{status.launch_target}"],
                env=env,
            )

    def is_running(self, status: AppStatus) -> bool:
        if not status.match_root:
            return False
        return base.any_process_under([status.match_root])

    def stop(self, status: AppStatus) -> None:
        if status.match_root:
            base.stop_processes_under([status.match_root])

    # ---- shortcut ----
    def _shortcut_paths(self):
        paths = [os.path.join(os.path.expanduser("~"), "Desktop", "AI Launcher.lnk")]
        appdata = os.environ.get("APPDATA")
        if appdata:
            paths.append(os.path.join(
                appdata, "Microsoft", "Windows", "Start Menu", "Programs",
                "AI Launcher.lnk",
            ))
        return paths

    def _icon_path(self):
        icon = importlib.resources.files("code_ai.desktop").joinpath("ui", "icon.ico")
        return str(icon)

    def create_shortcut(self) -> str:
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable
        icon = self._icon_path()
        created = []
        for path in self._shortcut_paths():
            if os.path.exists(path):
                created.append(path)
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self._write_lnk(path, pythonw, "-m code_ai.cli desktop run", icon)
            created.append(path)
        return created[0] if created else ""

    def _write_lnk(self, path, target, args, icon):
        icon_line = f'$s.IconLocation = "{icon}"\n' if os.path.exists(icon) else ""
        script = (
            "$ws = New-Object -ComObject WScript.Shell\n"
            f'$s = $ws.CreateShortcut("{path}")\n'
            f'$s.TargetPath = "{target}"\n'
            f'$s.Arguments = "{args}"\n'
            f"{icon_line}"
            "$s.Save()\n"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", script], check=False)

    def remove_shortcut(self) -> list:
        removed = []
        for path in self._shortcut_paths():
            if os.path.exists(path):
                try:
                    os.remove(path)
                    removed.append(path)
                except OSError:
                    pass
        return removed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_desktop_windows.py -q`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
git add src/code_ai/desktop/platforms/windows.py tests/test_desktop_windows.py
git commit -m "feat(desktop): Windows launch/monitor/stop + .lnk shortcut create/remove"
```

---

## Task 8: macOS backend — detect + proxy

**Files:**
- Create: `src/code_ai/desktop/platforms/macos.py`
- Test: `tests/test_desktop_macos.py`

> macOS modules use only cross-platform stdlib (subprocess, plistlib, os, shutil), so these tests run on the Windows dev host. Real on-Mac behavior is smoke-tested later per the spec's §12.

- [ ] **Step 1: Write the failing test**

Create `tests/test_desktop_macos.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_desktop_macos.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.code_ai.desktop.platforms.macos'`.

- [ ] **Step 3: Write the implementation**

Create `src/code_ai/desktop/platforms/macos.py`:

```python
import importlib.resources
import os
import plistlib
import shutil
import subprocess
import sys

from . import base
from .base import AppStatus


class MacBackend:
    # ---- detection ----
    def detect(self, app, override_path=None) -> AppStatus:
        if override_path and os.path.exists(override_path):
            binary = self._bundle_binary(override_path) or override_path
            return AppStatus(app.id, found=True, direct=True,
                             launch_target=binary, match_root=override_path)
        bundle = self._find_bundle(app)
        if bundle:
            return AppStatus(app.id, found=True, direct=False,
                             launch_target=bundle, match_root=bundle)
        return AppStatus(app.id, found=False)

    def _find_bundle(self, app) -> str:
        try:
            out = subprocess.check_output(
                ["mdfind", f"kMDItemCFBundleIdentifier == '{app.mac_bundle_id}'"],
                text=True, stderr=subprocess.DEVNULL,
            )
            for line in out.splitlines():
                line = line.strip()
                if line.endswith(".app") and os.path.exists(line):
                    return line
        except Exception:
            pass
        for base_dir in ("/Applications", os.path.expanduser("~/Applications")):
            candidate = os.path.join(base_dir, app.mac_bundle_name)
            if os.path.exists(candidate):
                return candidate
        return ""

    def _bundle_binary(self, bundle: str) -> str:
        plist = os.path.join(bundle, "Contents", "Info.plist")
        try:
            with open(plist, "rb") as f:
                data = plistlib.load(f)
            name = data.get("CFBundleExecutable")
            if name:
                return os.path.join(bundle, "Contents", "MacOS", name)
        except Exception:
            pass
        return ""

    # ---- proxy ----
    def proxy_enabled(self) -> bool:
        return self._parse_scutil(self._scutil_output())

    def _scutil_output(self) -> str:
        try:
            return subprocess.check_output(
                ["scutil", "--proxy"], text=True, stderr=subprocess.DEVNULL,
            )
        except Exception:
            return ""

    @staticmethod
    def _parse_scutil(text: str) -> bool:
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("HTTPEnable") or s.startswith("HTTPSEnable"):
                if s.endswith(": 1") or s.endswith(":1"):
                    return True
        return False

    # ---- launch / monitor (filled in Task 9) ----
    def launch(self, status: AppStatus, env: dict) -> None:
        raise NotImplementedError

    def is_running(self, status: AppStatus) -> bool:
        raise NotImplementedError

    def stop(self, status: AppStatus) -> None:
        raise NotImplementedError

    # ---- file dialog filter ----
    def pick_path_filter(self) -> tuple:
        return ("Application (*.app)",)

    # ---- shortcut (filled in Task 9) ----
    def create_shortcut(self) -> str:
        raise NotImplementedError

    def remove_shortcut(self) -> list:
        raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_desktop_macos.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/code_ai/desktop/platforms/macos.py tests/test_desktop_macos.py
git commit -m "feat(desktop): macOS backend detect (mdfind/.app) + scutil proxy check"
```

---

## Task 9: macOS backend — launch, monitor, shortcut

**Files:**
- Modify: `src/code_ai/desktop/platforms/macos.py`
- Test: `tests/test_desktop_macos.py` (append)

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_desktop_macos.py`:

```python
from src.code_ai.desktop.platforms import base as base_mod
from src.code_ai.desktop.platforms.base import AppStatus


def test_launch_brokered_uses_open_a(monkeypatch):
    calls = {}
    monkeypatch.setattr(macos.subprocess, "Popen",
                        lambda argv, env=None: calls.update(argv=argv, env=env))
    be = macos.MacBackend()
    st = AppStatus("claude", found=True, direct=False,
                   launch_target="/Applications/Claude.app", match_root="/Applications/Claude.app")
    be.launch(st, {"A": "1"})
    assert calls["argv"] == ["open", "-a", "/Applications/Claude.app"]
    assert calls["env"] == {"A": "1"}


def test_launch_direct_runs_binary(monkeypatch):
    calls = {}
    monkeypatch.setattr(macos.subprocess, "Popen",
                        lambda argv, env=None: calls.update(argv=argv, env=env))
    be = macos.MacBackend()
    st = AppStatus("claude", found=True, direct=True,
                   launch_target="/Applications/Claude.app/Contents/MacOS/Claude",
                   match_root="/Applications/Claude.app")
    be.launch(st, {})
    assert calls["argv"] == ["/Applications/Claude.app/Contents/MacOS/Claude"]


def test_is_running_and_stop_delegate_to_base(monkeypatch):
    seen = {}
    monkeypatch.setattr(base_mod, "any_process_under", lambda roots: seen.setdefault("run", roots) or True)
    monkeypatch.setattr(base_mod, "stop_processes_under", lambda roots: seen.setdefault("stop", roots))
    be = macos.MacBackend()
    st = AppStatus("claude", found=True, match_root="/Applications/Claude.app")
    assert be.is_running(st) is True
    be.stop(st)
    assert seen["run"] == ["/Applications/Claude.app"]
    assert seen["stop"] == ["/Applications/Claude.app"]


def test_create_shortcut_idempotent_when_exists(monkeypatch, tmp_path):
    home = tmp_path
    (home / "Desktop").mkdir()
    appdir = home / "Desktop" / "AI Launcher.app"
    appdir.mkdir()
    monkeypatch.setattr(macos.os.path, "expanduser",
                        lambda p: p.replace("~", str(home)))

    def boom(*a, **k):
        raise AssertionError("should not shell out when shortcut exists")
    monkeypatch.setattr(macos.subprocess, "run", boom)

    be = macos.MacBackend()
    assert be.create_shortcut() == str(appdir)


def test_remove_shortcut(monkeypatch, tmp_path):
    home = tmp_path
    (home / "Desktop").mkdir()
    appdir = home / "Desktop" / "AI Launcher.app"
    appdir.mkdir()
    monkeypatch.setattr(macos.os.path, "expanduser",
                        lambda p: p.replace("~", str(home)))
    be = macos.MacBackend()
    removed = be.remove_shortcut()
    assert str(appdir) in removed
    assert not appdir.exists()
    assert be.remove_shortcut() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_desktop_macos.py -q`
Expected: FAIL — the launch/monitor/shortcut methods raise `NotImplementedError`.

- [ ] **Step 3: Replace the placeholder methods**

In `src/code_ai/desktop/platforms/macos.py`, replace the `# ---- launch / monitor (filled in Task 9) ----` block and the `# ---- shortcut (filled in Task 9) ----` block with:

```python
    # ---- launch / monitor ----
    def launch(self, status: AppStatus, env: dict) -> None:
        if status.direct:
            subprocess.Popen([status.launch_target], env=env)
        else:
            subprocess.Popen(["open", "-a", status.launch_target], env=env)

    def is_running(self, status: AppStatus) -> bool:
        if not status.match_root:
            return False
        return base.any_process_under([status.match_root])

    def stop(self, status: AppStatus) -> None:
        if status.match_root:
            base.stop_processes_under([status.match_root])

    # ---- shortcut ----
    def _shortcut_path(self):
        return os.path.expanduser("~/Desktop/AI Launcher.app")

    def create_shortcut(self) -> str:
        app_path = self._shortcut_path()
        if os.path.exists(app_path):
            return app_path
        python = sys.executable
        script = (f'do shell script "{python} -m code_ai.cli desktop run '
                  f'> /dev/null 2>&1 &"')
        subprocess.run(["osacompile", "-o", app_path, "-e", script], check=False)
        try:
            icon = str(importlib.resources.files("code_ai.desktop")
                       .joinpath("ui", "icon.icns"))
            dest = os.path.join(app_path, "Contents", "Resources", "applet.icns")
            if os.path.exists(icon) and os.path.isdir(os.path.dirname(dest)):
                shutil.copyfile(icon, dest)
        except Exception:
            pass
        return app_path

    def remove_shortcut(self) -> list:
        app_path = self._shortcut_path()
        if os.path.exists(app_path):
            shutil.rmtree(app_path, ignore_errors=True)
            return [app_path]
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_desktop_macos.py -q`
Expected: PASS (12 passed).

- [ ] **Step 5: Verify the backend selector now passes too**

Run: `python -m pytest tests/test_desktop_backend.py -q`
Expected: PASS (3 passed) — both backends now import cleanly.

- [ ] **Step 6: Commit**

```bash
git add src/code_ai/desktop/platforms/macos.py tests/test_desktop_macos.py
git commit -m "feat(desktop): macOS launch/monitor/stop + osacompile .app shortcut"
```

---

## Task 10: Bridge (headless js_api)

**Files:**
- Create: `src/code_ai/desktop/bridge.py`
- Test: `tests/test_desktop_bridge.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_desktop_bridge.py`:

```python
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
    def __init__(self, found=True, proxy=True):
        self.found = found
        self.proxy = proxy
        self.launched = None
        self.stopped = None

    def detect(self, app, override):
        return AppStatus(app.id, found=self.found, direct=False,
                         launch_target="t", match_root="r")

    def launch(self, status, env):
        self.launched = (status, env)

    def is_running(self, status):
        return False

    def stop(self, status):
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_desktop_bridge.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.code_ai.desktop.bridge'`.

- [ ] **Step 3: Write the implementation**

Create `src/code_ai/desktop/bridge.py`:

```python
import os

from .apps import APP_REGISTRY, get_app
from . import config as cfg
from .env import merge_env


class LauncherBridge:
    """pywebview js_api. Pure-Python and headless-testable.

    The GUI layer (app.py) injects `window` and `open_dialog` after the
    pywebview window is created; methods that need them degrade gracefully
    when they are absent (so unit tests never touch a real window).
    """

    def __init__(self, backend, apps=APP_REGISTRY):
        self.backend = backend
        self.apps = apps
        self.window = None
        self.open_dialog = 20  # pywebview OPEN_DIALOG; overridden in app.py
        self._status = {}
        self.refresh_detection()

    # ---- detection cache ----
    def refresh_detection(self):
        data = cfg.load_desktop_config()
        for app in self.apps:
            override = cfg.get_app_path(data, app.id)
            self._status[app.id] = self.backend.detect(app, override)

    def _running(self, app_id):
        st = self._status.get(app_id)
        if not st or not st.found:
            return False
        try:
            return bool(self.backend.is_running(st))
        except Exception:
            return False

    # ---- queries exposed to JS ----
    def list_apps(self):
        return [
            {"id": a.id, "display": a.display,
             "found": self._status[a.id].found, "running": self._running(a.id)}
            for a in self.apps
        ]

    def statuses(self):
        return {a.id: self._running(a.id) for a in self.apps}

    # ---- actions ----
    def launch_app(self, app_id):
        data = cfg.load_desktop_config()
        if cfg.get_check_system_proxy(data) and not self.backend.proxy_enabled():
            return {"ok": False, "error": "系统代理未开启，已取消启动"}
        app = get_app(app_id)
        override = cfg.get_app_path(data, app_id)
        status = self.backend.detect(app, override)
        self._status[app_id] = status
        if not status.found:
            return {"ok": False, "error": "未检测到应用，请先配置路径"}
        env = merge_env(os.environ,
                        cfg.get_common_env(data),
                        cfg.get_app_env(data, app_id))
        try:
            self.backend.launch(status, env)
        except Exception as exc:
            return {"ok": False, "error": f"启动失败: {exc}"}
        return {"ok": True}

    def stop_app(self, app_id):
        status = self._status.get(app_id)
        if not status or not status.found:
            return {"ok": False, "error": "未检测到应用"}
        try:
            self.backend.stop(status)
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
        if self.window is None:
            return {"ok": False}
        file_types = self.backend.pick_path_filter()
        result = self.window.create_file_dialog(self.open_dialog, file_types=file_types)
        if not result:
            return {"ok": False}
        path = result[0]
        data = cfg.load_desktop_config()
        cfg.set_app_path(data, app_id, path)
        cfg.save_desktop_config(data)
        self.refresh_detection()
        return {"ok": True, "path": path}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_desktop_bridge.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/code_ai/desktop/bridge.py tests/test_desktop_bridge.py
git commit -m "feat(desktop): add LauncherBridge (proxy gate, env merge, settings)"
```

---

## Task 11: GUI app + UI assets

**Files:**
- Create: `src/code_ai/desktop/app.py`
- Create: `src/code_ai/desktop/ui/index.html`
- Create: `src/code_ai/desktop/ui/style.css`
- Create: `src/code_ai/desktop/ui/app.js`
- Test: `tests/test_desktop_app_import.py`

- [ ] **Step 1: Write the failing test (import-safety + UI assets present)**

Create `tests/test_desktop_app_import.py`:

```python
import src.code_ai.desktop.app as app_mod


def test_app_module_imports_without_webview():
    # app.py must be importable with no [desktop] extra installed:
    # webview is imported only inside run_gui().
    assert hasattr(app_mod, "run_gui")


def test_ui_assets_are_packaged():
    # Anchor on the module's own location (robust regardless of how the
    # editable install registers subpackages); reads the real source tree.
    from pathlib import Path
    ui = Path(app_mod.__file__).parent / "ui"
    assert (ui / "index.html").is_file()
    assert (ui / "style.css").is_file()
    assert (ui / "app.js").is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_desktop_app_import.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.code_ai.desktop.app'`.

- [ ] **Step 3: Write `app.py`**

Create `src/code_ai/desktop/app.py`:

```python
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
```

- [ ] **Step 4: Write `ui/style.css`**

Create `src/code_ai/desktop/ui/style.css`:

```css
* { box-sizing: border-box; }
body {
  margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
  background: #15171c; color: #e6e8eb;
}
header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid #262a31;
}
header h1 { font-size: 16px; margin: 0; letter-spacing: .5px; }
.icon-btn {
  background: #20242c; border: 1px solid #2e333c; color: #cfd3da;
  border-radius: 8px; padding: 6px 10px; cursor: pointer;
}
.icon-btn:hover { background: #2a2f38; }
#apps { display: flex; gap: 16px; padding: 22px 20px; flex-wrap: wrap; }
.card {
  position: relative; width: 200px; background: #1b1e24;
  border: 1px solid #272b33; border-radius: 14px; padding: 18px;
  display: flex; flex-direction: column; align-items: center; gap: 12px;
}
.card .title { font-size: 16px; font-weight: 600; }
.card .cfg {
  position: absolute; top: 10px; right: 10px; background: transparent;
  border: none; color: #7a818c; cursor: pointer; font-size: 15px;
}
.status { font-size: 13px; }
.status.on { color: #46d27e; }
.status.off { color: #8a909a; }
.status.warn { color: #e0a93b; }
.action {
  width: 100%; padding: 9px 0; border-radius: 9px; border: none;
  cursor: pointer; font-size: 14px; font-weight: 600;
  background: #3563e9; color: white;
}
.action:hover { filter: brightness(1.08); }
.action[data-mode="stop"] { background: #b5453d; }
.action[data-mode="config"] { background: #4a5160; }
.panel {
  padding: 18px 20px; border-top: 1px solid #262a31;
}
.panel h2 { font-size: 13px; text-transform: uppercase; color: #8a909a; margin: 0 0 12px; }
.row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.env-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.env-row input {
  background: #0f1115; border: 1px solid #2a2f38; color: #e6e8eb;
  border-radius: 6px; padding: 6px 8px; flex: 1;
}
.env-row .del { background: #2a2f38; border: none; color: #cfd3da; border-radius: 6px; cursor: pointer; padding: 4px 9px; }
.linklike { background: none; border: none; color: #6ea8fe; cursor: pointer; padding: 0; }
.primary {
  background: #3563e9; border: none; color: white; border-radius: 8px;
  padding: 8px 16px; cursor: pointer; font-weight: 600;
}
.modal {
  position: fixed; inset: 0; background: rgba(0,0,0,.55);
  display: none; align-items: center; justify-content: center;
}
.modal.show { display: flex; }
.modal .box {
  background: #1b1e24; border: 1px solid #2a2f38; border-radius: 14px;
  padding: 22px; width: 420px;
}
.modal .box h3 { margin: 0 0 14px; font-size: 15px; }
.modal .actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
#toast {
  position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%);
  background: #2a2f38; color: #fff; padding: 10px 18px; border-radius: 8px;
  opacity: 0; transition: opacity .2s; pointer-events: none;
}
#toast.show { opacity: 1; }
```

- [ ] **Step 5: Write `ui/index.html`**

Create `src/code_ai/desktop/ui/index.html`:

```html
<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Launcher</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>AI Launcher</h1>
    <button class="icon-btn" id="toggle-settings">⚙ 设置</button>
  </header>

  <section id="apps"></section>

  <section class="panel" id="settings-panel" style="display:none;">
    <h2>全局设置</h2>
    <label class="row">
      <input type="checkbox" id="proxy"> 检查系统代理（启动前校验）
    </label>
    <h2>通用环境变量</h2>
    <div id="common-env"></div>
    <div class="row">
      <button class="linklike" id="add-common">＋ 添加</button>
      <button class="primary" id="save-settings">保存</button>
    </div>
  </section>

  <div class="modal" id="app-modal">
    <div class="box">
      <h3 id="app-modal-title">专有设置</h3>
      <div class="row">
        路径: <span id="app-path">(自动检测)</span>
        <button class="linklike" id="pick-path">配置路径</button>
      </div>
      <h2>专有环境变量</h2>
      <div id="app-env"></div>
      <button class="linklike" id="add-app-env">＋ 添加</button>
      <div class="actions">
        <button class="icon-btn" id="close-app">取消</button>
        <button class="primary" id="save-app">保存</button>
      </div>
    </div>
  </div>

  <div id="toast"></div>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 6: Write `ui/app.js`**

Create `src/code_ai/desktop/ui/app.js`:

```javascript
const api = () => window.pywebview.api;
let APPS = [];
let curApp = null;

async function init() {
  APPS = await api().list_apps();
  renderApps();
  await loadSettings();
}

function findApp(id) { return APPS.find((x) => x.id === id); }

function renderApps() {
  const grid = document.getElementById("apps");
  grid.innerHTML = "";
  for (const a of APPS) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML =
      `<button class="cfg" title="专有设置">⚙</button>` +
      `<div class="title">${a.display}</div>` +
      `<div class="status" id="status-${a.id}"></div>` +
      `<button class="action" id="btn-${a.id}"></button>`;
    grid.appendChild(card);
    updateCard(a.id, a.found, a.running);
    document.getElementById(`btn-${a.id}`).onclick = () => onAction(a.id);
    card.querySelector(".cfg").onclick = () => openAppSettings(a.id);
  }
}

function updateCard(id, found, running) {
  const a = findApp(id);
  if (a) { a.found = found; a.running = running; }
  const s = document.getElementById(`status-${id}`);
  const b = document.getElementById(`btn-${id}`);
  if (!s || !b) return;
  if (!found) {
    s.textContent = "⚠ 未检测到"; s.className = "status warn";
    b.textContent = "配置路径"; b.dataset.mode = "config";
  } else if (running) {
    s.textContent = "● 运行中"; s.className = "status on";
    b.textContent = "中止"; b.dataset.mode = "stop";
  } else {
    s.textContent = "○ 已停止"; s.className = "status off";
    b.textContent = "启动"; b.dataset.mode = "launch";
  }
}

async function onAction(id) {
  const mode = document.getElementById(`btn-${id}`).dataset.mode;
  if (mode === "config") {
    const r = await api().pick_app_path(id);
    if (r && r.ok) await refresh();
    return;
  }
  if (mode === "launch") {
    const r = await api().launch_app(id);
    if (!r.ok) toast(r.error);
  } else if (mode === "stop") {
    const r = await api().stop_app(id);
    if (!r.ok) toast(r.error);
  }
  await refresh();
}

async function refresh() {
  APPS = await api().list_apps();
  for (const a of APPS) updateCard(a.id, a.found, a.running);
}

window.updateStatus = (map) => {
  for (const id in map) {
    const a = findApp(id);
    if (a) updateCard(id, a.found, map[id]);
  }
};

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 3000);
}

// ---- settings ----
async function loadSettings() {
  const s = await api().get_settings();
  document.getElementById("proxy").checked = !!s.check_system_proxy;
  renderEnv("common-env", s.env_vars);
}

function renderEnv(containerId, vars) {
  const c = document.getElementById(containerId);
  c.innerHTML = "";
  for (const [k, v] of Object.entries(vars || {})) addEnvRow(containerId, k, v);
}

function addEnvRow(containerId, k = "", v = "") {
  const c = document.getElementById(containerId);
  const row = document.createElement("div");
  row.className = "env-row";
  row.innerHTML =
    `<input class="k" placeholder="KEY" value="${k}">` +
    `<span>=</span>` +
    `<input class="v" placeholder="VALUE" value="${v}">` +
    `<button class="del">×</button>`;
  row.querySelector(".del").onclick = () => row.remove();
  c.appendChild(row);
}

function collectEnv(containerId) {
  const out = {};
  for (const row of document.querySelectorAll(`#${containerId} .env-row`)) {
    const k = row.querySelector(".k").value.trim();
    const v = row.querySelector(".v").value;
    if (k) out[k] = v;
  }
  return out;
}

async function saveSettings() {
  await api().save_settings({
    check_system_proxy: document.getElementById("proxy").checked,
    env_vars: collectEnv("common-env"),
  });
  toast("已保存");
}

// ---- per-app modal ----
async function openAppSettings(id) {
  curApp = id;
  const s = await api().get_app_settings(id);
  document.getElementById("app-modal-title").textContent =
    `${findApp(id).display} 专有设置`;
  document.getElementById("app-path").textContent = s.path || "(自动检测)";
  renderEnv("app-env", s.env_vars);
  document.getElementById("app-modal").classList.add("show");
}

async function saveAppSettings() {
  await api().save_app_settings(curApp, { env_vars: collectEnv("app-env") });
  document.getElementById("app-modal").classList.remove("show");
  toast("已保存");
}

async function pickPath() {
  const r = await api().pick_app_path(curApp);
  if (r && r.ok) {
    document.getElementById("app-path").textContent = r.path;
    await refresh();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("toggle-settings").onclick = () => {
    const p = document.getElementById("settings-panel");
    p.style.display = p.style.display === "none" ? "block" : "none";
  };
  document.getElementById("add-common").onclick = () => addEnvRow("common-env");
  document.getElementById("save-settings").onclick = saveSettings;
  document.getElementById("add-app-env").onclick = () => addEnvRow("app-env");
  document.getElementById("save-app").onclick = saveAppSettings;
  document.getElementById("pick-path").onclick = pickPath;
  document.getElementById("close-app").onclick = () =>
    document.getElementById("app-modal").classList.remove("show");
});

window.addEventListener("pywebviewready", init);
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/test_desktop_app_import.py -q`
Expected: PASS (2 passed).

- [ ] **Step 8: Commit**

```bash
git add src/code_ai/desktop/app.py src/code_ai/desktop/ui/ tests/test_desktop_app_import.py
git commit -m "feat(desktop): GUI app shell (run_gui + poll thread) and web UI assets"
```

---

## Task 12: CLI desktop sub-app (install / run / uninstall)

**Files:**
- Modify: `src/code_ai/cli.py`
- Test: `tests/test_desktop_cli.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_desktop_cli.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_desktop_cli.py -q`
Expected: FAIL — the `desktop` command group does not exist yet (`No such command 'desktop'` / non-zero exit with usage error).

- [ ] **Step 3: Add the desktop sub-app to `cli.py`**

In `src/code_ai/cli.py`, add the following block immediately **before** the `def version_callback(value: bool):` line (after the `run_command` function):

```python
desktop_app = typer.Typer(
    help="AI desktop launcher: install / run / uninstall",
    add_completion=False,
)
app.add_typer(desktop_app, name="desktop")

_DESKTOP_UNSUPPORTED = "code-ai desktop is supported on Windows and macOS only."


@desktop_app.command("install")
def desktop_install():
    """Create the double-click desktop shortcut (idempotent)."""
    from .desktop.platforms import get_backend

    backend = get_backend()
    if backend is None:
        typer.echo(_DESKTOP_UNSUPPORTED)
        raise typer.Exit(1)
    path = backend.create_shortcut()
    if path:
        typer.echo(f"Shortcut ready: {path}")
        typer.echo("Open the launcher anytime with: code-ai desktop run")
    else:
        typer.echo("Could not create the shortcut.")
        raise typer.Exit(1)


@desktop_app.command("run")
def desktop_run():
    """Open the AI launcher GUI window."""
    from .desktop.platforms import get_backend

    backend = get_backend()
    if backend is None:
        typer.echo(_DESKTOP_UNSUPPORTED)
        raise typer.Exit(1)
    try:
        import webview  # noqa: F401
        import psutil  # noqa: F401
    except ImportError:
        typer.echo("The desktop launcher needs extra dependencies.")
        typer.echo("Install them with: pip install ai-code-switcher[desktop]")
        raise typer.Exit(1)
    from .desktop.app import run_gui

    run_gui()


@desktop_app.command("uninstall")
def desktop_uninstall(
    purge: bool = typer.Option(
        False, "--purge", help="Also delete ~/.code-ai/desktop.yaml without asking"
    ),
    keep_config: bool = typer.Option(
        False, "--keep-config", help="Keep ~/.code-ai/desktop.yaml without asking"
    ),
):
    """Remove the shortcut, then optionally delete launcher settings."""
    from .desktop.platforms import get_backend
    from .desktop import config as desktop_config

    backend = get_backend()
    if backend is None:
        typer.echo(_DESKTOP_UNSUPPORTED)
        raise typer.Exit(1)

    removed = backend.remove_shortcut()
    if removed:
        for path in removed:
            typer.echo(f"Removed: {path}")
    else:
        typer.echo("No shortcut found — nothing to remove.")

    config_path = desktop_config.DESKTOP_CONFIG_FILE
    if not config_path.exists() or keep_config:
        return

    delete = purge
    if not purge:
        delete = typer.confirm(
            f"Also delete launcher settings ({config_path})?", default=False
        )
    if delete:
        config_path.unlink()
        typer.echo("Deleted launcher settings.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_desktop_cli.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Manually verify the command is registered**

Run: `PYTHONPATH=src python -m code_ai.cli desktop --help`
Expected: Help text listing `install`, `run`, `uninstall`.

- [ ] **Step 6: Commit**

```bash
git add src/code_ai/cli.py tests/test_desktop_cli.py
git commit -m "feat(desktop): add 'code-ai desktop' install/run/uninstall command group"
```

---

## Task 13: Packaging, README, and full verification

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`

- [ ] **Step 1: Add the optional extra and package data to `pyproject.toml`**

In `pyproject.toml`, after the `dependencies = [...]` block (after line `]` that closes dependencies, before `[project.scripts]`), insert:

```toml
[project.optional-dependencies]
desktop = ["pywebview>=5", "psutil>=5.9"]
```

And after the `[tool.setuptools.packages.find]` block, insert:

```toml
[tool.setuptools.package-data]
code_ai = ["desktop/ui/*"]
```

- [ ] **Step 2: Verify the package builds metadata without error**

Run: `python -m pip install -e . -q`
Expected: Reinstalls `ai-code-switcher` with no errors (base deps only; the `[desktop]` extra is not pulled in).

- [ ] **Step 3: Append a README section**

Run this exact command to append the docs (PowerShell here-string keeps the literal text):

```bash
cat >> README.md <<'EOF'

## Desktop launcher (`code-ai desktop`)

A double-clickable GUI (Windows + macOS) that starts and Steam-style stops the
Claude, ChatGPT, and Codex desktop apps. Each app has one button that toggles
between **启动** (launch) and **中止** (stop), with a live running indicator.

```bash
pip install ai-code-switcher[desktop]   # one-time: install the GUI deps
code-ai desktop install                 # create the double-click shortcut
code-ai desktop run                     # open the launcher window
code-ai desktop uninstall               # remove the shortcut (asks about settings)
```

Settings live in `~/.code-ai/desktop.yaml` (separate from CLI profiles): a
"check system proxy" toggle, plus **通用** (common) and **专有** (per-app)
environment variables. Per-app values override common values on a shared key.
EOF
```

- [ ] **Step 4: Run the FULL test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS — all existing tests plus the new desktop tests (no failures, no errors). Confirm the new files contributed roughly 50+ new passing tests and that the pre-existing `test_integration.py` / `test_launcher.py` / `test_models.py` still pass.

- [ ] **Step 5: Smoke-test the CLI surface (no GUI)**

Run: `PYTHONPATH=src python -m code_ai.cli --help`
Expected: top-level help now lists the `desktop` command alongside `run`, `list`, etc.

Run: `PYTHONPATH=src python -m code_ai.cli desktop install`
Expected (on this Windows host): prints `Shortcut ready: ...AI Launcher.lnk` and the run hint; a shortcut appears on the Desktop.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml README.md
git commit -m "build(desktop): add optional [desktop] extra, package UI assets, document command"
```

- [ ] **Step 7 (manual, optional): GUI smoke test**

Run: `pip install -e ".[desktop]" -q` then `PYTHONPATH=src python -m code_ai.cli desktop run`
Expected: the AI Launcher window opens; cards show 运行中 / 已停止 / 未检测到; launch/中止 work; settings persist to `~/.code-ai/desktop.yaml`. (macOS behavior — `open`/`scutil`/`osacompile` and the bundle IDs in §3 — must be confirmed on a real Mac per spec §12.)

---

## Verification of full test suite

After Task 13, the complete suite must be green:

Run: `python -m pytest tests/ -q`
Expected: all passing. The desktop feature adds no new prompt to `add_profile`, so the existing `tests/test_integration.py` `side_effect` input lists are unchanged.

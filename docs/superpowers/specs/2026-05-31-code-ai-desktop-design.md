# `code-ai desktop` — AI Launcher — Design

**Date:** 2026-05-31
**Status:** Approved (design phase)
**Feature:** A double-clickable desktop launcher that starts and Steam-style babysits the Claude, ChatGPT, and Codex desktop apps. Cross-platform: Windows + macOS.

---

## 1. Overview & scope

`code-ai desktop` adds a new subcommand that creates a double-clickable desktop shortcut (once) and opens a small GUI window (pywebview). The window shows one card per supported AI desktop app — **Claude**, **ChatGPT**, **Codex** — each with a single button that behaves like Steam's play/stop control:

- When the app is **stopped**, the button reads **启动** (Launch).
- When the app is **running**, the same button flips to **中止** (Stop) and a status indicator shows it as running.
- Clicking **中止** terminates the whole app (all its processes), exactly like Steam stopping a running game.

The launcher monitors the apps continuously, so status stays correct even if an app was started or closed outside the launcher.

### Platform scope

**Windows and macOS.** The OS-specific concerns — detection, launch, process monitoring, the system-proxy check, and the double-click shortcut — are isolated behind a `PlatformBackend` interface (§2.1) with one implementation per OS. The config, bridge, UI, and app registry are fully platform-agnostic. On Linux (or any unsupported platform) the `desktop` command prints a friendly "supported on Windows and macOS only" message and exits cleanly.

> **Verification note:** The Windows backend is developed and testable on the target machine. The macOS backend is implemented to spec but **must be smoke-tested on a real Mac** before macOS is considered done (paths, `open`/`osacompile`/`scutil` behavior cannot be executed from the Windows dev environment).

### Non-goals (v1)

Auto-start on boot; system-tray icon / minimize-to-tray; Linux support; launching the underlying *CLIs* (this launches the GUI desktop apps); bundling a standalone executable (PyInstaller / py2app). All are deferrable behind the module boundary defined below.

---

## 2. Module layout

A new self-contained package `src/code_ai/desktop/` keeps the small CLI core clean. Each module has one job, matching the project's existing one-purpose-per-module style. **No existing module's behavior changes**; `cli.py` only gains one new command.

```
src/code_ai/desktop/
  __init__.py
  apps.py            # AppSpec registry: id, display, + per-OS launch/match identifiers
  config.py          # load/save ~/.code-ai/desktop.yaml (separate from CLI profiles)
  env.py             # merge 通用 + 专有 env into the effective launch environment
  bridge.py          # pywebview js_api class + background status-poll thread
  app.py             # builds the window, wires the bridge, webview.start(...)
  platforms/
    __init__.py      # get_backend() -> selects WindowsBackend | MacBackend | None
    base.py          # PlatformBackend protocol (the cross-OS contract)
    windows.py       # MSIX/AppsFolder, Get-AppxPackage, registry proxy, .lnk shortcut
    macos.py         # .app bundles, open/mdfind, scutil proxy, osacompile .app shortcut
  ui/index.html
  ui/app.js
  ui/style.css
  ui/icon.ico        # Windows icon
  ui/icon.icns       # macOS icon
```

### 2.1 The `PlatformBackend` contract (`platforms/base.py`)

The single seam between platform-agnostic code and OS specifics. Selected **once** at startup by `get_backend()` based on `sys.platform` (`win32` → Windows, `darwin` → macOS, else `None` → unsupported message).

```python
class PlatformBackend(Protocol):
    def detect(self, app: AppSpec, override_path: str | None) -> AppStatus: ...
    #   resolves install state + the concrete launch target

    def launch(self, resolved: AppStatus, env: dict[str, str]) -> None: ...
    #   brokered launch by default; direct-binary launch when a custom path is set

    def is_running(self, resolved: AppStatus) -> bool: ...
    def stop(self, resolved: AppStatus) -> None: ...

    def proxy_enabled(self) -> bool: ...
    def pick_path_filter(self) -> tuple[str, ...]: ...
    #   file-dialog filter: (".exe",) on Windows, (".app",) on macOS

    def create_shortcut(self) -> str: ...
    #   creates the double-click launcher, returns its path
```

### Design rationale

- **Two separate config files, deliberately.** CLI profiles stay in `~/.code-ai/config.yaml` and drive the env-switching `run` path. The launcher's own settings live in `~/.code-ai/desktop.yaml`. Keeping them apart means the desktop feature cannot corrupt or churn-migrate the profiles, and `profile_from_dict` / `launcher.py` stay untouched.
- **One platform seam, not scattered `if sys.platform`.** All OS divergence lives in `platforms/`; every other module is OS-agnostic. Adding Linux later = one new backend file.
- **Detection runs once; monitoring never shells out.** The expensive discovery call (`Get-AppxPackage` on Windows, `mdfind`/dir scan on macOS) runs a single time at startup. The ~1.5 s status loop is pure in-process `psutil`, so the UI stays responsive.

---

## 3. App registry & detection (`apps.py` + per-OS `detect`)

`apps.py` holds the platform-agnostic identity plus a small per-OS identifier bundle. Detected identifiers for the three apps:

| id | display | Windows AUMID / folder signature | macOS bundle name / id |
|---|---|---|---|
| `claude` | Claude | `Claude_pzs8sxrjxfjjc!Claude` · `^Claude_.*_pzs8sxrjxfjjc$` | `Claude.app` · `com.anthropic.claudefordesktop` |
| `chatgpt` | ChatGPT | `OpenAI.ChatGPT-Desktop_2p2nqsd0c76g0!ChatGPT` · `^OpenAI\.ChatGPT-Desktop_.*_2p2nqsd0c76g0$` | `ChatGPT.app` · `com.openai.chat` |
| `codex` | Codex | `OpenAI.Codex_2p2nqsd0c76g0!App` · `^OpenAI\.Codex_.*_2p2nqsd0c76g0$` | `Codex.app` · `com.openai.codex` |

> macOS bundle identifiers above are the expected values; each must be confirmed on a real Mac during the smoke test (an app may ship a different `CFBundleIdentifier`). Detection falls back to bundle-name match if the id differs.

### `AppSpec` shape

```python
@dataclass(frozen=True)
class AppSpec:
    id: str                  # "claude" | "chatgpt" | "codex"
    display: str             # "Claude"
    win_aumid: str           # shell:AppsFolder launch id
    win_family_regex: str    # matches the versioned WindowsApps folder name
    mac_bundle_name: str     # "Claude.app"
    mac_bundle_id: str       # "com.anthropic.claudefordesktop"
```

### Detection states (`AppStatus`)

Each app resolves to exactly one of three states, carrying the concrete launch target so later calls need no re-discovery:

1. **installed-brokered** — found by the OS (MSIX via `Get-AppxPackage`; `.app` via Spotlight/dir scan). Launch via the OS broker (AUMID / `open`).
2. **installed-direct** — a user-configured custom path exists and is valid (`.exe` on Windows; `.app` bundle on macOS). Launch the binary directly (reliable env).
3. **not-found** — neither; the card shows a **配置路径** button.

When auto-detect misses an app, the card shows **配置路径** → native file dialog (filtered to `.exe` or `.app` per backend) → chosen path saved to `desktop.yaml` under `apps.<id>.path`. A configured custom path always wins over auto-detection.

Windows matches the **family signature** (name prefix + publisher-hash suffix, ignoring the version segment) so detection survives app auto-updates to a new version folder. macOS resolves the bundle by id (`mdfind`) then falls back to `/Applications/<name>.app` and `~/Applications/<name>.app`.

---

## 4. Launch + monitor engine (per-OS `launch` / `is_running` / `stop`) — core

On **both** OSes the default launch goes through an OS **broker** (Windows shell / macOS LaunchServices), so the launcher never becomes the app's parent process. "Running?" and "Stop" are answered by **process identity** (image path under the resolved app location), not by a spawned handle.

### Launch

| | Windows | macOS |
|---|---|---|
| **brokered** (default) | `Popen(["explorer.exe", f"shell:AppsFolder\\{aumid}"], env=eff)` | `Popen(["open", "-a", bundle_path], env=eff)` |
| **direct** (custom path, reliable env) | `Popen([exe_path], env=eff)` | `Popen([f"{bundle}/Contents/MacOS/{exec_name}"], env=eff)` where `exec_name` is read from the bundle's `Info.plist` (`CFBundleExecutable`) |

`eff` is the effective environment from §5.

### Is-running

`psutil.process_iter(["exe"])` → **True if ANY** process's exe path is under the app's resolved location:
- Windows: under the resolved `WindowsApps\<family>` folder (or equal to the custom `.exe`).
- macOS: under the resolved `<App>.app/` bundle path (or the custom bundle).

Electron apps spawn many helper processes (the target Windows machine showed 8 live `Claude.exe` PIDs; macOS is analogous). The rule is **any matching process alive ⇒ running**. Defining "running" by app identity (not by a handle we spawned) keeps status correct even when the app was launched outside the launcher — the behavior wanted from a Steam-style toggle.

### Stop (中止)

1. Collect every process whose exe matches the app (plus `proc.children(recursive=True)`).
2. `terminate()` each (POSIX `SIGTERM` / Windows terminate).
3. Wait up to ~3 s (`psutil.wait_procs`).
4. `kill()` any stragglers.

This closes the whole app, like Steam stopping a game. (Shared, platform-agnostic logic built on `psutil`; only the "which path counts as this app" predicate comes from the backend.)

---

## 5. Proxy check + env injection

### System-proxy check (per-OS `proxy_enabled()`)

A **检查系统代理** checkbox (default **on**), stored in `desktop.yaml`. On a launch click, if enabled and the backend reports proxy **off** → **abort the launch** and show an in-window error modal: "系统代理未开启，已取消启动". If on → proceed.

- **Windows:** read `HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings\ProxyEnable` (`1` = on).
- **macOS:** parse `scutil --proxy` for `HTTPEnable` / `HTTPSEnable` (either `1` = on).

### Environment variables — two tiers (`env.py`, platform-agnostic)

- **通用 (common)** `env_vars` — applied to **every** app launch.
- **专有 (per-app)** `apps.<id>.env_vars` — applied only when launching that specific app.

### Merge precedence at launch

```
eff = os.environ.copy()
eff.update(common_env_vars)          # 通用
eff.update(per_app_env_vars[id])     # 专有 — wins on key collision
```

**专有 wins** on a shared key (general first, specific last). This mirrors the existing `merge_launch_args` "last-occurrence-wins" convention in `launcher.py`, keeping precedence predictable across the codebase.

### Injection reliability (same rule on both OSes)

Best-effort, by design — and the rule generalizes cleanly across platforms:

- **Reliable** for **direct** launches (custom-path `.exe` / bundle inner-binary): `Popen` inherits `eff`.
- **Generally will not propagate** for **brokered** launches (Windows `explorer shell:AppsFolder`, macOS `open`): the OS broker, not the launcher, starts the process. For those, the **system-proxy check** is what actually governs network routing.

No global or persistent OS environment is modified — no system-wide side effects, no launch-window race.

---

## 6. Launcher config (`config.py` → `~/.code-ai/desktop.yaml`)

Separate file from CLI profiles. Lazily created with defaults on first open. Read/written through small typed helpers mirroring the existing `config.py` `load`/`save` pattern. **Cross-platform key** (`path`, not `exe_path`) holds whatever the OS uses (`.exe` on Windows, `.app` on macOS).

```yaml
check_system_proxy: true
env_vars:                 # 通用 — every app launch gets these
  HTTP_PROXY: http://127.0.0.1:7890
apps:
  claude:
    env_vars:             # 专有 — only Claude
      ANTHROPIC_LOG: debug
  codex:
    path: "/Applications/Codex.app"   # custom path override (.exe on Win / .app on macOS)
    env_vars:
      CODEX_SPECIFIC: value
```

Each `apps.<id>` block is the single home for both that app's custom `path` and its 专有 `env_vars`. Every key may be absent; absent blocks fall back to defaults.

---

## 7. pywebview UI + bridge (`bridge.py` + `app.py` + `ui/`)

pywebview is cross-platform (EdgeWebView2 on Windows, WKWebView on macOS); the UI and bridge are OS-agnostic and call the selected backend.

### Bridge (`js_api`)

- `list_apps()` → `[{id, display, state, running}]`
- `launch_app(id)` → `{ok, error?}` (error e.g. proxy-off)
- `stop_app(id)` → `{ok, error?}`
- `get_settings()` / `save_settings({check_system_proxy, env_vars})` — global
- `get_app_settings(id)` / `save_app_settings(id, {env_vars})` — per-app 专有
- `pick_app_path(id)` → native file dialog (filter from `backend.pick_path_filter()`), saves `path`, returns new state

### Status push loop

A daemon thread polls `is_running` for each app every ~1.5 s and pushes results to JS via `window.evaluate_js("updateStatus(...)")`. This drives the live status dots and the 启动↔中止 flip without the UI polling back constantly. Launch/stop calls return a structured result the JS renders as a modal/toast.

### Layout

The global **⚙ 设置** panel holds the proxy checkbox and the **通用环境变量** editor (key/value rows, ＋添加). Each app card has its own small **⚙** that opens that app's panel: its **专有环境变量** editor and **配置路径** (custom path). Global vs per-app is mirrored in where it is edited.

```
┌──────────────────────  AI Launcher  ────────────────┐
│                                                ⚙ 设置 │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐        │
│  │  Claude  ⚙ │ │ ChatGPT  ⚙ │ │  Codex   ⚙ │  ← per-app ⚙: 专有 env + 路径
│  │  ● 运行中   │ │  ○ 已停止   │ │ ⚠ 未检测到  │        │
│  │ [  中止  ] │ │ [  启动  ] │ │ [ 配置路径 ]│        │
│  └────────────┘ └────────────┘ └────────────┘        │
│  设置: ☑ 检查系统代理  │  通用环境变量 [K]=[V] ＋添加   │
└──────────────────────────────────────────────────────┘
```

Web assets are plain HTML/CSS/JS shipped as package data and loaded via `importlib.resources`. Visual polish to be applied at implementation time (frontend-design); the mockup is layout-only.

---

## 8. `code-ai desktop` command + shortcut (per-OS `create_shortcut()`)

New Typer command in `cli.py`:

1. **Idempotent shortcut:** if the double-click launcher is missing, create it; else leave it. "Create only if missing" makes the "install + open" action safely repeatable.
   - **Windows:** `Desktop\AI Launcher.lnk` (+ Start-Menu copy) via `WScript.Shell` (COM, no new dependency). Target `pythonw.exe -m code_ai.cli desktop`, icon `ui/icon.ico` → opens with **no console window**.
   - **macOS:** `~/Desktop/AI Launcher.app` built via `osacompile` (preinstalled) wrapping `do shell script "<python> -m code_ai.cli desktop &> /dev/null &"`, with `ui/icon.icns` dropped into the bundle's `Resources`. Double-clicks like a native app, **no Terminal window**.
2. **Open the GUI** (always).

Flag: `--no-shortcut` skips step 1 (open only). On unsupported platforms the command prints the "Windows and macOS only" message and exits before any of the above.

---

## 9. Dependencies & packaging

New deps are isolated as an **optional extra** so the base CLI stays at two dependencies. Both deps are cross-platform:

```toml
[project.optional-dependencies]
desktop = ["pywebview>=5", "psutil>=5.9"]
```

Install: `pip install ai-code-switcher[desktop]`.

The `desktop` command imports `pywebview` / `psutil` **lazily**; if missing it prints the exact install command and exits cleanly rather than raising `ImportError`. Web assets (and both icon formats) ship via `[tool.setuptools.package-data]`.

---

## 10. Testing

Follows the existing `from src.code_ai...` import style and `unittest.mock` patterns. Focus on the platform-agnostic logic and on each backend's pure-logic parts (string/path/parse), mocking the OS calls. Backend selection lets tests target either backend regardless of host OS.

- **Backend selection** — `get_backend()` returns Windows backend for `win32`, macOS for `darwin`, `None` (→ friendly exit) otherwise.
- **`apps.py` / detection (Windows)** — family-signature regex matches versioned folder names; configured custom path wins; not-found state.
- **detection (macOS)** — bundle resolution by id with fallback to `/Applications` and `~/Applications`; custom `.app` path wins. (`mdfind` / filesystem mocked.)
- **process logic** — `is_running` / `stop` driven by a **fake psutil** (monkeypatched `process_iter` / fake procs): assert path-matching (under WindowsApps folder vs under `.app` bundle) and the terminate→wait→kill escalation. No real processes spawned.
- **proxy** — Windows: monkeypatch the registry read; macOS: monkeypatch `scutil --proxy` output parsing. Proxy-on proceeds, proxy-off aborts with the correct error message.
- **env merge precedence** (`env.py`) — 专有 overrides 通用 on a shared key (the §5 rule); platform-agnostic, runs on any host.
- **`config.py`** — defaults created on first load; round-trip; both 通用 and 专有 env lists + custom `path` persist.
- **`bridge.py`** — `launch_app` returns an error result when proxy is off (no window needed; bridge logic is callable headless with a stub backend).

The existing `test_integration.py` input-mock lists are **untouched** — this feature adds no prompt to `add_profile`, so none of those `side_effect` lists change.

---

## 11. File-change summary

**New:**
- `src/code_ai/desktop/` — `apps.py`, `config.py`, `env.py`, `bridge.py`, `app.py`, `__init__.py`
- `src/code_ai/desktop/platforms/` — `__init__.py`, `base.py`, `windows.py`, `macos.py`
- `src/code_ai/desktop/ui/` — `index.html`, `app.js`, `style.css`, `icon.ico`, `icon.icns`
- `tests/test_desktop_backend.py`, `tests/test_desktop_detect.py`, `tests/test_desktop_process.py`, `tests/test_desktop_proxy.py`, `tests/test_desktop_config.py`, `tests/test_desktop_env.py`, `tests/test_desktop_bridge.py`

**Modified:**
- `src/code_ai/cli.py` — add the `desktop` command (lazy import of the desktop package)
- `pyproject.toml` — `[project.optional-dependencies] desktop`, `package-data` for `ui/`

**Untouched:** `models.py`, `launcher.py`, `config.py` (profiles), `profiles.py`, `buddy.py`, and all existing tests.

---

## 12. Cross-platform verification status

| Concern | Windows | macOS |
|---|---|---|
| Detection | dev + unit-testable on target | implement to spec → **smoke-test on Mac** |
| Launch (brokered/direct) | dev + testable | **smoke-test on Mac** |
| is_running / stop | dev + testable | **smoke-test on Mac** |
| Proxy check | dev + testable | **smoke-test on Mac** (`scutil` parse) |
| Shortcut | dev + testable | **smoke-test on Mac** (`osacompile`) |
| Bundle ids in §3 | n/a | **confirm `CFBundleIdentifier` on Mac** |

macOS is "implemented" when the spec is coded and unit tests pass with mocked OS calls; it is "done" only after the smoke-test column is checked on a real Mac.

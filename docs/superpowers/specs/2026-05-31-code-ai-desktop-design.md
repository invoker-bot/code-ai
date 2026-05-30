# `code-ai desktop` — AI Launcher — Design

**Date:** 2026-05-31
**Status:** Approved (design phase)
**Feature:** A double-clickable desktop launcher that starts and Steam-style babysits the Claude, ChatGPT, and Codex desktop apps.

---

## 1. Overview & scope

`code-ai desktop` adds a new subcommand that creates a double-clickable desktop shortcut (once) and opens a small GUI window (pywebview). The window shows one card per supported AI desktop app — **Claude**, **ChatGPT**, **Codex** — each with a single button that behaves like Steam's play/stop control:

- When the app is **stopped**, the button reads **启动** (Launch).
- When the app is **running**, the same button flips to **中止** (Stop) and a status indicator shows it as running.
- Clicking **中止** terminates the whole app (all its processes), exactly like Steam stopping a running game.

The launcher monitors the apps continuously, so status stays correct even if an app was started or closed outside the launcher.

### Platform scope

**Windows only for v1.** Detection (`Get-AppxPackage`), launch (`shell:AppsFolder`), the proxy check (Windows registry), and the `.lnk` shortcut are all Windows-specific. On macOS/Linux the `desktop` command prints a friendly "Windows-only for now" message and exits cleanly. This is deliberate YAGNI: the target environment is Windows 11, where all three apps ship as MSIX packages.

### Non-goals (v1)

Auto-start on boot; system-tray icon / minimize-to-tray; non-Windows support; launching the underlying *CLIs* (this launches the GUI desktop apps); bundling a standalone `.exe` via PyInstaller. All are deferrable behind the module boundary defined below.

---

## 2. Module layout

A new self-contained package `src/code_ai/desktop/` keeps the small CLI core clean. Each module has one job, matching the project's existing one-purpose-per-module style. **No existing module's behavior changes**; `cli.py` only gains one new command.

```
src/code_ai/desktop/
  __init__.py
  apps.py        # AppSpec registry: id, display name, AUMID, package-family signature
  detect.py      # locate each app (Get-AppxPackage once at startup) + custom-path override
  process.py     # psutil: is_running(app), stop(app) — match by image path, kill tree
  launch.py      # start app: explorer shell:AppsFolder\<AUMID> (MSIX) or Popen (exe)
  proxy.py       # read HKCU Internet Settings ProxyEnable
  config.py      # load/save ~/.code-ai/desktop.yaml (separate from profiles)
  shortcut.py    # create Desktop + Start-Menu .lnk via WScript.Shell (no new dep)
  bridge.py      # pywebview js_api class + background status-poll thread
  app.py         # builds the window, wires the bridge, webview.start(...)
  ui/index.html
  ui/app.js
  ui/style.css
  ui/icon.ico
```

### Design rationale

- **Two separate config files, deliberately.** CLI profiles stay in `~/.code-ai/config.yaml` and drive the env-switching `run` path. The launcher's own settings live in `~/.code-ai/desktop.yaml`. Keeping them apart means the desktop feature cannot corrupt or churn-migrate the profiles, and `profile_from_dict` / `launcher.py` stay untouched.
- **Detection shells out once; monitoring never does.** `Get-AppxPackage` runs a single time at window startup to resolve install locations. The ~1.5 s status loop is pure in-process `psutil`, so the UI stays responsive (this is why the hybrid engine was chosen over per-tick PowerShell polling).

---

## 3. App registry & detection (`apps.py` + `detect.py`)

A hard-coded registry of the three known apps, using the identifiers detected on the target machine:

| id | display | AUMID | family signature (version-proof folder match) |
|---|---|---|---|
| `claude` | Claude | `Claude_pzs8sxrjxfjjc!Claude` | `^Claude_.*_pzs8sxrjxfjjc$` |
| `chatgpt` | ChatGPT | `OpenAI.ChatGPT-Desktop_2p2nqsd0c76g0!ChatGPT` | `^OpenAI\.ChatGPT-Desktop_.*_2p2nqsd0c76g0$` |
| `codex` | Codex | `OpenAI.Codex_2p2nqsd0c76g0!App` | `^OpenAI\.Codex_.*_2p2nqsd0c76g0$` |

### `AppSpec` shape

```python
@dataclass(frozen=True)
class AppSpec:
    id: str             # "claude" | "chatgpt" | "codex"
    display: str        # "Claude"
    aumid: str          # shell:AppsFolder launch id
    family_regex: str   # matches the versioned WindowsApps folder name
```

### Detection states

Each app resolves to exactly one of three states:

1. **installed-msix** — found via `Get-AppxPackage` (install location resolved); launch by AUMID.
2. **installed-exe** — a user-configured custom `.exe` path exists in `desktop.yaml` and is valid; launch by `Popen`.
3. **not-found** — neither; the card shows a **配置路径** button.

When auto-detect misses an app (e.g. Codex on a machine without the MSIX, or a non-Store install), the card shows **配置路径** → pywebview native file dialog → chosen path saved to `desktop.yaml` under `apps.<id>.exe_path`. A configured custom path always wins over auto-detection.

Matching the **family signature** (name prefix + publisher-hash suffix, ignoring the version segment) keeps detection working after the apps auto-update to a new version folder.

---

## 4. Launch + monitor engine (`launch.py` + `process.py`) — core

This is the heart of the feature. MSIX apps are started by a Windows **shell broker**, so the launcher never becomes their parent process. "Running?" and "Stop" are therefore answered by **process identity** (image path under the app's install location), not by a spawned process handle.

### Launch

- **MSIX:** `subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{aumid}"], env=effective_env)`. The shell broker owns the real process tree.
- **exe override:** `subprocess.Popen([exe_path], env=effective_env)`.

(`effective_env` is computed in §5.)

### Is-running

```
psutil.process_iter(["exe"]) → True if ANY process's exe path is under the app's
resolved install location (or equals the configured custom exe path).
```

Electron apps spawn many helper processes (the target machine showed 8 live `Claude.exe` PIDs). The rule is **any matching process alive ⇒ running**. Defining "running" by app identity (not by a handle we spawned) is what makes the status correct even when the app was launched outside the launcher — the behavior wanted from a Steam-style toggle.

### Stop (中止)

1. Collect every process whose exe matches the app (plus `proc.children(recursive=True)`).
2. `terminate()` each.
3. Wait up to ~3 s (`psutil.wait_procs`).
4. `kill()` any stragglers.

This closes the whole app, like Steam stopping a game.

---

## 5. Proxy check + env injection (`proxy.py`)

### System-proxy check

A **检查系统代理** checkbox (default **on**), stored in `desktop.yaml`. On a launch click, if enabled:

- Read `HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings\ProxyEnable`.
- If `0` or absent → **abort the launch** and show an in-window error modal: "系统代理未开启，已取消启动".
- If `1` → proceed.

### Environment variables — two tiers

- **通用 (common)** `env_vars` — applied to **every** app launch.
- **专有 (per-app)** `apps.<id>.env_vars` — applied only when launching that specific app.

### Merge precedence at launch

```
effective_env = os.environ.copy()
effective_env.update(common_env_vars)          # 通用
effective_env.update(per_app_env_vars[id])     # 专有 — wins on key collision
```

**专有 wins** on a shared key (general first, specific last). This mirrors the existing `merge_launch_args` "last-occurrence-wins" convention in `launcher.py`, keeping precedence predictable across the codebase.

### Injection reliability

Best-effort, by design:

- **Reliable** for apps launched via a direct `.exe` path (`Popen` inherits `effective_env`).
- **Generally will not propagate** to shell-brokered MSIX apps (the broker, not the launcher, starts them). For those, the **system-proxy check** is what actually governs network routing.

No global or persistent Windows environment is modified — there are no system-wide side effects and no launch-window race.

---

## 6. Launcher config (`config.py` → `~/.code-ai/desktop.yaml`)

Separate file from CLI profiles. Lazily created with defaults on first open. Read/written through small typed helpers mirroring the existing `config.py` `load`/`save` pattern.

```yaml
check_system_proxy: true
env_vars:                 # 通用 — every app launch gets these
  HTTP_PROXY: http://127.0.0.1:7890
apps:
  claude:
    env_vars:             # 专有 — only Claude
      ANTHROPIC_LOG: debug
  codex:
    exe_path: "C:\\Users\\me\\AppData\\Local\\Programs\\Codex\\Codex.exe"  # custom path override
    env_vars:
      CODEX_SPECIFIC: value
```

Each `apps.<id>` block is the single home for both that app's custom path (`exe_path`) and its 专有 env (`env_vars`). Every key may be absent; absent blocks fall back to defaults.

---

## 7. pywebview UI + bridge (`bridge.py` + `app.py` + `ui/`)

### Bridge (`js_api`)

A `js_api` class exposes to the web layer:

- `list_apps()` → `[{id, display, state, running}]`
- `launch_app(id)` → `{ok, error?}` (error e.g. proxy-off)
- `stop_app(id)` → `{ok, error?}`
- `get_settings()` / `save_settings({check_system_proxy, env_vars})` — global
- `get_app_settings(id)` / `save_app_settings(id, {env_vars})` — per-app 专有
- `pick_app_path(id)` → opens native file dialog, saves `exe_path`, returns new state

### Status push loop

A daemon thread polls `is_running` for each app every ~1.5 s and pushes results to JS via `window.evaluate_js("updateStatus(...)")`. This drives the live status dots and the 启动↔中止 flip without the UI polling back constantly. Launch/stop calls return a structured result the JS renders as a modal/toast.

### Layout

The global **⚙ 设置** panel holds the proxy checkbox and the **通用环境变量** editor (key/value rows, ＋添加). Each app card has its own small **⚙** that opens that app's panel: its **专有环境变量** editor and **配置路径** (custom exe). Global vs per-app is mirrored in where it is edited.

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

## 8. `code-ai desktop` command + shortcut (`shortcut.py`)

New Typer command in `cli.py`:

1. **Idempotent shortcut:** if `Desktop\AI Launcher.lnk` (and the Start-Menu copy) is missing, create it via `WScript.Shell` (COM, no new dependency). Target: `pythonw.exe -m code_ai.cli desktop`, icon `ui/icon.ico`, so a double-click opens the window with **no console window**. "Create only if missing" makes the "install + open" action safely repeatable.
2. **Open the GUI** (always).

Flag: `--no-shortcut` skips step 1 (open only).

On non-Windows, the command prints the "Windows-only for now" message and exits before any of the above.

---

## 9. Dependencies & packaging

New deps are isolated as an **optional extra** so the base CLI stays at two dependencies:

```toml
[project.optional-dependencies]
desktop = ["pywebview>=5", "psutil>=5.9"]
```

Install: `pip install ai-code-switcher[desktop]`.

The `desktop` command imports `pywebview` / `psutil` **lazily**; if they are missing it prints the exact install command (`pip install ai-code-switcher[desktop]`) and exits cleanly rather than raising an `ImportError`. Web assets are registered via `[tool.setuptools.package-data]` so they ship in the wheel.

---

## 10. Testing

Follows the existing `from src.code_ai...` import style and `unittest.mock` patterns. Focus on the GUI/COM-free logic.

- **`detect.py`** — family-signature regex matches versioned folder names; configured custom path wins over auto-detect; not-found path returns the right state.
- **`process.py`** — `is_running` / `stop` driven by a **fake psutil** (monkeypatched `process_iter` / fake proc objects): assert path-matching and the terminate→wait→kill escalation. No real processes spawned.
- **`proxy.py`** — monkeypatch the registry read: proxy-on proceeds, proxy-off aborts with the correct error message.
- **`config.py`** — defaults created on first load; round-trip; both 通用 and 专有 env lists persist.
- **env merge precedence** — 专有 overrides 通用 on a shared key (the §5 rule).
- **`bridge.py`** — `launch_app` returns an error result when proxy is off (no window needed; bridge logic is callable headless).

The existing `test_integration.py` input-mock lists are **untouched** — this feature adds no prompt to `add_profile`, so none of those `side_effect` lists change.

---

## 11. File-change summary

**New:**
- `src/code_ai/desktop/` (all modules + `ui/` assets listed in §2)
- `tests/test_desktop_detect.py`, `tests/test_desktop_process.py`, `tests/test_desktop_proxy.py`, `tests/test_desktop_config.py`, `tests/test_desktop_bridge.py`

**Modified:**
- `src/code_ai/cli.py` — add the `desktop` command (lazy import of the desktop package)
- `pyproject.toml` — `[project.optional-dependencies] desktop`, `package-data` for `ui/`

**Untouched:** `models.py`, `launcher.py`, `config.py` (profiles), `profiles.py`, `buddy.py`, and all existing tests.

import importlib.resources
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
        return bool(base.any_process_under([status.match_root]))

    def stop(self, status: AppStatus) -> None:
        if status.match_root:
            base.stop_processes_under([status.match_root])

    # ---- file dialog filter ----
    def pick_path_filter(self) -> tuple:
        return ("Executable (*.exe)",)

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
        try:
            icon = importlib.resources.files("code_ai.desktop").joinpath(
                "ui", "icon.ico")
        except (ModuleNotFoundError, FileNotFoundError, TypeError):
            return ""
        return str(icon)

    def create_shortcut(self) -> str:
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable
        icon = self._icon_path()
        paths = self._shortcut_paths()
        # Idempotent: if any shortcut already exists, do nothing (no shell-out).
        for path in paths:
            if os.path.exists(path):
                return path
        created = []
        for path in paths:
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

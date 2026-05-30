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

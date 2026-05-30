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

    # ---- file dialog filter ----
    def pick_path_filter(self) -> tuple:
        return ("Application (*.app)",)

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

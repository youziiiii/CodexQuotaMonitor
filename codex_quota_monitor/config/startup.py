from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "CodexQuotaMonitor"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_packaged_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def set_start_on_login(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg

    if enabled and not is_packaged_app():
        raise RuntimeError("开机自启动仅支持打包后的 CodexQuotaMonitor.exe")

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            command = _startup_command()
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def _startup_command() -> str:
    if not is_packaged_app():
        raise RuntimeError("开机自启动仅支持打包后的 CodexQuotaMonitor.exe")
    return f'"{Path(sys.executable)}"'

from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "CodexQuotaMonitor"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def set_start_on_login(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg

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
    exe = Path(sys.executable)
    if exe.name.lower().endswith(".exe") and "python" not in exe.name.lower():
        return f'"{exe}"'
    main_file = Path(__file__).resolve().parents[1] / "main.py"
    return f'"{exe}" "{main_file}"'

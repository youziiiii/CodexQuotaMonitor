from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_CONFIG_PATH = Path.home() / "AppData" / "Roaming" / "CodexQuotaMonitor" / "config.json"
VALID_REFRESH_INTERVALS = {30, 60, 300, 900}


@dataclass
class AppSettings:
    refresh_interval_seconds: int = 60
    provider: str = "realtime"
    notifications_enabled: bool = True
    start_on_login: bool = False
    low_quota_alerts_enabled: bool = True
    auth_json_path: str = str(Path.home() / ".codex" / "auth.json")


class SettingsStore:
    def __init__(self, path: str | Path = DEFAULT_CONFIG_PATH) -> None:
        self.path = Path(path)
        self.last_invalid_backup_path: Path | None = None

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return self._validate(data)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return self._backup_and_restore_defaults()

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(settings)
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary_path.replace(self.path)

    def _validate(self, data: object) -> AppSettings:
        if not isinstance(data, dict):
            raise TypeError("config root must be an object")

        allowed = {field.name for field in AppSettings.__dataclass_fields__.values()}
        filtered = {key: value for key, value in data.items() if key in allowed}
        interval = filtered.get("refresh_interval_seconds", 60)
        if type(interval) is not int or interval not in VALID_REFRESH_INTERVALS:
            raise ValueError("invalid refresh_interval_seconds")
        provider = filtered.get("provider", "realtime")
        if provider not in {"realtime", "mock"}:
            raise ValueError("invalid provider")
        for name in ("notifications_enabled", "start_on_login", "low_quota_alerts_enabled"):
            if name in filtered and type(filtered[name]) is not bool:
                raise TypeError(f"invalid {name}")
        auth_path = filtered.get("auth_json_path", AppSettings().auth_json_path)
        if not isinstance(auth_path, str) or not auth_path.strip():
            raise TypeError("invalid auth_json_path")
        return AppSettings(**filtered)

    def _backup_and_restore_defaults(self) -> AppSettings:
        settings = AppSettings()
        if self.path.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup = self.path.with_name(f"{self.path.stem}.invalid-{timestamp}{self.path.suffix}")
            try:
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.path, backup)
                self.last_invalid_backup_path = backup
            except OSError:
                self.last_invalid_backup_path = None
        try:
            self.save(settings)
        except OSError:
            pass
        return settings

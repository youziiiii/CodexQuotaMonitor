from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path.home() / "AppData" / "Roaming" / "CodexQuotaMonitor" / "config.json"


@dataclass
class AppSettings:
    refresh_interval_seconds: int = 60
    provider: str = "realtime"
    notifications_enabled: bool = True
    notify_on_refresh: bool = False
    start_on_login: bool = False
    low_quota_alerts_enabled: bool = True
    auth_json_path: str = str(Path.home() / ".codex" / "auth.json")
    five_hour_limit: int = 30_000_000
    weekly_limit: int = 1_000_000_000
    account_display_name: str = "先森 罗"
    account_plan: str = "Plus"
    avatar_number: int = 33


class SettingsStore:
    def __init__(self, path: str | Path = DEFAULT_CONFIG_PATH) -> None:
        self.path = Path(path)

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppSettings()
        allowed = {field.name for field in AppSettings.__dataclass_fields__.values()}
        filtered = {key: value for key, value in data.items() if key in allowed}
        filtered.pop("api_key", None)
        filtered.pop("token", None)
        if filtered.get("provider") not in {"realtime", "mock"}:
            filtered["provider"] = "realtime"
        if filtered.get("five_hour_limit") in {200_000, 12_000_000}:
            filtered["five_hour_limit"] = 30_000_000
        if filtered.get("weekly_limit") == 2_000_000:
            filtered["weekly_limit"] = 1_000_000_000
        return AppSettings(**filtered)

    def save(self, settings: AppSettings, transient_secret: str | None = None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(settings)
        data.pop("api_key", None)
        data.pop("token", None)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

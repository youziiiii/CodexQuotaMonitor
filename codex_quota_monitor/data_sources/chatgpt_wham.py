from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from codex_quota_monitor.core.models import UsageSnapshot, UsageSource, UsageWindow, empty_snapshot
from codex_quota_monitor.core.security import redact_secret
from codex_quota_monitor.data_sources.base import UsageProvider


BASE_URL = "https://chatgpt.com/backend-api"
USAGE_URL = f"{BASE_URL}/wham/usage"
CREDITS_URL = f"{BASE_URL}/wham/rate-limit-reset-credits"


class ChatGPTWhamUsageProvider(UsageProvider):
    def __init__(
        self,
        auth_path: str | None = None,
        get_json: Callable[[str, dict[str, str]], dict[str, Any]] | None = None,
    ) -> None:
        self.auth_path = auth_path or str(Path.home() / ".codex" / "auth.json")
        self.get_json = get_json or _url_get_json

    def fetch(self, now: datetime | None = None) -> UsageSnapshot:
        now = now or datetime.now(timezone.utc)
        source = UsageSource(
            name="ChatGPT Codex 实时额度",
            kind="chatgpt_realtime",
            is_estimate=False,
            detail="来自 chatgpt.com/backend-api/wham/usage",
        )
        try:
            auth = self._load_auth()
            headers = _headers_from_auth(auth)
            usage = self.get_json(USAGE_URL, headers)
            credits = self.get_json(CREDITS_URL, headers)
            return _snapshot_from_usage(source, usage, credits, now)
        except Exception as exc:
            return empty_snapshot(source, now, f"实时额度读取失败：{redact_secret(exc)}")

    def _load_auth(self) -> dict[str, Any]:
        path = Path(self.auth_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Codex auth.json not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))


def _headers_from_auth(auth: dict[str, Any]) -> dict[str, str]:
    tokens = auth.get("tokens") or {}
    access_token = tokens.get("access_token")
    if not access_token:
        raise ValueError("Codex auth.json does not contain tokens.access_token")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "OpenAI-Beta": "codex-1",
        "originator": "Codex Desktop",
        "Accept": "application/json",
    }
    account_id = tokens.get("account_id")
    if account_id:
        headers["ChatGPT-Account-ID"] = str(account_id)
    return headers


def _url_get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def _snapshot_from_usage(
    source: UsageSource,
    usage: dict[str, Any],
    credits: dict[str, Any],
    now: datetime,
) -> UsageSnapshot:
    rate_limit = usage.get("rate_limit") or usage.get("rateLimits") or {}
    primary = _normalize_limit(rate_limit.get("primary_window") or rate_limit.get("primary"), 18_000)
    secondary = _normalize_limit(rate_limit.get("secondary_window") or rate_limit.get("secondary"), 604_800)
    available_resets = _available_resets(usage, credits)
    return UsageSnapshot(
        source=source,
        total_used_units=primary.used_units + secondary.used_units,
        five_hour=primary,
        weekly=secondary,
        last_refresh=now,
        metadata={
            "available_resets": str(available_resets),
            "unit": "实时额度",
            "plan_type": str(usage.get("plan_type") or ""),
            "allowed": str((usage.get("rate_limit") or {}).get("allowed", "")),
        },
    )


def _normalize_limit(value: Any, expected_seconds: int) -> UsageWindow:
    label = "5 小时" if expected_seconds == 18_000 else "1 周"
    if not isinstance(value, dict):
        return UsageWindow(label, 0, 100, 0, None)
    used_percent = value.get("used_percent", value.get("usedPercent", 100))
    try:
        used = int(round(float(used_percent)))
    except (TypeError, ValueError):
        used = 100
    used = max(0, min(100, used))
    reset_time = _reset_time(value)
    return UsageWindow(label, used, 100, 100 - used, reset_time)


def _reset_time(value: dict[str, Any]) -> datetime | None:
    reset_at = value.get("reset_at") or value.get("resetsAt") or value.get("resets_at")
    if reset_at is None:
        return None
    try:
        return datetime.fromtimestamp(float(reset_at), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _available_resets(usage: dict[str, Any], credits: dict[str, Any]) -> int:
    usage_count = (usage.get("rate_limit_reset_credits") or {}).get("available_count")
    credits_count = credits.get("available_count")
    for value in (usage_count, credits_count):
        if isinstance(value, int):
            return value
    return 0

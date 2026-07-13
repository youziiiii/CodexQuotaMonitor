from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from codex_quota_monitor.core.models import (
    ResetCredit,
    UsageSnapshot,
    UsageSource,
    UsageWindow,
    empty_snapshot,
)
from codex_quota_monitor.core.security import redact_secret
from codex_quota_monitor.data_sources.base import UsageProvider


BASE_URL = "https://chatgpt.com/backend-api"
USAGE_URL = f"{BASE_URL}/wham/usage"
CREDITS_URL = f"{BASE_URL}/wham/rate-limit-reset-credits"
FIVE_HOUR_SECONDS = 18_000
WEEK_SECONDS = 604_800


class ChatGPTWhamUsageProvider(UsageProvider):
    def __init__(
        self,
        auth_path: str | None = None,
        get_json: Callable[[str, dict[str, str]], dict[str, Any]] | None = None,
    ) -> None:
        self.auth_path = auth_path or str(Path.home() / ".codex" / "auth.json")
        self.get_json = get_json or _url_get_json
        self._last_available_resets: int | None = None
        self._last_reset_credits: tuple[ResetCredit, ...] = ()

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
            available_resets = _available_resets(usage, {})
            reset_credits = self._last_reset_credits
            warning_message = None
            try:
                credits = self.get_json(CREDITS_URL, headers)
                credits_resets = _available_resets({}, credits)
                if credits_resets is not None:
                    available_resets = credits_resets
                reset_credits = _reset_credits(credits)
                self._last_reset_credits = reset_credits
            except Exception as exc:
                if self._last_available_resets is not None:
                    available_resets = self._last_available_resets
                warning_message = f"重置次数刷新失败：{redact_secret(exc)}"

            if available_resets is not None:
                self._last_available_resets = available_resets
            return _snapshot_from_usage(
                source,
                usage,
                now,
                available_resets=available_resets,
                reset_credits=reset_credits,
                warning_message=warning_message,
            )
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
    now: datetime,
    available_resets: int | None = None,
    reset_credits: tuple[ResetCredit, ...] = (),
    warning_message: str | None = None,
) -> UsageSnapshot:
    rate_limit = usage.get("rate_limit") or usage.get("rateLimits") or {}
    five_hour, weekly = _classify_windows(rate_limit)
    if five_hour.percent_remaining is None and weekly.percent_remaining is None:
        raise ValueError("额度接口缺少有效的额度窗口数据")
    return UsageSnapshot(
        source=source,
        total_used_units=five_hour.used_units + weekly.used_units,
        five_hour=five_hour,
        weekly=weekly,
        last_refresh=now,
        reset_credits=reset_credits,
        warning_message=warning_message,
        metadata={
            "available_resets": "--" if available_resets is None else str(available_resets),
            "unit": "实时额度",
            "plan_type": str(usage.get("plan_type") or ""),
            "allowed": str((usage.get("rate_limit") or {}).get("allowed", "")),
        },
    )


def _classify_windows(rate_limit: dict[str, Any]) -> tuple[UsageWindow, UsageWindow]:
    five_hour = UsageWindow("5 小时", 0, 0, 0, None)
    weekly = UsageWindow("1 周", 0, 0, 0, None)
    candidates = (
        (rate_limit.get("primary_window") or rate_limit.get("primary"), FIVE_HOUR_SECONDS),
        (rate_limit.get("secondary_window") or rate_limit.get("secondary"), WEEK_SECONDS),
    )
    for value, fallback_seconds in candidates:
        if not isinstance(value, dict):
            continue
        window_seconds = _window_seconds(value, fallback_seconds)
        window = _normalize_limit(value, window_seconds)
        kind = _window_kind(window_seconds, fallback_seconds)
        if kind == "weekly":
            weekly = window
        else:
            five_hour = window
    return five_hour, weekly


def _window_seconds(value: dict[str, Any], fallback: int) -> int:
    raw = value.get("limit_window_seconds", value.get("limitWindowSeconds"))
    try:
        seconds = int(raw)
    except (TypeError, ValueError):
        return fallback
    return seconds if seconds > 0 else fallback


def _window_kind(window_seconds: int, fallback: int) -> str:
    if 6 * 24 * 60 * 60 <= window_seconds <= 8 * 24 * 60 * 60:
        return "weekly"
    if 4 * 60 * 60 <= window_seconds <= 6 * 60 * 60:
        return "five_hour"
    return "weekly" if fallback == WEEK_SECONDS else "five_hour"


def _normalize_limit(value: Any, window_seconds: int) -> UsageWindow:
    label = "1 周" if _window_kind(window_seconds, window_seconds) == "weekly" else "5 小时"
    if not isinstance(value, dict):
        return UsageWindow(label, 0, 0, 0, None)
    used_percent = value.get("used_percent", value.get("usedPercent"))
    if used_percent is None:
        return UsageWindow(label, 0, 0, 0, _reset_time(value))
    try:
        used = int(round(float(used_percent)))
    except (TypeError, ValueError):
        return UsageWindow(label, 0, 0, 0, _reset_time(value))
    used = max(0, min(100, used))
    reset_time = _reset_time(value)
    return UsageWindow(label, used, 100, 100 - used, reset_time)


def _reset_time(value: dict[str, Any]) -> datetime | None:
    reset_at = value.get("reset_at") or value.get("resetsAt") or value.get("resets_at")
    return _parse_datetime(reset_at)


def _reset_credits(value: dict[str, Any]) -> tuple[ResetCredit, ...]:
    raw_credits = value.get("credits")
    if not isinstance(raw_credits, list):
        return ()

    credits: list[ResetCredit] = []
    for raw_credit in raw_credits:
        if not isinstance(raw_credit, dict):
            continue
        reset_type = str(raw_credit.get("reset_type") or "").strip()
        title = str(raw_credit.get("title") or "Full reset").strip()
        status = str(raw_credit.get("status") or "unknown").strip()
        credits.append(
            ResetCredit(
                title=title or "Full reset",
                reset_type=reset_type,
                status=status,
                granted_at=_parse_datetime(raw_credit.get("granted_at")),
                expires_at=_parse_datetime(
                    raw_credit.get("expires_at") or raw_credit.get("expiration_at")
                ),
            )
        )
    return tuple(credits)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if abs(timestamp) >= 100_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)

        text = str(value).strip()
        if not text:
            return None
        try:
            timestamp = float(text)
        except ValueError:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        if abs(timestamp) >= 100_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _available_resets(usage: dict[str, Any], credits: dict[str, Any]) -> int | None:
    usage_count = (usage.get("rate_limit_reset_credits") or {}).get("available_count")
    credits_count = credits.get("available_count")
    for value in (usage_count, credits_count):
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    raw_credits = credits.get("credits")
    if isinstance(raw_credits, list):
        return sum(
            1
            for credit in raw_credits
            if isinstance(credit, dict)
            and str(credit.get("status") or "").casefold() == "available"
        )
    return None

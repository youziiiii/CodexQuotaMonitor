from __future__ import annotations

from datetime import datetime, timezone

from codex_quota_monitor.core.models import UsageSnapshot, UsageSource, empty_snapshot
from codex_quota_monitor.data_sources.base import UsageProvider


class OpenAIAdminUsageProvider(UsageProvider):
    def fetch(self, now: datetime | None = None) -> UsageSnapshot:
        now = now or datetime.now(timezone.utc)
        source = UsageSource(
            name="OpenAI Admin Usage API",
            kind="official_api_usage",
            is_estimate=False,
            detail="官方 API 用量接口占位；它不提供个人 Codex 剩余额度。",
        )
        return empty_snapshot(
            source,
            now,
            "OpenAI API Usage 可报告组织 API 用量，但不提供个人 Codex 剩余额度；当前应用使用 ChatGPT/Codex 实时额度接口。",
        )

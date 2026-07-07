from __future__ import annotations

from datetime import datetime, timezone

from codex_quota_monitor.core.models import UsageSource, empty_snapshot
from codex_quota_monitor.core.security import redact_secret
from codex_quota_monitor.data_sources.base import UsageProvider


class RefreshService:
    def __init__(self, provider: UsageProvider) -> None:
        self.provider = provider

    def refresh(self, now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        try:
            return self.provider.fetch(now=now)
        except Exception as exc:
            source = UsageSource(
                name="刷新错误",
                kind="error",
                is_estimate=True,
                detail="数据源刷新失败，程序已继续运行。",
            )
            return empty_snapshot(source, now, f"刷新失败：{redact_secret(exc)}")

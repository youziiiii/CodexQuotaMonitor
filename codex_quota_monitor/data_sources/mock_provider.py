from __future__ import annotations

from datetime import datetime, timedelta, timezone

from codex_quota_monitor.core.models import (
    ResetCredit,
    UsageSnapshot,
    UsageSource,
    UsageWindow,
)
from codex_quota_monitor.data_sources.base import UsageProvider


class MockUsageProvider(UsageProvider):
    def fetch(self, now: datetime | None = None) -> UsageSnapshot:
        now = now or datetime.now(timezone.utc)
        return UsageSnapshot(
            source=UsageSource(
                name="Mock 演示数据",
                kind="mock",
                is_estimate=True,
                detail="演示数据，不是官方 Codex 额度。",
            ),
            total_used_units=42_000,
            five_hour=UsageWindow("5 小时演示", 7_500, 10_000, 2_500, now + timedelta(hours=2)),
            weekly=UsageWindow("周演示", 62_000, 100_000, 38_000, now + timedelta(days=3)),
            last_refresh=now,
            reset_credits=(
                ResetCredit(
                    title="Full reset",
                    reset_type="codex_rate_limits",
                    status="available",
                    granted_at=now - timedelta(days=2),
                    expires_at=now + timedelta(days=28),
                ),
                ResetCredit(
                    title="Full reset",
                    reset_type="codex_rate_limits",
                    status="available",
                    granted_at=now - timedelta(days=1),
                    expires_at=now + timedelta(days=29),
                ),
            ),
            metadata={"available_resets": "2", "unit": "演示额度"},
        )

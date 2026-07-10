from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class UsageSource:
    name: str
    kind: str
    is_estimate: bool
    detail: str


@dataclass(frozen=True)
class UsageWindow:
    label: str
    used_units: int
    limit_units: int
    remaining_units: int
    reset_time: datetime | None

    @property
    def percent_used(self) -> int | None:
        if self.limit_units <= 0:
            return None
        return max(0, min(100, round(self.used_units / self.limit_units * 100)))

    @property
    def percent_remaining(self) -> int | None:
        if self.limit_units <= 0:
            return None
        return max(0, min(100, round(self.remaining_units / self.limit_units * 100)))


@dataclass(frozen=True)
class UsageSnapshot:
    source: UsageSource
    total_used_units: int
    five_hour: UsageWindow
    weekly: UsageWindow
    last_refresh: datetime
    error_message: str | None = None
    warning_message: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def empty_snapshot(source: UsageSource, now: datetime, error_message: str | None = None) -> UsageSnapshot:
    return UsageSnapshot(
        source=source,
        total_used_units=0,
        five_hour=UsageWindow("5 小时窗口", 0, 0, 0, None),
        weekly=UsageWindow("周窗口", 0, 0, 0, None),
        last_refresh=now,
        error_message=error_message,
    )

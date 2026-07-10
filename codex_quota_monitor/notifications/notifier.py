from __future__ import annotations

from codex_quota_monitor.core.models import UsageSnapshot
from codex_quota_monitor.core.thresholds import quota_state


class Notifier:
    def __init__(self, tray_icon=None) -> None:
        self.tray_icon = tray_icon
        self._last_alert_key: str | None = None
        self._error_active = False

    def show(self, title: str, message: str) -> None:
        if self.tray_icon is not None and self.tray_icon.supportsMessages():
            self.tray_icon.showMessage(title, message)

    def maybe_alert_low_quota(self, snapshot: UsageSnapshot, enabled: bool) -> None:
        if not enabled:
            return
        states = {
            "5 小时窗口": quota_state(snapshot.five_hour.remaining_units, snapshot.five_hour.limit_units),
            "本周窗口": quota_state(snapshot.weekly.remaining_units, snapshot.weekly.limit_units),
        }
        alert_parts = [name for name, state in states.items() if state in {"warning", "critical"}]
        if not alert_parts:
            self._last_alert_key = None
            return
        key = "|".join(f"{name}:{states[name]}" for name in alert_parts)
        if key == self._last_alert_key:
            return
        self._last_alert_key = key
        self.show(
            "Codex 额度偏低",
            f"以下窗口剩余额度低于阈值：{', '.join(alert_parts)}。",
        )

    def alert_error(self, snapshot: UsageSnapshot, enabled: bool) -> None:
        if enabled and snapshot.error_message and not self._error_active:
            self._error_active = True
            self.show("Codex 额度刷新失败", snapshot.error_message)

    def clear_error(self) -> None:
        self._error_active = False

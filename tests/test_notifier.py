from datetime import datetime, timezone

from codex_quota_monitor.core.models import UsageSource, empty_snapshot
from codex_quota_monitor.notifications.notifier import Notifier


class RecordingNotifier(Notifier):
    def __init__(self):
        super().__init__()
        self.messages = []

    def show(self, title: str, message: str) -> None:
        self.messages.append((title, message))


def test_refresh_error_notifies_once_until_success_clears_state():
    notifier = RecordingNotifier()
    source = UsageSource("刷新错误", "error", True, "test")
    snapshot = empty_snapshot(source, datetime.now(timezone.utc), "network failed")

    notifier.alert_error(snapshot, enabled=True)
    notifier.alert_error(snapshot, enabled=True)
    notifier.clear_error()
    notifier.alert_error(snapshot, enabled=True)

    assert len(notifier.messages) == 2

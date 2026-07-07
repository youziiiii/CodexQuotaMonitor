from datetime import datetime, timezone

from codex_quota_monitor.core.refresh import RefreshService


class BrokenProvider:
    def fetch(self, now=None):
        raise RuntimeError("network failed with sk-test-secret-value")


def test_refresh_service_turns_provider_exception_into_redacted_snapshot():
    now = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)
    service = RefreshService(BrokenProvider())

    snapshot = service.refresh(now=now)

    assert snapshot.error_message is not None
    assert "network failed" in snapshot.error_message
    assert "sk-test-secret-value" not in snapshot.error_message
    assert snapshot.source.kind == "error"

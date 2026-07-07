from codex_quota_monitor.core.thresholds import quota_state


def test_quota_state_uses_warning_and_critical_thresholds():
    assert quota_state(remaining=50, limit=100) == "normal"
    assert quota_state(remaining=19, limit=100) == "warning"
    assert quota_state(remaining=9, limit=100) == "critical"
    assert quota_state(remaining=0, limit=0) == "unknown"

from datetime import datetime, timezone

from codex_quota_monitor.data_sources.chatgpt_wham import ChatGPTWhamUsageProvider


def test_wham_provider_parses_realtime_usage_and_reset_credits(tmp_path):
    auth = tmp_path / "auth.json"
    auth.write_text(
        """
        {
          "tokens": {
            "access_token": "test-access-token",
            "account_id": "account-123"
          }
        }
        """,
        encoding="utf-8",
    )
    requests = []

    def fake_get(url, headers):
        requests.append((url, headers))
        if url.endswith("/wham/usage"):
            return {
                "plan_type": "plus",
                "rate_limit": {
                    "primary_window": {
                        "used_percent": 39,
                        "limit_window_seconds": 18000,
                        "reset_at": 1783436220,
                    },
                    "secondary_window": {
                        "used_percent": 5,
                        "limit_window_seconds": 604800,
                        "reset_at": 1784023680,
                    },
                },
                "rate_limit_reset_credits": {"available_count": 2},
            }
        return {"available_count": 2}

    now = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)
    provider = ChatGPTWhamUsageProvider(auth_path=str(auth), get_json=fake_get)

    snapshot = provider.fetch(now=now)

    assert snapshot.source.kind == "chatgpt_realtime"
    assert snapshot.source.is_estimate is False
    assert snapshot.five_hour.percent_remaining == 61
    assert snapshot.weekly.percent_remaining == 95
    assert snapshot.metadata["available_resets"] == "2"
    assert requests[0][1]["Authorization"] == "Bearer test-access-token"
    assert requests[0][1]["ChatGPT-Account-ID"] == "account-123"


def test_wham_provider_missing_auth_returns_visible_error(tmp_path):
    provider = ChatGPTWhamUsageProvider(auth_path=str(tmp_path / "missing.json"))

    snapshot = provider.fetch(now=datetime(2026, 7, 7, tzinfo=timezone.utc))

    assert snapshot.error_message is not None
    assert "auth.json" in snapshot.error_message
    assert snapshot.five_hour.percent_remaining is None


def test_credits_failure_keeps_last_count_and_updates_quota(tmp_path):
    auth = tmp_path / "auth.json"
    auth.write_text('{"tokens":{"access_token":"test-token"}}', encoding="utf-8")
    credit_calls = 0
    used_percent = 20

    def fake_get(url, headers):
        nonlocal credit_calls
        if url.endswith("/usage"):
            return {
                "rate_limit": {
                    "primary_window": {"used_percent": used_percent},
                    "secondary_window": {"used_percent": 30},
                }
            }
        credit_calls += 1
        if credit_calls == 1:
            return {"available_count": 3}
        raise TimeoutError("credits timeout")

    provider = ChatGPTWhamUsageProvider(auth_path=str(auth), get_json=fake_get)
    first = provider.fetch()
    used_percent = 35
    second = provider.fetch()

    assert first.metadata["available_resets"] == "3"
    assert second.five_hour.percent_remaining == 65
    assert second.metadata["available_resets"] == "3"
    assert second.error_message is None
    assert second.warning_message == "重置次数刷新失败：credits timeout"


def test_missing_usage_windows_are_reported_as_unknown_refresh_error(tmp_path):
    auth = tmp_path / "auth.json"
    auth.write_text('{"tokens":{"access_token":"test-token"}}', encoding="utf-8")
    provider = ChatGPTWhamUsageProvider(
        auth_path=str(auth),
        get_json=lambda url, headers: {"rate_limit": {}} if url.endswith("/usage") else {},
    )

    snapshot = provider.fetch()

    assert snapshot.error_message is not None
    assert "缺少有效" in snapshot.error_message
    assert snapshot.five_hour.percent_remaining is None

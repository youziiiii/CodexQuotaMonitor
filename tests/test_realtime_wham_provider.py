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

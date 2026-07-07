import json

from codex_quota_monitor.config.settings import AppSettings, SettingsStore
from codex_quota_monitor.core.security import redact_secret


def test_settings_store_does_not_persist_token_or_api_key(tmp_path):
    path = tmp_path / "config.json"
    store = SettingsStore(path)
    settings = AppSettings(
        refresh_interval_seconds=300,
        provider="realtime",
        notifications_enabled=False,
        notify_on_refresh=True,
        start_on_login=True,
        low_quota_alerts_enabled=True,
    )

    store.save(settings, transient_secret="sk-test-secret-value")
    raw = path.read_text(encoding="utf-8")

    assert "sk-test-secret-value" not in raw
    assert "api_key" not in raw.lower()
    assert json.loads(raw)["refresh_interval_seconds"] == 300
    assert store.load().provider == "realtime"


def test_redact_secret_masks_openai_and_bearer_tokens():
    text = "Bearer sk-proj-abcdef1234567890 and token=oai-test-token-value"

    redacted = redact_secret(text)

    assert "abcdef1234567890" not in redacted
    assert "oai-test-token-value" not in redacted
    assert "sk-proj-" in redacted
    assert "token=" in redacted

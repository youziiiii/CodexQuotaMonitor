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
        start_on_login=True,
        low_quota_alerts_enabled=True,
    )

    store.save(settings)
    raw = path.read_text(encoding="utf-8")

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


def test_invalid_config_is_backed_up_and_replaced_with_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[]", encoding="utf-8")
    store = SettingsStore(path)

    settings = store.load()

    assert settings == AppSettings()
    assert store.last_invalid_backup_path is not None
    assert store.last_invalid_backup_path.read_text(encoding="utf-8") == "[]"
    assert json.loads(path.read_text(encoding="utf-8"))["refresh_interval_seconds"] == 60


def test_invalid_refresh_interval_is_rejected_and_restored(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"refresh_interval_seconds": 0}', encoding="utf-8")

    settings = SettingsStore(path).load()

    assert settings.refresh_interval_seconds == 60

import pytest

from codex_quota_monitor.config import startup


def test_source_mode_cannot_create_startup_command(monkeypatch):
    monkeypatch.delattr(startup.sys, "frozen", raising=False)

    with pytest.raises(RuntimeError, match="仅支持打包"):
        startup._startup_command()


def test_packaged_exe_is_used_as_startup_command(monkeypatch):
    monkeypatch.setattr(startup.sys, "frozen", True, raising=False)
    monkeypatch.setattr(startup.sys, "executable", r"C:\Apps\CodexQuotaMonitor.exe")

    assert startup._startup_command() == '"C:\\Apps\\CodexQuotaMonitor.exe"'

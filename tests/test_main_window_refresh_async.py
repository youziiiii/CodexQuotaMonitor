from datetime import datetime, timedelta, timezone

from PySide6.QtWidgets import QApplication

from codex_quota_monitor.config.settings import AppSettings
from codex_quota_monitor.core.models import UsageSnapshot, UsageSource, UsageWindow, empty_snapshot
from codex_quota_monitor.ui.main_window import MainWindow


class Store:
    def load(self):
        return AppSettings(provider="mock", notifications_enabled=False, low_quota_alerts_enabled=False)

    def save(self, settings):
        self.saved = settings


class RecordingThreadPool:
    def __init__(self):
        self.tasks = []

    def start(self, task):
        self.tasks.append(task)


class BlockingService:
    def __init__(self):
        self.calls = 0

    def refresh(self):
        self.calls += 1
        raise AssertionError("refresh should run in the queued background task")


def test_refresh_now_queues_background_task_without_blocking_ui_thread():
    app = QApplication.instance() or QApplication([])
    pool = RecordingThreadPool()
    window = MainWindow(settings_store=Store(), thread_pool=pool, auto_refresh=False)
    window.service = BlockingService()

    window.refresh_now()

    assert app is not None
    assert window.service.calls == 0
    assert len(pool.tasks) == 1
    assert window.refresh_in_progress is True

    window.shutdown()
    window.close()


def _snapshot(five_remaining: int) -> UsageSnapshot:
    now = datetime.now(timezone.utc)
    return UsageSnapshot(
        source=UsageSource("test", "mock", True, "test"),
        total_used_units=100 - five_remaining,
        five_hour=UsageWindow("5 小时", 100 - five_remaining, 100, five_remaining, now),
        weekly=UsageWindow("1 周", 20, 100, 80, now),
        last_refresh=now,
        metadata={"available_resets": "2", "unit": "测试"},
    )


def test_provider_change_discards_old_result_and_keeps_old_display_until_new_success(monkeypatch):
    app = QApplication.instance() or QApplication([])
    pool = RecordingThreadPool()
    window = MainWindow(settings_store=Store(), thread_pool=pool, auto_refresh=False)
    monkeypatch.setattr("codex_quota_monitor.ui.main_window.set_start_on_login", lambda enabled: None)

    window._finish_refresh(_snapshot(72))
    assert window.five_line.percent.text() == "72%"

    window.refresh_now()
    old_task = pool.tasks[-1]
    window.provider_combo.setCurrentIndex(0)
    window.save_settings()
    window._finish_refresh(_snapshot(15), old_task)

    assert window.five_line.percent.text() == "72%"
    new_task = pool.tasks[-1]
    assert new_task.generation != old_task.generation

    window._finish_refresh(_snapshot(64), new_task)
    assert window.five_line.percent.text() == "64%"
    assert app is not None
    window.shutdown()
    window.close()


def test_refresh_failure_keeps_last_result_shows_duration_and_backs_off():
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings_store=Store(), auto_refresh=False)
    window._finish_refresh(_snapshot(70))
    source = UsageSource("刷新错误", "error", True, "test")
    failure = empty_snapshot(source, datetime.now(timezone.utc), "network failed")

    window._finish_refresh(failure)
    assert window.five_line.percent.text() == "70%"
    assert window.timer.interval() == 60_000

    window._finish_refresh(failure)
    assert window.timer.interval() == 120_000
    window._failure_started = datetime.now(timezone.utc) - timedelta(minutes=2, seconds=5)
    window._update_failure_status()
    assert "已持续 2 分钟" in window.status_label.text()
    assert app is not None
    window.shutdown()
    window.close()


def test_source_mode_disables_start_on_login_control():
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings_store=Store(), auto_refresh=False)

    assert window.startup_check.isEnabled() is False
    assert "仅支持打包" in window.startup_check.toolTip()
    assert app is not None
    window.shutdown()
    window.close()

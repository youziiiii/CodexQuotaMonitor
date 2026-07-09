from PySide6.QtWidgets import QApplication

from codex_quota_monitor.config.settings import AppSettings
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

    window.tray.icon.hide()
    window.close()

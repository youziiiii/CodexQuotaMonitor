from PySide6.QtWidgets import QApplication

from codex_quota_monitor.config.settings import AppSettings
from codex_quota_monitor.ui.main_window import MainWindow


class Store:
    def load(self):
        return AppSettings(provider="mock", notifications_enabled=False)

    def save(self, settings):
        pass


def test_settings_panel_collapses_window_back_to_content_height():
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings_store=Store(), auto_refresh=False)
    window.show()
    app.processEvents()
    collapsed_height = window.height()

    window.toggle_settings()
    app.processEvents()
    expanded_height = window.height()
    window.toggle_settings()
    app.processEvents()

    assert expanded_height > collapsed_height
    assert window.settings_panel.isHidden()
    assert window.height() == collapsed_height
    window.shutdown()
    window.close()

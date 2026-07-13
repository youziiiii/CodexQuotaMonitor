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


def test_settings_panel_shrinks_when_expanded_minimum_height_is_stale():
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings_store=Store(), auto_refresh=False)
    window.show()
    app.processEvents()
    collapsed_height = window.height()

    window.toggle_settings()
    app.processEvents()
    assert window.height() > collapsed_height

    window.toggle_settings()
    window._resize_to_content()

    assert window.settings_panel.isHidden()
    assert window.height() == collapsed_height
    window.shutdown()
    window.close()


def test_reset_details_collapse_and_restore_window_height():
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings_store=Store(), auto_refresh=False)
    window.show()
    app.processEvents()
    expanded_height = window.height()

    window.reset_panel.toggle_button.click()
    app.processEvents()
    collapsed_height = window.height()

    assert window.reset_panel.is_expanded is False
    assert collapsed_height < expanded_height

    window.reset_panel.toggle_button.click()
    app.processEvents()
    assert window.reset_panel.is_expanded is True
    assert window.height() == expanded_height
    window.shutdown()
    window.close()

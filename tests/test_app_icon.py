from pathlib import Path

from PySide6.QtWidgets import QApplication

from codex_quota_monitor.config.settings import AppSettings
from codex_quota_monitor.ui.main_window import MainWindow
from codex_quota_monitor.ui.tray import APP_ICON_PATH, create_app_icon


class Store:
    def load(self):
        return AppSettings(provider="mock", notifications_enabled=False, low_quota_alerts_enabled=False)


def test_app_icon_asset_exists_for_packaging():
    assert APP_ICON_PATH.exists()
    assert APP_ICON_PATH.name == "app_icon.ico"


def test_create_app_icon_returns_non_empty_icon():
    app = QApplication.instance() or QApplication([])

    assert app is not None
    assert create_app_icon().isNull() is False


def test_main_window_sets_titlebar_icon():
    app = QApplication.instance() or QApplication([])
    window = MainWindow(settings_store=Store(), auto_refresh=False)

    assert app is not None
    assert window.windowIcon().isNull() is False

    window.shutdown()
    window.close()


def test_build_script_uses_packaged_app_icon():
    script = Path("build_exe.ps1").read_text(encoding="utf-8")

    assert "--icon" in script
    assert "assets/app_icon.ico" in script

from datetime import datetime, timezone

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QStyle
from PySide6.QtWidgets import QWidget

from codex_quota_monitor.core.models import UsageSnapshot, UsageSource, UsageWindow
from codex_quota_monitor.ui.tray import QuotaPopup, TrayController, _quota_icon_text


def _snapshot() -> UsageSnapshot:
    now = datetime(2026, 7, 7, 18, 0, tzinfo=timezone.utc)
    return UsageSnapshot(
        source=UsageSource(
            name="ChatGPT Codex 实时额度",
            kind="chatgpt_realtime",
            is_estimate=False,
            detail="test",
        ),
        total_used_units=44,
        five_hour=UsageWindow("5 小时", 39, 100, 61, now),
        weekly=UsageWindow("1 周", 32, 100, 68, datetime(2026, 7, 14, 18, 0, tzinfo=timezone.utc)),
        last_refresh=now,
        metadata={"available_resets": "2"},
    )


def test_quota_popup_shows_five_hour_remaining_and_reset_time():
    app = QApplication.instance() or QApplication([])
    popup = QuotaPopup()

    popup.update_snapshot(_snapshot())

    assert app is not None
    assert popup.title_label.text() == "5 小时剩余"
    assert popup.percent_label.text() == "61%"
    assert popup.refresh_label.text().startswith("刷新时间 ")
    assert "--" not in popup.refresh_label.text()


def test_quota_popup_shows_weekly_remaining_and_weekly_reset_date_time():
    app = QApplication.instance() or QApplication([])
    popup = QuotaPopup()

    popup.update_snapshot(_snapshot())

    assert app is not None
    assert popup.week_percent_label.text() == "本周剩余 68%"
    assert popup.week_refresh_label.text().startswith("周刷新 ")
    assert "7月" in popup.week_refresh_label.text()
    assert "02:00" in popup.week_refresh_label.text()


def test_tray_icon_text_is_only_five_hour_remaining_number():
    assert _quota_icon_text(None) == "--"
    assert _quota_icon_text(67) == "67"
    assert _quota_icon_text(100) == "100"


def test_quota_popup_hides_when_window_deactivates():
    app = QApplication.instance() or QApplication([])
    popup = QuotaPopup()
    popup.show()
    app.processEvents()

    QApplication.sendEvent(popup, QEvent(QEvent.Type.WindowDeactivate))

    assert popup.isVisible() is False


def test_quota_popup_refresh_button_triggers_callback():
    app = QApplication.instance() or QApplication([])
    calls = []
    popup = QuotaPopup(on_refresh=lambda: calls.append("refresh"))

    popup.refresh_button.click()

    assert app is not None
    assert calls == ["refresh"]


def test_tray_tooltip_uses_percentages_for_realtime_windows():
    app = QApplication.instance() or QApplication([])

    class Window(QWidget):
        def refresh_now(self):
            pass

    window = Window()
    tray = TrayController(window)

    tray.update_snapshot(_snapshot())

    assert app is not None
    assert "5 小时剩余：61%" in tray.icon.toolTip()
    assert "本周剩余：68%" in tray.icon.toolTip()


def test_tray_icon_is_not_the_system_computer_icon():
    app = QApplication.instance() or QApplication([])

    class Window(QWidget):
        def refresh_now(self):
            pass

    tray = TrayController(Window())
    system_icon_key = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon).cacheKey()

    assert tray.icon.icon().cacheKey() != system_icon_key


def test_tray_icon_updates_when_snapshot_changes():
    app = QApplication.instance() or QApplication([])

    class Window(QWidget):
        def refresh_now(self):
            pass

    tray = TrayController(Window())
    before = tray.icon.icon().cacheKey()

    tray.update_snapshot(_snapshot())

    assert app is not None
    assert tray.icon.icon().cacheKey() != before


def test_tray_controller_hides_popup_when_clicking_outside_popup():
    app = QApplication.instance() or QApplication([])

    class Window(QWidget):
        def refresh_now(self):
            pass

    outside = QWidget()
    tray = TrayController(Window())
    tray.popup.show()
    app.processEvents()

    click = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(1, 1),
        QPointF(1, 1),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    tray.eventFilter(outside, click)

    assert tray.popup.isVisible() is False

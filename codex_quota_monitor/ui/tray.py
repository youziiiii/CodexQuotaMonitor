from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
)

from codex_quota_monitor.core.models import UsageSnapshot


APP_ICON_PATH = Path(__file__).resolve().parents[2] / "assets" / "app_icon.ico"


def _format_reset_clock(snapshot: UsageSnapshot) -> str:
    value = snapshot.five_hour.reset_time
    if value is None:
        return "--:--"
    return value.astimezone().strftime("%H:%M")


def _format_reset_date_time(value) -> str:
    if value is None:
        return "--"
    local = value.astimezone()
    return f"{local.month}月{local.day}日 {local.strftime('%H:%M')}"


def _quota_color(percent: int | None) -> QColor:
    if percent is None:
        return QColor("#7ee787")
    if percent < 10:
        return QColor("#ff5c5c")
    if percent < 20:
        return QColor("#f6c453")
    return QColor("#7ee787")


def create_app_icon() -> QIcon:
    if APP_ICON_PATH.exists():
        icon = QIcon(str(APP_ICON_PATH))
        if not icon.isNull():
            return icon

    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#4a4d55"), 2))
    painter.setBrush(QColor("#24262b"))
    painter.drawRoundedRect(QRectF(3, 3, 58, 58), 13, 13)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#7ee787"))
    painter.drawRoundedRect(QRectF(10, 10, 9, 44), 4, 4)
    painter.setPen(QColor("#f5f5f6"))
    font = QFont("Segoe UI", 27)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "C")
    painter.end()
    return QIcon(pixmap)


def _quota_icon_text(percent: int | None) -> str:
    if percent is None:
        return "--"
    return str(max(0, min(100, percent)))


def create_quota_icon(percent: int | None = None) -> QIcon:
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    accent = _quota_color(percent)
    text = _quota_icon_text(percent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#4a4d55"), 2))
    painter.setBrush(QColor("#24262b"))
    painter.drawRoundedRect(QRectF(3, 3, 58, 58), 13, 13)

    painter.setPen(accent)
    font_size = 25 if len(text) <= 2 else 19
    font = QFont("Segoe UI", font_size)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return QIcon(pixmap)


class QuotaPopup(QFrame):
    def __init__(self, on_refresh=None) -> None:
        super().__init__(None)
        self.on_refresh = on_refresh
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setObjectName("quotaPopup")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self.title_label = QLabel("5 小时剩余")
        self.title_label.setObjectName("popupTitle")
        self.percent_label = QLabel("--%")
        self.percent_label.setObjectName("popupPercent")
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        top.addWidget(self.title_label)
        top.addWidget(self.percent_label, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setObjectName("popupProgress")

        self.refresh_label = QLabel("刷新时间 --:--")
        self.refresh_label.setObjectName("popupRefresh")

        self.week_percent_label = QLabel("本周剩余 --%")
        self.week_percent_label.setObjectName("popupWeek")

        self.week_refresh_label = QLabel("周刷新 --")
        self.week_refresh_label.setObjectName("popupWeek")

        self.refresh_button = QPushButton("立即刷新")
        self.refresh_button.setObjectName("popupRefreshButton")
        self.refresh_button.clicked.connect(self._refresh_clicked)

        layout.addLayout(top)
        layout.addWidget(self.progress)
        layout.addWidget(self.refresh_label)
        layout.addWidget(self.week_percent_label)
        layout.addWidget(self.week_refresh_label)
        layout.addWidget(self.refresh_button)
        self._apply_styles()

    def update_snapshot(self, snapshot: UsageSnapshot) -> None:
        percent = snapshot.five_hour.percent_remaining
        self.percent_label.setText(f"{percent}%")
        self.progress.setValue(percent)
        self.refresh_label.setText(f"刷新时间 {_format_reset_clock(snapshot)}")
        self.week_percent_label.setText(f"本周剩余 {snapshot.weekly.percent_remaining}%")
        self.week_refresh_label.setText(f"周刷新 {_format_reset_date_time(snapshot.weekly.reset_time)}")
        state = "normal"
        if percent < 10:
            state = "critical"
        elif percent < 20:
            state = "warning"
        for widget in (self.percent_label, self.progress):
            widget.setProperty("quotaState", state)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            #quotaPopup {
                background: #292a2d;
                border: 1px solid #4a4d55;
                border-radius: 8px;
                color: #f5f5f6;
                font-family: "Microsoft YaHei UI", "Segoe UI";
                min-width: 210px;
            }
            #popupTitle {
                color: #f5f5f6;
                font-size: 10.5pt;
                font-weight: 700;
            }
            #popupPercent {
                color: #7ee787;
                font-size: 12pt;
                font-weight: 800;
                min-width: 54px;
            }
            #popupPercent[quotaState="warning"] { color: #f6c453; }
            #popupPercent[quotaState="critical"] { color: #ff5c5c; }
            #popupRefresh {
                color: #b8bcc6;
                font-size: 9pt;
            }
            #popupWeek {
                color: #d6dae3;
                font-size: 9pt;
            }
            #popupRefreshButton {
                background: #34363a;
                border: 1px solid #4b5563;
                border-radius: 6px;
                color: #f4f4f5;
                padding: 5px 8px;
                font-size: 9pt;
            }
            #popupRefreshButton:hover { background: #40434a; }
            #popupProgress {
                height: 6px;
                border: none;
                border-radius: 3px;
                background: #3a3d45;
            }
            #popupProgress::chunk {
                border-radius: 3px;
                background: #7ee787;
            }
            #popupProgress[quotaState="warning"]::chunk { background: #f6c453; }
            #popupProgress[quotaState="critical"]::chunk { background: #ff5c5c; }
            """
        )

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.WindowDeactivate:
            self.hide()
        return super().event(event)

    def _refresh_clicked(self) -> None:
        if self.on_refresh is not None:
            self.on_refresh()


class TrayController(QObject):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.window = window
        app = QApplication.instance()
        self.app = app
        self.icon = QSystemTrayIcon(create_quota_icon(), window)
        self.popup = QuotaPopup(on_refresh=window.refresh_now)
        menu = QMenu()
        show_action = QAction("显示主窗口", menu)
        show_action.triggered.connect(self._show_window)
        refresh_action = QAction("立即刷新", menu)
        refresh_action.triggered.connect(window.refresh_now)
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(app.quit)
        menu.addAction(show_action)
        menu.addAction(refresh_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(self._activated)
        self.icon.show()
        self.app.installEventFilter(self)

    def update_snapshot(self, snapshot: UsageSnapshot) -> None:
        self.popup.update_snapshot(snapshot)
        self.icon.setIcon(create_quota_icon(snapshot.five_hour.percent_remaining))
        reset_clock = _format_reset_clock(snapshot)
        self.icon.setToolTip(
            "Codex 实时额度\n"
            f"5 小时剩余：{snapshot.five_hour.percent_remaining}%\n"
            f"刷新时间：{reset_clock}\n"
            f"本周剩余：{snapshot.weekly.percent_remaining}%"
        )

    def _activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_popup()

    def _toggle_popup(self) -> None:
        if self.popup.isVisible():
            self.popup.hide()
            return
        self._position_popup()
        self.popup.show()
        self.popup.raise_()

    def _position_popup(self) -> None:
        self.popup.adjustSize()
        pos = QCursor.pos()
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        if screen is None:
            self.popup.move(pos)
            return
        rect = screen.availableGeometry()
        width = self.popup.width()
        height = self.popup.height()
        x = min(max(pos.x() - width + 24, rect.left()), rect.right() - width)
        y = min(max(pos.y() - height - 12, rect.top()), rect.bottom() - height)
        self.popup.move(x, y)

    def _show_window(self) -> None:
        self.popup.hide()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def eventFilter(self, obj, event) -> bool:
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and self.popup.isVisible()
            and obj is not self.popup
            and not self.popup.isAncestorOf(obj)
        ):
            self.popup.hide()
        return False

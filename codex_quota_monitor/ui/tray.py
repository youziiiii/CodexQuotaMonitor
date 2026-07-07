from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QApplication, QStyle

from codex_quota_monitor.core.models import UsageSnapshot
from codex_quota_monitor.ui.widgets import format_units


class TrayController:
    def __init__(self, window) -> None:
        self.window = window
        app = QApplication.instance()
        icon = app.style().standardIcon(QStyle.SP_ComputerIcon)
        self.icon = QSystemTrayIcon(icon, window)
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

    def update_snapshot(self, snapshot: UsageSnapshot) -> None:
        self.icon.setToolTip(
            "Codex 实时额度\n"
            f"5 小时剩余：{format_units(snapshot.five_hour.remaining_units)}\n"
            f"本周剩余：{format_units(snapshot.weekly.remaining_units)}"
        )

    def _activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_window()

    def _show_window(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

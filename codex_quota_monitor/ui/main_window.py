from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from codex_quota_monitor.config.credentials import CredentialStore
from codex_quota_monitor.config.settings import AppSettings, SettingsStore
from codex_quota_monitor.config.startup import set_start_on_login
from codex_quota_monitor.core.models import UsageSnapshot
from codex_quota_monitor.core.refresh import RefreshService
from codex_quota_monitor.data_sources.chatgpt_wham import ChatGPTWhamUsageProvider
from codex_quota_monitor.data_sources.mock_provider import MockUsageProvider
from codex_quota_monitor.notifications.notifier import Notifier
from codex_quota_monitor.ui.tray import TrayController, create_app_icon


def _fmt_clock(value) -> str:
    if value is None:
        return "--:--"
    return value.astimezone().strftime("%H:%M")


def _fmt_date(value) -> str:
    if value is None:
        return "--"
    local = value.astimezone()
    return f"{local.month}月{local.day}日"


class UsageLine(QWidget):
    def __init__(self, label: str) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(label)
        self.label.setObjectName("usageLabel")
        self.percent = QLabel("--%")
        self.percent.setObjectName("usagePercent")
        self.reset = QLabel("--")
        self.reset.setObjectName("usageReset")
        layout.addWidget(self.label, 1)
        layout.addWidget(self.percent)
        layout.addWidget(self.reset)

    def update_values(self, percent_remaining: int, reset_text: str) -> None:
        self.percent.setText(f"{percent_remaining}%")
        self.reset.setText(reset_text)
        state = "normal"
        if percent_remaining < 10:
            state = "critical"
        elif percent_remaining < 20:
            state = "warning"
        self.percent.setProperty("quotaState", state)
        self.percent.style().unpolish(self.percent)
        self.percent.style().polish(self.percent)


class ActionLine(QFrame):
    def __init__(self, text: str, right_text: str = "", emphasis: bool = False) -> None:
        super().__init__()
        self.left_text = text
        self.right_text = right_text
        self.setObjectName("actionLine")
        if emphasis:
            self.setProperty("emphasis", "true")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(26, 7, 6, 7)
        layout.setSpacing(6)
        self.left_label = QLabel(text)
        self.left_label.setObjectName("actionLineText")
        self.right_label = QLabel("")
        self.right_label.setObjectName("actionLineText")
        layout.addWidget(self.left_label)
        layout.addWidget(self.right_label)
        layout.addStretch(1)
        self._render()

    def set_right_text(self, value: str) -> None:
        self.right_text = value
        self._render()

    def text(self) -> str:
        suffix = f"  {self.right_label.text()}" if self.right_label.text() else ""
        return f"{self.left_label.text()}{suffix}"

    def _render(self) -> None:
        self.left_label.setText(self.left_text)
        self.right_label.setText(self.right_text.replace("›", "").strip())


class RefreshTaskSignals(QObject):
    finished = Signal(object)


class RefreshTask(QRunnable):
    def __init__(self, service: RefreshService) -> None:
        super().__init__()
        self.service = service
        self.signals = RefreshTaskSignals()

    def run(self) -> None:
        self.signals.finished.emit(self.service.refresh())


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings_store: SettingsStore | None = None,
        thread_pool: QThreadPool | None = None,
        auto_refresh: bool = True,
    ) -> None:
        super().__init__()
        self.settings_store = settings_store or SettingsStore()
        self.credential_store = CredentialStore()
        self.settings = self.settings_store.load()
        self.service = RefreshService(self._make_provider())
        self.thread_pool = thread_pool or QThreadPool.globalInstance()
        self.refresh_in_progress = False
        self._refresh_tasks: list[RefreshTask] = []
        self.setWindowTitle("Codex 剩余用量")
        self.setWindowIcon(create_app_icon())
        self.setFixedWidth(445)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_now)
        self._build_ui()
        self.tray = TrayController(self)
        self.notifier = Notifier(self.tray.icon)
        self._apply_styles()
        self._apply_timer()
        if auto_refresh:
            self.refresh_now()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        panel = QFrame()
        panel.setObjectName("quotaPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 12, 14, 12)
        panel_layout.setSpacing(10)

        header = QHBoxLayout()
        title_icon = QLabel("◉")
        title_icon.setObjectName("titleIcon")
        title = QLabel("剩余用量")
        title.setObjectName("title")
        self.collapse_button = QPushButton("⌄")
        self.collapse_button.setObjectName("iconButton")
        self.collapse_button.clicked.connect(self.toggle_settings)
        header.addWidget(title_icon)
        header.addWidget(title, 1)
        header.addWidget(self.collapse_button)
        panel_layout.addLayout(header)

        self.five_line = UsageLine("5 小时")
        self.week_line = UsageLine("1 周")
        panel_layout.addWidget(self.five_line)
        panel_layout.addWidget(self.week_line)

        self.source_label = QLabel("实时数据 · ChatGPT/Codex 额度")
        self.source_label.setObjectName("sourceLabel")
        panel_layout.addWidget(self.source_label)

        self.reset_line = ActionLine("可用重置", "0 次")
        panel_layout.addWidget(self.reset_line)

        layout.addWidget(panel)

        self.settings_panel = self._build_settings_panel()
        layout.addWidget(self.settings_panel)
        self.settings_panel.hide()

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.setCentralWidget(root)

    def _build_settings_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("settingsPanel")
        layout = QFormLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("实时额度", "realtime")
        self.provider_combo.addItem("Mock 演示数据", "mock")
        self.provider_combo.setCurrentIndex(0 if self.settings.provider == "realtime" else 1)

        self.interval_combo = QComboBox()
        for label, seconds in [("30 秒", 30), ("60 秒", 60), ("5 分钟", 300), ("15 分钟", 900)]:
            self.interval_combo.addItem(label, seconds)
        idx = self.interval_combo.findData(self.settings.refresh_interval_seconds)
        self.interval_combo.setCurrentIndex(max(0, idx))

        self.startup_check = QCheckBox("开机自启动")
        self.startup_check.setChecked(self.settings.start_on_login)
        self.low_alert_check = QCheckBox("低余量提醒")
        self.low_alert_check.setChecked(self.settings.low_quota_alerts_enabled)
        self.notifications_check = QCheckBox("系统通知")
        self.notifications_check.setChecked(self.settings.notifications_enabled)

        layout.addRow("数据源", self.provider_combo)
        layout.addRow("刷新间隔", self.interval_combo)
        layout.addRow("", self.startup_check)
        layout.addRow("", self.low_alert_check)
        layout.addRow("", self.notifications_check)
        save_button = QPushButton("保存并刷新")
        save_button.clicked.connect(self.save_settings)
        layout.addRow("", save_button)
        return panel

    def _make_provider(self):
        if self.settings.provider == "mock":
            return MockUsageProvider()
        return ChatGPTWhamUsageProvider(auth_path=self.settings.auth_json_path)

    def _apply_timer(self) -> None:
        self.timer.stop()
        self.timer.start(self.settings.refresh_interval_seconds * 1000)

    def toggle_settings(self) -> None:
        visible = not self.settings_panel.isVisible()
        self.settings_panel.setVisible(visible)
        self.collapse_button.setText("⌃" if visible else "⌄")

    def refresh_now(self) -> None:
        if self.refresh_in_progress:
            return
        self.refresh_in_progress = True
        if self.status_label.text() == "":
            self.status_label.setText("正在刷新...")
        task = RefreshTask(self.service)
        self._refresh_tasks.append(task)
        task.signals.finished.connect(lambda snapshot, finished_task=task: self._finish_refresh(snapshot, finished_task))
        self.thread_pool.start(task)

    def _finish_refresh(self, snapshot: UsageSnapshot, task: RefreshTask | None = None) -> None:
        self.refresh_in_progress = False
        if task in self._refresh_tasks:
            self._refresh_tasks.remove(task)
        self._render_snapshot(snapshot)
        self.tray.update_snapshot(snapshot)
        if snapshot.error_message:
            self.notifier.alert_error(snapshot, self.settings.notifications_enabled)
        else:
            self.notifier.maybe_alert_low_quota(snapshot, self.settings.low_quota_alerts_enabled)

    def _render_snapshot(self, snapshot: UsageSnapshot) -> None:
        self.five_line.update_values(snapshot.five_hour.percent_remaining, _fmt_clock(snapshot.five_hour.reset_time))
        self.week_line.update_values(snapshot.weekly.percent_remaining, _fmt_date(snapshot.weekly.reset_time))
        resets = snapshot.metadata.get("available_resets", "0")
        self.reset_line.set_right_text(f"{resets} 次")
        source_prefix = "实时数据" if not snapshot.source.is_estimate else "演示数据"
        self.source_label.setText(f"{source_prefix} · {snapshot.metadata.get('unit', '使用量')}")
        if snapshot.error_message:
            self.status_label.setText(snapshot.error_message)
        else:
            self.status_label.setText("")

    def save_settings(self) -> None:
        self.settings = AppSettings(
            refresh_interval_seconds=int(self.interval_combo.currentData()),
            provider=str(self.provider_combo.currentData()),
            notifications_enabled=self.notifications_check.isChecked(),
            notify_on_refresh=False,
            start_on_login=self.startup_check.isChecked(),
            low_quota_alerts_enabled=self.low_alert_check.isChecked(),
            auth_json_path=self.settings.auth_json_path,
            five_hour_limit=self.settings.five_hour_limit,
            weekly_limit=self.settings.weekly_limit,
            account_display_name=self.settings.account_display_name,
            account_plan=self.settings.account_plan,
            avatar_number=self.settings.avatar_number,
        )
        self.settings_store.save(self.settings)
        set_start_on_login(self.settings.start_on_login)
        self.service = RefreshService(self._make_provider())
        self._apply_timer()
        self.refresh_now()

    def closeEvent(self, event) -> None:
        if self.tray.icon.isVisible():
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            #root { background: #101623; color: #f4f4f5; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 10.5pt; }
            #quotaPanel { background: #2a2a2b; border: 1px solid #3a3a3c; border-radius: 14px; }
            #title { font-size: 13pt; font-weight: 700; color: #ffffff; }
            #titleIcon { color: #c8c8c8; font-size: 12pt; }
            #iconButton { background: transparent; border: none; color: #9ca3af; font-size: 15pt; padding: 2px 6px; }
            #usageLabel { color: #ffffff; font-size: 12pt; font-weight: 700; padding-left: 26px; }
            #usagePercent { color: #a1a1aa; min-width: 56px; qproperty-alignment: AlignRight; }
            #usagePercent[quotaState="warning"] { color: #f6c453; font-weight: 700; }
            #usagePercent[quotaState="critical"] { color: #ff5c5c; font-weight: 800; }
            #usageReset { color: #a1a1aa; min-width: 58px; qproperty-alignment: AlignRight; }
            #sourceLabel { color: #737373; padding-left: 2px; }
            #actionLine { background: transparent; border: none; color: #f3f4f6; font-weight: 600; }
            #actionLineText { color: #f3f4f6; font-weight: 600; }
            #actionLine[emphasis="true"] { color: #ffffff; }
            #settingsPanel { background: #202124; border: 1px solid #34363a; border-radius: 10px; color: #f4f4f5; }
            #statusLabel { color: #8f96a3; padding: 0 4px; }
            QLineEdit, QComboBox, QSpinBox { background: #111318; color: #f4f4f5; border: 1px solid #3b3f46; border-radius: 6px; padding: 5px; }
            QCheckBox { color: #e5e7eb; }
            QPushButton { background: #34363a; color: #f4f4f5; border: 1px solid #4b5563; border-radius: 7px; padding: 7px 10px; }
            QPushButton:hover { background: #40434a; }
            """
        )


def run_app() -> int:
    app = QApplication([])
    app.setWindowIcon(create_app_icon())
    QApplication.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    return app.exec()

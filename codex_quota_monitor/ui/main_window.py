from __future__ import annotations

from datetime import datetime, timezone

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

from codex_quota_monitor.config.settings import AppSettings, SettingsStore
from codex_quota_monitor.config.startup import is_packaged_app, set_start_on_login
from codex_quota_monitor.core.models import UsageSnapshot
from codex_quota_monitor.core.refresh import RefreshService
from codex_quota_monitor.core.security import redact_secret
from codex_quota_monitor.core.single_instance import SingleInstance
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
        self.percent = QLabel("--")
        self.percent.setObjectName("usagePercent")
        self.reset = QLabel("--")
        self.reset.setObjectName("usageReset")
        layout.addWidget(self.label, 1)
        layout.addWidget(self.percent)
        layout.addWidget(self.reset)

    def update_values(self, percent_remaining: int | None, reset_text: str) -> None:
        self.percent.setText("--" if percent_remaining is None else f"{percent_remaining}%")
        self.reset.setText(reset_text)
        state = "unknown" if percent_remaining is None else "normal"
        if percent_remaining is not None and percent_remaining < 10:
            state = "critical"
        elif percent_remaining is not None and percent_remaining < 20:
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
    def __init__(self, service: RefreshService, generation: int) -> None:
        super().__init__()
        self.service = service
        self.generation = generation
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
        self.settings = self.settings_store.load()
        self.service = RefreshService(self._make_provider())
        self._owns_thread_pool = thread_pool is None
        self.thread_pool = thread_pool or QThreadPool(self)
        self.refresh_in_progress = False
        self._refresh_tasks: list[RefreshTask] = []
        self._provider_generation = 0
        self._pending_refresh = False
        self._last_success_snapshot: UsageSnapshot | None = None
        self._failure_started: datetime | None = None
        self._failure_message: str | None = None
        self._failure_count = 0
        self._shutting_down = False
        self.setWindowTitle("Codex 剩余用量")
        self.setWindowIcon(create_app_icon())
        self.setFixedWidth(445)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._auto_refresh)
        self.failure_status_timer = QTimer(self)
        self.failure_status_timer.setInterval(1000)
        self.failure_status_timer.timeout.connect(self._update_failure_status)
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

        self.reset_line = ActionLine("可用重置", "--")
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
        packaged = is_packaged_app()
        self.startup_check.setChecked(self.settings.start_on_login if packaged else False)
        self.startup_check.setEnabled(packaged)
        if not packaged:
            self.startup_check.setToolTip("开机自启动仅支持打包后的 CodexQuotaMonitor.exe")
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
        self.timer.setInterval(self.settings.refresh_interval_seconds * 1000)

    def _schedule_next_refresh(self, delay_seconds: int | None = None) -> None:
        if self._shutting_down:
            return
        delay = delay_seconds or self.settings.refresh_interval_seconds
        self.timer.start(delay * 1000)

    def _auto_refresh(self) -> None:
        self._request_refresh(manual=False)

    def toggle_settings(self) -> None:
        visible = not self.settings_panel.isVisible()
        self.settings_panel.setVisible(visible)
        self.collapse_button.setText("⌃" if visible else "⌄")
        QTimer.singleShot(0, self._resize_to_content)

    def _resize_to_content(self) -> None:
        layout = self.centralWidget().layout()
        if layout is not None:
            layout.activate()
        self.resize(self.width(), self.sizeHint().height())

    def refresh_now(self) -> None:
        self._request_refresh(manual=True)

    def _request_refresh(self, manual: bool) -> None:
        if self._shutting_down:
            return
        if manual:
            self.timer.stop()
        if self.refresh_in_progress:
            if manual:
                self._pending_refresh = True
            return
        self._start_refresh()

    def _start_refresh(self) -> None:
        self.refresh_in_progress = True
        if self._last_success_snapshot is None and self._failure_started is None:
            self.status_label.setText("正在刷新...")
        task = RefreshTask(self.service, self._provider_generation)
        self._refresh_tasks.append(task)
        task.signals.finished.connect(lambda snapshot, finished_task=task: self._finish_refresh(snapshot, finished_task))
        self.thread_pool.start(task)

    def _finish_refresh(self, snapshot: UsageSnapshot, task: RefreshTask | None = None) -> None:
        self.refresh_in_progress = False
        if task in self._refresh_tasks:
            self._refresh_tasks.remove(task)
        if self._shutting_down:
            return
        if task is not None and task.generation != self._provider_generation:
            self._run_pending_refresh()
            return

        if snapshot.error_message:
            self._failure_count += 1
            if self._failure_started is None:
                self._failure_started = datetime.now(timezone.utc)
                self.failure_status_timer.start()
            self._failure_message = snapshot.error_message
            if self._last_success_snapshot is None:
                self._render_snapshot(snapshot)
                self.tray.update_snapshot(snapshot)
            self._update_failure_status()
            self.notifier.alert_error(snapshot, self.settings.notifications_enabled)
            retry_delay = min(
                self.settings.refresh_interval_seconds * (2 ** min(max(0, self._failure_count - 1), 5)),
                900,
            )
        else:
            self._last_success_snapshot = snapshot
            self._failure_started = None
            self._failure_message = None
            self._failure_count = 0
            self.failure_status_timer.stop()
            self.notifier.clear_error()
            self._render_snapshot(snapshot)
            self.tray.update_snapshot(snapshot)
            self.tray.set_status(snapshot.warning_message or "", error=False)
            self.notifier.maybe_alert_low_quota(snapshot, self.settings.low_quota_alerts_enabled)
            retry_delay = self.settings.refresh_interval_seconds

        if self._pending_refresh:
            self._run_pending_refresh()
        else:
            self._schedule_next_refresh(retry_delay)

    def _run_pending_refresh(self) -> None:
        self._pending_refresh = False
        self.timer.stop()
        self._start_refresh()

    def _render_snapshot(self, snapshot: UsageSnapshot) -> None:
        self.five_line.update_values(snapshot.five_hour.percent_remaining, _fmt_clock(snapshot.five_hour.reset_time))
        self.week_line.update_values(snapshot.weekly.percent_remaining, _fmt_date(snapshot.weekly.reset_time))
        resets = snapshot.metadata.get("available_resets", "--")
        self.reset_line.set_right_text("--" if resets == "--" else f"{resets} 次")
        if snapshot.error_message:
            source_prefix = "数据不可用"
        else:
            source_prefix = "实时数据" if not snapshot.source.is_estimate else "演示数据"
        self.source_label.setText(f"{source_prefix} · {snapshot.metadata.get('unit', '使用量')}")
        if snapshot.error_message:
            self.status_label.setText(snapshot.error_message)
        elif snapshot.warning_message:
            self.status_label.setText(snapshot.warning_message)
        else:
            self.status_label.setText("")

    def _update_failure_status(self) -> None:
        if self._failure_started is None or self._failure_message is None:
            return
        elapsed = max(0, int((datetime.now(timezone.utc) - self._failure_started).total_seconds()))
        if elapsed < 60:
            duration = f"{elapsed} 秒"
        elif elapsed < 3600:
            duration = f"{elapsed // 60} 分钟"
        else:
            duration = f"{elapsed // 3600} 小时 {(elapsed % 3600) // 60} 分钟"
        message = f"刷新失败，已持续 {duration}：{self._failure_message}"
        self.status_label.setText(message)
        self.tray.set_status(message, error=True)

    def save_settings(self) -> None:
        new_settings = AppSettings(
            refresh_interval_seconds=int(self.interval_combo.currentData()),
            provider=str(self.provider_combo.currentData()),
            notifications_enabled=self.notifications_check.isChecked(),
            start_on_login=self.startup_check.isEnabled() and self.startup_check.isChecked(),
            low_quota_alerts_enabled=self.low_alert_check.isChecked(),
            auth_json_path=self.settings.auth_json_path,
        )
        try:
            set_start_on_login(new_settings.start_on_login)
            self.settings_store.save(new_settings)
        except (OSError, RuntimeError) as exc:
            self.status_label.setText(f"设置保存失败：{redact_secret(exc)}")
            return
        self.settings = new_settings
        self._provider_generation += 1
        self.service = RefreshService(self._make_provider())
        self._apply_timer()
        self._pending_refresh = True
        if not self.refresh_in_progress:
            self._run_pending_refresh()

    def quit_app(self) -> None:
        self.shutdown()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self.timer.stop()
        self.failure_status_timer.stop()
        self._pending_refresh = False
        for task in self._refresh_tasks:
            try:
                task.signals.finished.disconnect()
            except RuntimeError:
                pass
        if self._owns_thread_pool:
            self.thread_pool.clear()
            self.thread_pool.waitForDone(1000)
        self.tray.shutdown()

    def closeEvent(self, event) -> None:
        if not self._shutting_down and self.tray.icon.isVisible():
            event.ignore()
            self.hide()
        else:
            self.shutdown()
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
            #usagePercent[quotaState="unknown"] { color: #a1a1aa; }
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
    app.setApplicationName("CodexQuotaMonitor")
    app.setWindowIcon(create_app_icon())
    QApplication.setQuitOnLastWindowClosed(False)
    instance = SingleInstance()
    if not instance.acquire():
        return 0
    window = MainWindow()
    instance.activation_requested.connect(window.tray.show_window)

    def cleanup() -> None:
        window.shutdown()
        instance.shutdown()

    app.aboutToQuit.connect(cleanup)
    window.show()
    return app.exec()

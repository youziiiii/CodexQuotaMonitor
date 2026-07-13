from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal
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
    QToolButton,
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
from codex_quota_monitor.ui.usage_widgets import ResetCreditsPanel, UsageLimitRow


def _fmt_clock(value) -> str | None:
    if value is None:
        return None
    return value.astimezone().strftime("%H:%M")


def _fmt_date(value) -> str | None:
    if value is None:
        return None
    local = value.astimezone()
    return f"{local.month}月{local.day}日"


def _parse_reset_count(value: object) -> int | None:
    try:
        count = int(str(value))
    except (TypeError, ValueError):
        return None
    return count if count >= 0 else None


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
        self.setFixedWidth(500)
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
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("使用量")
        title.setObjectName("pageTitle")
        self.collapse_button = QToolButton()
        self.collapse_button.setText("⚙︎")
        self.collapse_button.setObjectName("settingsButton")
        self.collapse_button.setToolTip("设置")
        self.collapse_button.clicked.connect(self.toggle_settings)
        header.addWidget(title, 1)
        header.addWidget(self.collapse_button)
        layout.addLayout(header)

        limits_panel = QFrame()
        limits_panel.setObjectName("limitsPanel")
        limits_layout = QVBoxLayout(limits_panel)
        limits_layout.setContentsMargins(0, 0, 0, 0)
        limits_layout.setSpacing(0)
        self.five_line = UsageLimitRow("5 小时使用限额")
        self.week_line = UsageLimitRow("每周使用限额")
        limits_layout.addWidget(self.five_line)
        limit_separator = QFrame()
        limit_separator.setObjectName("sectionSeparator")
        limit_separator.setFrameShape(QFrame.Shape.HLine)
        limit_separator.setFixedHeight(1)
        limits_layout.addWidget(limit_separator)
        limits_layout.addWidget(self.week_line)
        layout.addWidget(limits_panel)

        self.reset_panel = ResetCreditsPanel()
        self.reset_panel.expanded_changed.connect(
            lambda _: QTimer.singleShot(0, self._resize_to_content)
        )
        layout.addWidget(self.reset_panel)

        self.settings_panel = self._build_settings_panel()
        layout.addWidget(self.settings_panel)
        self.settings_panel.hide()

        self.source_label = QLabel("实时数据 · ChatGPT/Codex 额度")
        self.source_label.setObjectName("sourceLabel")
        self.source_label.hide()
        layout.addWidget(self.source_label)

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
        visible = self.settings_panel.isHidden()
        self.settings_panel.setVisible(visible)
        self.collapse_button.setToolTip("收起设置" if visible else "设置")
        QTimer.singleShot(0, self._resize_to_content)

    def _resize_to_content(self) -> None:
        layout = self.centralWidget().layout()
        target_height = self.sizeHint().height()
        if layout is not None:
            layout.invalidate()
            layout.activate()
            target_height = layout.sizeHint().height()

        # Qt can retain the expanded layout's minimum height for one event-loop
        # cycle after a child is hidden, causing the first shrink to be ignored.
        self.setMinimumHeight(target_height)
        self.resize(self.width(), target_height)

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
        self.five_line.setVisible(True)
        self.week_line.setVisible(True)
        self.five_line.update_values(
            snapshot.five_hour.percent_remaining,
            _fmt_clock(snapshot.five_hour.reset_time),
        )
        self.week_line.update_values(
            snapshot.weekly.percent_remaining,
            _fmt_date(snapshot.weekly.reset_time),
        )
        resets = _parse_reset_count(snapshot.metadata.get("available_resets"))
        self.reset_panel.update_credits(snapshot.reset_credits, resets)
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
        QTimer.singleShot(0, self._resize_to_content)

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
            #root {
                background: #202020;
                color: #f5f5f5;
                font-family: "Microsoft YaHei UI", "Segoe UI";
                font-size: 10.5pt;
            }
            #pageTitle { color: #ffffff; font-size: 18pt; font-weight: 700; }
            #settingsButton {
                background: transparent;
                border: none;
                color: #b8b8b8;
                font-family: "Segoe UI Symbol";
                font-size: 14pt;
                padding: 4px;
            }
            #settingsButton:hover { color: #ffffff; background: #303030; border-radius: 6px; }
            #limitsPanel, #resetPanel, #settingsPanel {
                background: #272727;
                border: 1px solid #3b3b3b;
                border-radius: 8px;
                color: #f5f5f5;
            }
            #limitTitle, #resetSectionTitle, #resetCreditTitle {
                color: #f7f7f7;
                font-weight: 700;
            }
            #limitReset, #resetCreditExpiry { color: #a7a7a7; }
            #limitPercent {
                color: #bdbdbd;
                min-width: 72px;
                font-weight: 500;
            }
            #limitPercent[quotaState="warning"] { color: #f6c453; font-weight: 700; }
            #limitPercent[quotaState="critical"] { color: #ff6868; font-weight: 700; }
            #limitProgress {
                background: #434343;
                border: none;
                border-radius: 4px;
            }
            #limitProgress::chunk { background: #f1f1f1; border-radius: 4px; }
            #limitProgress[quotaState="warning"]::chunk { background: #f6c453; }
            #limitProgress[quotaState="critical"]::chunk { background: #ff6868; }
            #sectionSeparator { background: #3a3a3a; border: none; }
            #resetBadge {
                background: #087a36;
                color: #e4ffed;
                border-radius: 10px;
                padding: 3px 10px;
                font-weight: 700;
            }
            #resetBadge[resetState="empty"], #resetBadge[resetState="unknown"] {
                background: #414141;
                color: #c8c8c8;
            }
            #resetToggleButton {
                background: transparent;
                border: none;
                color: #bdbdbd;
                padding: 3px;
            }
            #resetToggleButton:hover { color: #ffffff; background: #333333; border-radius: 5px; }
            #resetEmptyLabel { color: #8e8e8e; padding: 16px; }
            #sourceLabel { color: #777777; padding: 0 3px; }
            #statusLabel { color: #9ca3af; padding: 0 3px; }
            QLineEdit, QComboBox, QSpinBox {
                background: #171717;
                color: #f4f4f5;
                border: 1px solid #454545;
                border-radius: 6px;
                padding: 6px;
            }
            QCheckBox { color: #e5e7eb; }
            QPushButton {
                background: #353535;
                color: #f4f4f5;
                border: 1px solid #4a4a4a;
                border-radius: 7px;
                padding: 7px 10px;
            }
            QPushButton:hover { background: #414141; }
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

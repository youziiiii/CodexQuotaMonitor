from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from codex_quota_monitor.core.models import UsageWindow
from codex_quota_monitor.core.thresholds import quota_state


def format_units(value: int) -> str:
    return f"{value:,} 单位"


def format_time(value) -> str:
    if value is None:
        return "未知"
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "-") -> None:
        super().__init__()
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("cardValue")
        self.value_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class UsageBar(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.title_label = QLabel(title)
        self.value_label = QLabel("-")
        self.value_label.setAlignment(Qt.AlignRight)
        top.addWidget(self.title_label)
        top.addWidget(self.value_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addLayout(top)
        layout.addWidget(self.progress)

    def set_window(self, window: UsageWindow) -> None:
        self.value_label.setText(
            f"已用 {format_units(window.used_units)} / 剩余 {format_units(window.remaining_units)}"
        )
        self.progress.setValue(window.percent_used)
        state = quota_state(window.remaining_units, window.limit_units)
        self.progress.setProperty("quotaState", state)
        self.progress.style().unpolish(self.progress)
        self.progress.style().polish(self.progress)

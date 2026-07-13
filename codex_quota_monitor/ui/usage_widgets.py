from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from codex_quota_monitor.core.models import ResetCredit


class UsageLimitRow(QWidget):
    def __init__(self, title: str, unavailable_text: str = "-") -> None:
        super().__init__()
        self.unavailable_text = unavailable_text

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(18)

        copy = QVBoxLayout()
        copy.setSpacing(3)
        self.label = QLabel(title)
        self.label.setObjectName("limitTitle")
        self.reset = QLabel(unavailable_text)
        self.reset.setObjectName("limitReset")
        copy.addWidget(self.label)
        copy.addWidget(self.reset)
        layout.addLayout(copy, 1)

        meter = QHBoxLayout()
        meter.setSpacing(12)
        self.progress = QProgressBar()
        self.progress.setObjectName("limitProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(160)
        self.progress.setFixedHeight(8)
        self.percent = QLabel(unavailable_text)
        self.percent.setObjectName("limitPercent")
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        meter.addWidget(self.progress)
        meter.addWidget(self.percent)
        layout.addLayout(meter)

        self.update_values(None, None)

    def update_values(self, percent_remaining: int | None, reset_text: str | None) -> None:
        if percent_remaining is None:
            self.percent.setText(self.unavailable_text)
            self.reset.setText(self.unavailable_text)
            self.progress.setValue(0)
            state = "unknown"
        else:
            percent_remaining = max(0, min(100, percent_remaining))
            self.percent.setText(f"剩余 {percent_remaining}%")
            self.reset.setText(
                f"将于 {reset_text} 重置" if reset_text else self.unavailable_text
            )
            self.progress.setValue(percent_remaining)
            state = "normal"
            if percent_remaining < 10:
                state = "critical"
            elif percent_remaining < 20:
                state = "warning"

        for widget in (self.percent, self.progress):
            widget.setProperty("quotaState", state)
            widget.style().unpolish(widget)
            widget.style().polish(widget)


class ResetCreditRow(QWidget):
    def __init__(self, credit: ResetCredit) -> None:
        super().__init__()
        self.credit = credit

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        self.title_label = QLabel(credit.title or "Full reset")
        self.title_label.setObjectName("resetCreditTitle")
        self.expiry_label = QLabel(_format_expiry(credit))
        self.expiry_label.setObjectName("resetCreditExpiry")
        self.expiry_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.expiry_label)


class ResetCreditsPanel(QFrame):
    expanded_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("resetPanel")
        self._expanded = True
        self.rows: list[ResetCreditRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(16, 12, 12, 12)
        header.setSpacing(10)
        title = QLabel("使用限额重置")
        title.setObjectName("resetSectionTitle")
        self.count_badge = QLabel("可用 - 次")
        self.count_badge.setObjectName("resetBadge")
        self.toggle_button = QToolButton()
        self.toggle_button.setObjectName("resetToggleButton")
        self.toggle_button.setArrowType(Qt.ArrowType.UpArrow)
        self.toggle_button.setToolTip("收起重置详情")
        self.toggle_button.clicked.connect(self.toggle_expanded)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.count_badge)
        header.addWidget(self.toggle_button)
        layout.addLayout(header)

        layout.addWidget(_separator())
        self.body = QWidget()
        self.body.setObjectName("resetList")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        layout.addWidget(self.body)
        self.update_credits((), None)

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.body.setVisible(expanded)
        self.toggle_button.setArrowType(
            Qt.ArrowType.UpArrow if expanded else Qt.ArrowType.DownArrow
        )
        self.toggle_button.setToolTip("收起重置详情" if expanded else "展开重置详情")
        self.updateGeometry()
        self.expanded_changed.emit(expanded)

    def update_credits(
        self,
        credits: Iterable[ResetCredit],
        available_count: int | None,
    ) -> None:
        available = tuple(credit for credit in credits if credit.is_available)
        self.count_badge.setText(
            "可用 - 次" if available_count is None else f"可用 {available_count} 次"
        )
        badge_state = "unknown" if available_count is None else "available"
        if available_count == 0:
            badge_state = "empty"
        self.count_badge.setProperty("resetState", badge_state)
        self.count_badge.style().unpolish(self.count_badge)
        self.count_badge.style().polish(self.count_badge)

        _clear_layout(self.body_layout)
        self.rows.clear()
        if available:
            for index, credit in enumerate(available):
                if index:
                    self.body_layout.addWidget(_separator())
                row = ResetCreditRow(credit)
                self.rows.append(row)
                self.body_layout.addWidget(row)
        else:
            empty = QLabel(
                "重置日期暂不可用"
                if available_count is not None and available_count > 0
                else "当前没有可用重置"
            )
            empty.setObjectName("resetEmptyLabel")
            self.body_layout.addWidget(empty)
        self.body.setVisible(self._expanded)
        self.updateGeometry()


def _format_expiry(credit: ResetCredit) -> str:
    if credit.expires_at is None:
        return "-"
    local = credit.expires_at.astimezone()
    return f"{local.month}/{local.day} 到期"


def _separator() -> QFrame:
    separator = QFrame()
    separator.setObjectName("sectionSeparator")
    separator.setFrameShape(QFrame.Shape.HLine)
    separator.setFixedHeight(1)
    return separator


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()

from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from codex_quota_monitor.core.models import ResetCredit
from codex_quota_monitor.ui.usage_widgets import ResetCreditsPanel


def test_reset_panel_shows_count_and_right_aligned_expiry():
    app = QApplication.instance() or QApplication([])
    credit = ResetCredit(
        title="Full reset",
        reset_type="codex_rate_limits",
        status="available",
        granted_at=None,
        expires_at=datetime(2026, 7, 27, 0, 3, 49, tzinfo=timezone.utc),
    )
    panel = ResetCreditsPanel()

    panel.update_credits((credit,), 1)

    local_expiry = credit.expires_at.astimezone()
    assert panel.count_badge.text() == "可用 1 次"
    assert len(panel.rows) == 1
    assert panel.rows[0].title_label.text() == "Full reset"
    assert panel.rows[0].expiry_label.text() == (
        f"{local_expiry.month}/{local_expiry.day} 到期"
    )
    assert panel.rows[0].expiry_label.alignment() & Qt.AlignmentFlag.AlignRight
    assert app is not None
    panel.deleteLater()


def test_reset_panel_can_collapse_and_expand_details():
    app = QApplication.instance() or QApplication([])
    panel = ResetCreditsPanel()
    panel.show()
    app.processEvents()

    panel.toggle_button.click()
    assert panel.is_expanded is False
    assert panel.body.isHidden()

    panel.toggle_button.click()
    assert panel.is_expanded is True
    assert not panel.body.isHidden()
    panel.close()
    panel.deleteLater()

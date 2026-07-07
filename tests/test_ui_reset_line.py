from PySide6.QtWidgets import QApplication, QPushButton

from codex_quota_monitor.ui.main_window import ActionLine


def test_reset_line_is_static_text_without_arrow():
    app = QApplication.instance() or QApplication([])

    line = ActionLine("可用重置", "2 次  ›")

    assert app is not None
    assert not isinstance(line, QPushButton)
    assert "›" not in line.text()

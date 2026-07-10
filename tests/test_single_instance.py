from uuid import uuid4

from PySide6.QtWidgets import QApplication

from codex_quota_monitor.core.single_instance import SingleInstance


def test_second_instance_requests_activation_from_first_instance():
    app = QApplication.instance() or QApplication([])
    name = f"CodexQuotaMonitor-test-{uuid4()}"
    first = SingleInstance(name)
    second = SingleInstance(name)
    activations = []
    first.activation_requested.connect(lambda: activations.append("show"))

    assert first.acquire() is True
    assert second.acquire() is False
    for _ in range(10):
        app.processEvents()
        if activations:
            break

    assert activations == ["show"]
    second.shutdown()
    first.shutdown()

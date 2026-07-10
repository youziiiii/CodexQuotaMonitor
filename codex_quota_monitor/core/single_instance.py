from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    activation_requested = Signal()

    def __init__(self, server_name: str = "CodexQuotaMonitor") -> None:
        super().__init__()
        self.server_name = server_name
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._accept_connections)
        self._owns_server = False

    def acquire(self) -> bool:
        probe = QLocalSocket(self)
        probe.connectToServer(self.server_name)
        if probe.waitForConnected(250):
            probe.write(b"activate")
            probe.waitForBytesWritten(250)
            probe.disconnectFromServer()
            return False

        QLocalServer.removeServer(self.server_name)
        if not self.server.listen(self.server_name):
            raise RuntimeError(f"无法创建单实例服务：{self.server.errorString()}")
        self._owns_server = True
        return True

    def shutdown(self) -> None:
        if not self._owns_server:
            return
        self.server.close()
        QLocalServer.removeServer(self.server_name)
        self._owns_server = False

    def _accept_connections(self) -> None:
        while self.server.hasPendingConnections():
            connection = self.server.nextPendingConnection()
            if connection is None:
                continue
            self.activation_requested.emit()
            connection.disconnectFromServer()
            connection.deleteLater()

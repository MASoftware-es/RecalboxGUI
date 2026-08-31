from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from ..models import RecalboxEnvironment
from .ssh import ConnectionAttempt, RecalboxConnection


class ConnectionManager(QObject):
    """Único propietario y punto de cierre de las sesiones SSH de la aplicación."""

    connected = Signal(str, object)
    failed = Signal(str, str, str)
    attemptFinished = Signal(str)
    disconnected = Signal(str)

    def __init__(self, known_hosts: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._known_hosts = known_hosts
        self._connections: dict[str, RecalboxConnection] = {}
        self._attempts: dict[str, tuple[QThread, ConnectionAttempt]] = {}
        self._pending: set[str] = set()

    def is_connected(self, identifier: str) -> bool:
        return identifier in self._connections

    def is_pending(self, identifier: str) -> bool:
        return identifier in self._pending

    @property
    def has_pending_attempts(self) -> bool:
        return bool(self._pending)

    def connect_environment(self, environment: RecalboxEnvironment) -> bool:
        identifier = environment.identifier
        if self.is_connected(identifier) or self.is_pending(identifier):
            return False

        thread = QThread(self)
        attempt = ConnectionAttempt(environment, self._known_hosts)
        attempt.moveToThread(thread)
        thread.started.connect(attempt.run)
        attempt.connected.connect(self._connection_succeeded)
        attempt.failed.connect(self.failed.emit)
        attempt.finished.connect(self._attempt_finished)
        attempt.finished.connect(thread.quit)
        attempt.finished.connect(attempt.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda value=identifier: self._attempts.pop(value, None)
        )
        self._attempts[identifier] = thread, attempt
        self._pending.add(identifier)
        thread.start()
        return True

    def connection(self, identifier: str) -> RecalboxConnection | None:
        return self._connections.get(identifier)

    def close_connection(self, identifier: str) -> bool:
        connection = self._connections.pop(identifier, None)
        if connection is None:
            return False
        connection.close()
        self.disconnected.emit(identifier)
        return True

    def close_all(self) -> None:
        for identifier in tuple(self._connections):
            self.close_connection(identifier)

    def _connection_succeeded(
        self, identifier: str, connection: RecalboxConnection
    ) -> None:
        if self.is_connected(identifier):
            connection.close()
            return
        self._connections[identifier] = connection
        self.connected.emit(identifier, connection)

    def _attempt_finished(self, identifier: str) -> None:
        self._pending.discard(identifier)
        self.attemptFinished.emit(identifier)

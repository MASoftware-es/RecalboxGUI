from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from .ssh import RecalboxConnection


class RemoteScriptAttempt(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    outputLine = Signal(str)
    finished = Signal()

    def __init__(
        self,
        connection: RecalboxConnection,
        script: Path,
        arguments: tuple[str, ...],
        interpreter: str = "bash",
        timeout: float = 90.0,
    ) -> None:
        super().__init__()
        self.connection = connection
        self.script = script
        self.arguments = arguments
        self.interpreter = interpreter
        self.timeout = timeout

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(
                self.connection.run_script(
                    self.script,
                    self.arguments,
                    timeout=self.timeout,
                    output_line=self.outputLine.emit,
                    interpreter=self.interpreter,
                )
            )
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()


class RemoteDirectoryAttempt(QObject):
    succeeded = Signal(list)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, connection: RecalboxConnection, remote_path: str) -> None:
        super().__init__()
        self.connection = connection
        self.remote_path = remote_path

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(self.connection.list_directories(self.remote_path))
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()

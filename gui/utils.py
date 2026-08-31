from __future__ import annotations

from collections.abc import Callable
from tempfile import TemporaryDirectory
from typing import Any

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QStandardPaths, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QMessageBox, QWidget

from .assets import DIALOG_SOUND_PATH
from .paths import AppPaths


_dialog_player: QMediaPlayer | None = None
_dialog_audio: QAudioOutput | None = None
_dialog_text: Callable[[str], str] = lambda key: {
    "common.accept": "Aceptar",
    "common.yes": "Sí",
    "common.no": "No",
}.get(key, key)


def configure_dialog_translation(translator: Callable[[str], str]) -> None:
    """Configura el traductor utilizado por todos los cuadros de mensaje."""
    global _dialog_text
    _dialog_text = translator


def temporary_directory(prefix: str = "job-") -> TemporaryDirectory[str]:
    """Crea un temporal dentro de la caché privada del usuario."""
    paths = AppPaths.discover()
    paths.ensure()
    return TemporaryDirectory(prefix=prefix, dir=paths.temporary)


def open_external_location(url: QUrl) -> bool:
    """Abre una ubicación, con fallback directo para carpetas Samba."""
    if url.scheme().lower() == "smb":
        for candidate in (
            "nemo",
            "nautilus",
            "dolphin",
            "thunar",
            "pcmanfm-qt",
            "pcmanfm",
        ):
            executable = QStandardPaths.findExecutable(candidate)
            if not executable:
                continue
            process = QProcess()
            process.setProcessEnvironment(external_process_environment())
            process.setProgram(executable)
            arguments = [url.toString()]
            if candidate == "nemo":
                arguments.insert(0, "--no-desktop")
            process.setArguments(arguments)
            started = process.startDetached()
            if started:
                return True
    return QDesktopServices.openUrl(url)


def external_process_environment() -> QProcessEnvironment:
    """Entorno de escritorio sin inyecciones de runtimes Snap externos."""
    environment = QProcessEnvironment()
    system_environment = QProcessEnvironment.systemEnvironment()
    for name in (
        "HOME",
        "USER",
        "LOGNAME",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XAUTHORITY",
        "XDG_RUNTIME_DIR",
        "XDG_CURRENT_DESKTOP",
        "DESKTOP_SESSION",
        "DBUS_SESSION_BUS_ADDRESS",
        "LANG",
        "LC_ALL",
    ):
        if system_environment.contains(name):
            environment.insert(name, system_environment.value(name))
    environment.insert(
        "PATH",
        "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    )
    return environment


class AnonymousSambaOpener(QObject):
    """Monta como invitado y abre cualquier carpeta de un recurso Samba."""

    busyChanged = Signal(bool)
    opened = Signal()
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._target_url = QUrl()

    @property
    def busy(self) -> bool:
        return self._process is not None

    def open(self, target_url: QUrl) -> bool:
        """Inicia la apertura; devuelve False si la URL no es válida o está ocupado."""
        if self.busy or target_url.scheme().lower() != "smb" or not target_url.host():
            return False
        path_parts = [part for part in target_url.path().split("/") if part]
        if not path_parts:
            return False
        gio = QStandardPaths.findExecutable("gio")
        if not gio:
            self.failed.emit("GVFS_NOT_AVAILABLE")
            return True

        share_url = QUrl()
        share_url.setScheme("smb")
        share_url.setHost(target_url.host())
        share_url.setPath(f"/{path_parts[0]}")
        self._target_url = QUrl(target_url)
        self.busyChanged.emit(True)
        self._run(
            gio,
            ["mount", "--unmount", share_url.toString()],
            lambda _code, _detail: self._mount_anonymously(gio, share_url),
        )
        return True

    def _mount_anonymously(self, gio: str, share_url: QUrl) -> None:
        self._run(
            gio,
            ["mount", "--anonymous", share_url.toString()],
            self._mount_finished,
        )

    def _mount_finished(self, exit_code: int, detail: str) -> None:
        self._process = None
        self.busyChanged.emit(False)
        if exit_code != 0:
            self.failed.emit(detail or "ANONYMOUS_MOUNT_FAILED")
            return
        if not open_external_location(self._target_url):
            self.failed.emit("FILE_MANAGER_FAILED")
            return
        self.opened.emit()

    def _run(self, program: str, arguments: list[str], callback: Callable[[int, str], None]) -> None:
        process = QProcess(self)
        process.setProcessEnvironment(external_process_environment())
        process.setProgram(program)
        process.setArguments(arguments)

        def finished(exit_code: int, _status: QProcess.ExitStatus) -> None:
            detail = bytes(process.readAllStandardError()).decode(
                "utf-8", errors="replace"
            ).strip()
            callback(exit_code, detail)
            process.deleteLater()

        process.finished.connect(finished)
        self._process = process
        process.start()


def play_dialog_sound() -> None:
    """Reproduce el sonido común de diálogo sin bloquear la interfaz."""
    global _dialog_player, _dialog_audio
    if _dialog_player is None:
        _dialog_audio = QAudioOutput()
        _dialog_audio.setVolume(0.7)
        _dialog_player = QMediaPlayer()
        _dialog_player.setAudioOutput(_dialog_audio)
        _dialog_player.setSource(QUrl.fromLocalFile(str(DIALOG_SOUND_PATH)))
    _dialog_player.stop()
    _dialog_player.setPosition(0)
    _dialog_player.play()


def format_bytes(size: int) -> str:
    value = float(max(0, size))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            decimals = 0 if unit == "B" else 1
            return f"{value:.{decimals}f} {unit}"
        value /= 1024
    raise AssertionError("unidad inalcanzable")


def format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "--:--"
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def show_information(parent: QWidget | None, title: str, message: str) -> None:
    _show_message(parent, QMessageBox.Icon.Information, title, message)


def show_warning(parent: QWidget | None, title: str, message: str) -> None:
    _show_message(parent, QMessageBox.Icon.Warning, title, message)


def show_error(parent: QWidget | None, title: str, message: str) -> None:
    _show_message(parent, QMessageBox.Icon.Critical, title, message)


def ask_confirmation(parent: QWidget | None, title: str, message: str) -> bool:
    answer = _show_message(
        parent,
        QMessageBox.Icon.Question,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


def _show_message(
    parent: QWidget | None,
    icon: QMessageBox.Icon,
    title: str,
    message: str,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    default: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
) -> QMessageBox.StandardButton:
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(message)
    box.setStandardButtons(buttons)
    box.setDefaultButton(default)
    labels = {
        QMessageBox.StandardButton.Ok: "common.accept",
        QMessageBox.StandardButton.Yes: "common.yes",
        QMessageBox.StandardButton.No: "common.no",
    }
    for button_type, key in labels.items():
        button = box.button(button_type)
        if button is not None:
            button.setText(_dialog_text(key))
    return QMessageBox.StandardButton(box.exec())


def safely(callback: Callable[..., Any], on_error: Callable[[Exception], None]) -> Callable[..., None]:
    """Envuelve un callback visual y comunica sus excepciones sin cerrar Qt."""
    def wrapped(*args: Any, **kwargs: Any) -> None:
        try:
            callback(*args, **kwargs)
        except Exception as exc:
            on_error(exc)

    return wrapped

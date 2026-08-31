from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QMessageBox, QWidget

from .utils import play_dialog_sound


class DialogSoundEventFilter(QObject):
    """Aplica de forma centralizada la política sonora de los diálogos."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(watched, QWidget):
            if isinstance(watched, QMessageBox) or bool(watched.property("dialogSound")):
                play_dialog_sound()
        return super().eventFilter(watched, event)

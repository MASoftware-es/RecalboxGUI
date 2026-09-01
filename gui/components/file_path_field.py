from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from ..i18n import Translator


class FilePathField(QWidget):
    """Campo reutilizable para una ruta con selección visual asociada."""

    selectRequested = Signal()

    def __init__(self, translator: Translator, parent=None) -> None:
        super().__init__(parent)
        self.translator = translator
        self.path_edit = QLineEdit()
        self.select_button = QPushButton()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.path_edit, 1)
        layout.addWidget(self.select_button)
        self.select_button.clicked.connect(self.selectRequested.emit)
        self.retranslate_ui()

    def text(self) -> str:
        return self.path_edit.text()

    def setText(self, value: str) -> None:
        self.path_edit.setText(value)

    def clear(self) -> None:
        self.path_edit.clear()

    def retranslate_ui(self) -> None:
        self.select_button.setText(self.translator("gamelist.select_rom"))

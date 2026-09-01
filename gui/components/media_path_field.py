from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ..i18n import Translator


class MediaPathField(QWidget):
    selectRequested = Signal()
    uploadRequested = Signal()
    deleteRequested = Signal()

    def __init__(self, translator: Translator, parent=None) -> None:
        super().__init__(parent)
        self.translator = translator
        self._delete_allowed = True
        self.path_edit = QLineEdit()
        self.select_button = QPushButton()
        self.upload_button = QPushButton()
        self.delete_button = QPushButton()
        self.delete_button.setProperty("danger", True)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(220, 130)
        self.preview.setMaximumHeight(190)
        self.preview.setProperty("role", "mediaPreview")

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.path_edit, 1)
        row.addWidget(self.select_button)
        row.addWidget(self.upload_button)
        row.addWidget(self.delete_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(row)
        layout.addWidget(self.preview)

        self.select_button.clicked.connect(self.selectRequested.emit)
        self.upload_button.clicked.connect(self.uploadRequested.emit)
        self.delete_button.clicked.connect(self.deleteRequested.emit)
        self.path_edit.textChanged.connect(self._update_delete_state)
        self.retranslate_ui()

    def text(self) -> str:
        return self.path_edit.text()

    def set_text(self, value: str) -> None:
        self.path_edit.setText(value)

    def set_preview(self, data: bytes) -> None:
        pixmap = QPixmap()
        if data and pixmap.loadFromData(data):
            self.preview.setPixmap(
                pixmap.scaled(
                    self.preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.preview.setText("")
        else:
            self.preview.clear()
            self.preview.setText(self.translator("gamelist.no_image"))

    def set_busy(self, busy: bool) -> None:
        self.path_edit.setEnabled(not busy)
        self.select_button.setEnabled(not busy)
        self.upload_button.setEnabled(not busy)
        self.delete_button.setEnabled(
            not busy and self._delete_allowed and bool(self.text().strip())
        )

    def set_delete_enabled(self, enabled: bool) -> None:
        self._delete_allowed = enabled
        self._update_delete_state()

    def _update_delete_state(self) -> None:
        self.delete_button.setEnabled(
            self.isEnabled() and self._delete_allowed and bool(self.text().strip())
        )

    def retranslate_ui(self) -> None:
        self.select_button.setText(self.translator("gamelist.select_media"))
        self.upload_button.setText(self.translator("gamelist.upload"))
        self.delete_button.setText(self.translator("gamelist.delete_media"))
        if self.preview.pixmap().isNull():
            self.preview.setText(self.translator("gamelist.no_image"))

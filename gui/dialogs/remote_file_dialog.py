from __future__ import annotations

import posixpath

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from ..i18n import Translator
from ..utils import show_error


class RemoteFileDialog(QDialog):
    """Explorador SSH que no permite navegar fuera de su carpeta raíz."""

    def __init__(
        self,
        connection,
        root_path: str,
        translator: Translator,
        parent=None,
        *,
        allowed_extensions: tuple[str, ...] | None = None,
        title_key: str = "gamelist.file_browser_title",
    ):
        super().__init__(parent)
        self.connection = connection
        self.root_path = posixpath.normpath(root_path)
        self.current_path = self.root_path
        self.translator = translator
        self.allowed_extensions = (
            tuple(extension.casefold() for extension in allowed_extensions)
            if allowed_extensions
            else None
        )
        self.selected_path = ""

        self.setWindowTitle(translator(title_key))
        self.resize(620, 470)
        self.path_label = QLabel()
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.file_list = QListWidget()
        self.up_button = QPushButton(translator("gamelist.file_browser_up"))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.open_button = buttons.button(QDialogButtonBox.StandardButton.Open)
        self.open_button.setText(translator("gamelist.file_browser_select"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            translator("common.cancel")
        )
        self.open_button.setEnabled(False)

        top = QHBoxLayout()
        top.addWidget(self.up_button)
        top.addWidget(self.path_label, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.file_list, 1)
        layout.addWidget(buttons)

        self.up_button.clicked.connect(self._go_up)
        self.file_list.itemSelectionChanged.connect(self._selection_changed)
        self.file_list.itemDoubleClicked.connect(self._activate_item)
        buttons.accepted.connect(self._accept_file)
        buttons.rejected.connect(self.reject)
        self._load_directory()

    def _load_directory(self) -> None:
        try:
            entries = self.connection.list_directory_entries(self.current_path)
        except Exception as error:
            show_error(
                self,
                self.translator("gamelist.error_title"),
                self.translator("gamelist.remote_error", detail=str(error)),
            )
            return
        relative = posixpath.relpath(self.current_path, self.root_path)
        self.path_label.setText("/" if relative == "." else relative)
        self.file_list.clear()
        for name, is_directory in entries:
            if (
                not is_directory
                and self.allowed_extensions is not None
                and not name.casefold().endswith(self.allowed_extensions)
            ):
                continue
            item = QListWidgetItem(("📁 " if is_directory else "📄 ") + name)
            item.setData(Qt.ItemDataRole.UserRole, (name, is_directory))
            self.file_list.addItem(item)
        self.up_button.setEnabled(self.current_path != self.root_path)
        self.open_button.setEnabled(False)

    def _selection_changed(self) -> None:
        item = self.file_list.currentItem()
        self.open_button.setEnabled(
            bool(item and not item.data(Qt.ItemDataRole.UserRole)[1])
        )

    def _activate_item(self, item: QListWidgetItem) -> None:
        name, is_directory = item.data(Qt.ItemDataRole.UserRole)
        if is_directory:
            self.current_path = posixpath.join(self.current_path, name)
            self._load_directory()
        else:
            self._accept_file()

    def _go_up(self) -> None:
        if self.current_path == self.root_path:
            return
        parent = posixpath.dirname(self.current_path)
        if parent == self.root_path or parent.startswith(self.root_path + "/"):
            self.current_path = parent
            self._load_directory()

    def _accept_file(self) -> None:
        item = self.file_list.currentItem()
        if item is None:
            return
        name, is_directory = item.data(Qt.ItemDataRole.UserRole)
        if is_directory:
            return
        absolute = posixpath.join(self.current_path, name)
        self.selected_path = posixpath.relpath(absolute, self.root_path)
        self.accept()

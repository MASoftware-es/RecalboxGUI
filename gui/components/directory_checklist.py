from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QHeaderView, QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ..i18n import Translator


class DirectoryChecklist(QWidget):
    """Selector reutilizable de directorios mediante casillas."""

    selectionChanged = Signal()

    def __init__(self, translator: Translator, parent=None) -> None:
        super().__init__(parent)
        self.translator = translator
        self._controls_enabled = True
        self._checkboxes: list[QCheckBox] = []
        self.list = QTreeWidget()
        self.list.setRootIsDecorated(False)
        self.list.setAlternatingRowColors(True)
        self.list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.list.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.select_all_button = QPushButton()
        self.select_none_button = QPushButton()
        self.button_layout = QHBoxLayout()
        self.button_layout.addWidget(self.select_all_button)
        self.button_layout.addWidget(self.select_none_button)
        self.button_layout.addStretch()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list)
        layout.addLayout(self.button_layout)
        self.select_all_button.clicked.connect(lambda: self.set_all_checked(True))
        self.select_none_button.clicked.connect(lambda: self.set_all_checked(False))
        self.retranslate_ui()

    def set_directories(self, names: list[str]) -> None:
        self.list.clear()
        self._checkboxes.clear()
        for name in names:
            item = QTreeWidgetItem(["", name])
            item.setSizeHint(0, QSize(0, 28))
            self.list.addTopLevelItem(item)
            checkbox = QCheckBox()
            checkbox.toggled.connect(lambda _checked: self.selectionChanged.emit())
            container = QWidget()
            container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            checkbox_layout = QHBoxLayout(container)
            checkbox_layout.setContentsMargins(0, 3, 0, 3)
            checkbox_layout.addStretch()
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.addStretch()
            self.list.setItemWidget(item, 0, container)
            self._checkboxes.append(checkbox)
        self.set_controls_enabled(self._controls_enabled)
        self.selectionChanged.emit()

    def selected_directories(self) -> list[str]:
        return [
            self.list.topLevelItem(row).text(1)
            for row in range(self.list.topLevelItemCount())
            if self._checkboxes[row].isChecked()
        ]

    def set_all_checked(self, checked: bool) -> None:
        for checkbox in self._checkboxes:
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)
        self.selectionChanged.emit()

    def set_controls_enabled(self, enabled: bool) -> None:
        self._controls_enabled = enabled
        self.list.setEnabled(enabled)
        self.select_all_button.setEnabled(enabled and self.list.topLevelItemCount() > 0)
        self.select_none_button.setEnabled(enabled and self.list.topLevelItemCount() > 0)

    def retranslate_ui(self) -> None:
        self.list.setHeaderLabels(
            [
                self.translator("directory_selector.marked"),
                self.translator("directory_selector.platform"),
            ]
        )
        self.select_all_button.setText(self.translator("directory_selector.all"))
        self.select_none_button.setText(self.translator("directory_selector.none"))

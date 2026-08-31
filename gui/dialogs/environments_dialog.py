from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import Translator
from ..models import RecalboxEnvironment
from ..utils import ask_confirmation
from .base_dialog import ModalDialog


class EnvironmentsDialog(ModalDialog):
    def __init__(
        self,
        translator: Translator,
        environments: list[RecalboxEnvironment],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.translator = translator
        self.environments = deepcopy(environments)
        self._loading = False
        self.setWindowTitle(translator("environments.title"))
        self.setModal(True)
        self.resize(820, 480)

        self.environment_list = QListWidget()
        self.environment_list.setMinimumWidth(240)
        self.add_button = QPushButton(translator("common.add"))
        self.remove_button = QPushButton(translator("common.remove"))

        list_buttons = QHBoxLayout()
        list_buttons.addWidget(self.add_button)
        list_buttons.addWidget(self.remove_button)
        left = QVBoxLayout()
        left.addWidget(self.environment_list)
        left.addLayout(list_buttons)

        self.name_edit = QLineEdit()
        self.host_edit = QLineEdit()
        self.user_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_button = QToolButton()
        self.password_button.setText("👁")
        self.password_button.setCheckable(True)
        self.password_button.setToolTip(translator("environments.show_password"))
        password_container = QWidget()
        password_layout = QHBoxLayout(password_container)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(4)
        password_layout.addWidget(self.password_edit, 1)
        password_layout.addWidget(self.password_button)
        self.roms_path_edit = QLineEdit()

        self.form = QFormLayout()
        self.form.addRow(translator("environments.name"), self.name_edit)
        self.form.addRow(translator("environments.host"), self.host_edit)
        self.form.addRow(translator("environments.user"), self.user_edit)
        self.form.addRow(translator("environments.password"), password_container)
        self.form.addRow(translator("environments.roms_path"), self.roms_path_edit)

        self.form_container = QWidget()
        self.form_container.setLayout(self.form)
        self.placeholder = QLabel(translator("environments.select_hint"))
        self.placeholder.setProperty("role", "muted")
        self.placeholder.setWordWrap(True)

        right = QVBoxLayout()
        right.addWidget(self.form_container)
        right.addWidget(self.placeholder)
        right.addStretch()

        body = QHBoxLayout()
        body.addLayout(left, 1)
        body.addLayout(right, 2)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(translator("common.save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(translator("common.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(body)
        layout.addWidget(buttons)

        self.environment_list.currentRowChanged.connect(self._load_row)
        self.add_button.clicked.connect(self._add_environment)
        self.remove_button.clicked.connect(self._remove_environment)
        self.password_button.toggled.connect(self._toggle_password_visibility)
        for editor in self._editors():
            editor.textEdited.connect(self._update_current)

        self._rebuild_list()

    def _editors(self) -> tuple[QLineEdit, ...]:
        return self.name_edit, self.host_edit, self.user_edit, self.password_edit, self.roms_path_edit

    def _rebuild_list(self, selected: int = 0) -> None:
        self.environment_list.clear()
        for environment in self.environments:
            item = QListWidgetItem(environment.name)
            item.setData(Qt.ItemDataRole.UserRole, environment.identifier)
            self.environment_list.addItem(item)
        if self.environments:
            self.environment_list.setCurrentRow(min(selected, len(self.environments) - 1))
        else:
            self._load_row(-1)

    def _load_row(self, row: int) -> None:
        enabled = 0 <= row < len(self.environments)
        self.form_container.setEnabled(enabled)
        self.form_container.setVisible(enabled)
        self.placeholder.setVisible(not enabled)
        self.remove_button.setEnabled(enabled)
        self.password_button.setChecked(False)
        self._loading = True
        if enabled:
            environment = self.environments[row]
            values = environment.name, environment.host, environment.username, environment.password, environment.roms_path
        else:
            values = "", "", "", "", ""
        for editor, value in zip(self._editors(), values):
            editor.setText(value)
        self._loading = False

    def _toggle_password_visibility(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password_edit.setEchoMode(mode)
        key = "environments.hide_password" if visible else "environments.show_password"
        self.password_button.setToolTip(self.translator(key))

    def _update_current(self) -> None:
        if self._loading:
            return
        row = self.environment_list.currentRow()
        if not 0 <= row < len(self.environments):
            return
        environment = self.environments[row]
        environment.name = self.name_edit.text().strip()
        environment.host = self.host_edit.text().strip()
        environment.username = self.user_edit.text().strip()
        environment.password = self.password_edit.text()
        environment.roms_path = self.roms_path_edit.text().strip()
        self.environment_list.item(row).setText(environment.name or self.translator("environments.unnamed"))

    def _add_environment(self) -> None:
        base = self.translator("environments.new_name")
        used = {environment.name for environment in self.environments}
        name = base
        number = 2
        while name in used:
            name = f"{base} {number}"
            number += 1
        self.environments.append(RecalboxEnvironment.create(name))
        self._rebuild_list(len(self.environments) - 1)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _remove_environment(self) -> None:
        row = self.environment_list.currentRow()
        if not 0 <= row < len(self.environments):
            return
        if not ask_confirmation(
            self,
            self.translator("environments.remove_title"),
            self.translator("environments.remove_confirm", name=self.environments[row].name),
        ):
            return
        del self.environments[row]
        self._rebuild_list(row)

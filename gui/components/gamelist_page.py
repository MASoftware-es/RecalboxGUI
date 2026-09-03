from __future__ import annotations

import posixpath
import unicodedata
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..connection import RemoteCallAttempt, RemoteFileChangedError
from ..dialogs.remote_file_dialog import RemoteFileDialog
from ..gamelist import EditableGame, GameListData, GameListRepository, GameListValidationError
from ..i18n import Translator
from ..utils import ask_confirmation, show_error, show_information
from .file_path_field import FilePathField
from .media_path_field import MediaPathField
from .marked_checkbox import MarkedCheckBox


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")


def _alphabetical_key(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    ).casefold()


class GameListItem(QTreeWidgetItem):
    """Fila ordenable por nombre, carátula o estado oculto."""

    def __lt__(self, other: QTreeWidgetItem) -> bool:
        column = self.treeWidget().sortColumn() if self.treeWidget() else 0
        if column in {1, 2}:
            own_value = bool(self.data(column, Qt.ItemDataRole.UserRole))
            other_value = bool(other.data(column, Qt.ItemDataRole.UserRole))
            if own_value != other_value:
                return own_value < other_value
        return _alphabetical_key(self.text(0)) < _alphabetical_key(other.text(0))


class GameListPage(QWidget):
    def __init__(self, connection, translator: Translator, parent=None) -> None:
        super().__init__(parent)
        self.connection = connection
        self.translator = translator
        self.repository = GameListRepository(connection)
        self._thread: QThread | None = None
        self._worker: RemoteCallAttempt | None = None
        self._success_callback: Callable[[object], None] | None = None
        self._data: GameListData | None = None
        self._game: EditableGame | None = None
        self._pending_uploads: set[str] = set()
        self._pending_game_selection: int | None = None
        self._new_game = False
        self._operation_kind = ""
        self._requested_system = ""
        self._after_finish: Callable[[], None] | None = None
        self._restore_games_focus = False

        self.systems_group = QGroupBox()
        self.systems_list = QListWidget()
        self.systems_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        systems_layout = QVBoxLayout(self.systems_group)
        systems_layout.addWidget(self.systems_list)

        self.games_group = QGroupBox()
        self.games_list = QTreeWidget()
        self.games_list.setColumnCount(3)
        self.games_list.setRootIsDecorated(False)
        self.games_list.setAlternatingRowColors(True)
        self.games_list.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.games_list.setSortingEnabled(True)
        self.games_list.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.games_list.header().setStretchLastSection(False)
        self.games_list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.games_list.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.games_list.header().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.new_button = QPushButton()
        self.delete_button = QPushButton()
        self.delete_button.setProperty("danger", True)
        game_buttons = QHBoxLayout()
        game_buttons.addWidget(self.new_button)
        game_buttons.addWidget(self.delete_button)
        games_layout = QVBoxLayout(self.games_group)
        games_layout.addWidget(self.games_list)
        games_layout.addLayout(game_buttons)

        self.editor_group = QGroupBox()
        self.path_edit = FilePathField(translator)
        self.hidden_check = MarkedCheckBox()
        self.name_edit = QLineEdit()
        self.aliases_edit = QLineEdit()
        self.genre_edit = QLineEdit()
        self.genreid_edit = QLineEdit()
        self.publisher_edit = QLineEdit()
        self.developer_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setAcceptRichText(False)
        self.description_edit.setMinimumHeight(130)
        self.image_field = MediaPathField(translator)
        self.thumbnail_field = MediaPathField(translator)
        self.form = QFormLayout()
        self.editor_body = QWidget()
        self.editor_body.setLayout(self.form)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.editor_body)
        self.reload_button = QPushButton()
        self.save_button = QPushButton()
        self.save_button.setProperty("execution", True)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.reload_button)
        buttons.addWidget(self.save_button)
        editor_layout = QVBoxLayout(self.editor_group)
        editor_layout.addWidget(self.scroll, 1)
        editor_layout.addLayout(buttons)

        self.status = QLabel()
        self.status.setProperty("role", "muted")
        self.status.setWordWrap(True)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.systems_group)
        splitter.addWidget(self.games_group)
        splitter.addWidget(self.editor_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([220, 300, 580])
        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.status)

        self.systems_list.currentTextChanged.connect(self._load_selected_system)
        self.games_list.currentItemChanged.connect(self._select_game)
        self.reload_button.clicked.connect(self.reload_current_game)
        self.save_button.clicked.connect(self.save_current_game)
        self.new_button.clicked.connect(self.new_game)
        self.delete_button.clicked.connect(self.delete_current_game)
        self.path_edit.selectRequested.connect(self._select_rom_file)
        self.image_field.selectRequested.connect(
            lambda: self._select_remote_media("image")
        )
        self.thumbnail_field.selectRequested.connect(
            lambda: self._select_remote_media("thumbnail")
        )
        self.image_field.uploadRequested.connect(lambda: self._choose_image("image"))
        self.thumbnail_field.uploadRequested.connect(
            lambda: self._choose_image("thumbnail")
        )
        self.image_field.deleteRequested.connect(lambda: self.delete_media("image"))
        self.thumbnail_field.deleteRequested.connect(
            lambda: self.delete_media("thumbnail")
        )
        self.image_field.path_edit.textChanged.connect(self._update_media_delete_buttons)
        self.thumbnail_field.path_edit.textChanged.connect(
            self._update_media_delete_buttons
        )
        self.retranslate_ui()
        self._set_editor_enabled(False)
        self._load_systems()

    @property
    def busy(self) -> bool:
        return self._thread is not None

    def _build_form(self) -> None:
        tr = self.translator
        self.form.addRow(tr("gamelist.path"), self.path_edit)
        self.form.addRow(tr("gamelist.hidden"), self.hidden_check)
        self.form.addRow(tr("gamelist.name"), self.name_edit)
        self.form.addRow(tr("gamelist.aliases"), self.aliases_edit)
        self.form.addRow(tr("gamelist.genre"), self.genre_edit)
        self.form.addRow(tr("gamelist.genreid"), self.genreid_edit)
        self.form.addRow(tr("gamelist.publisher"), self.publisher_edit)
        self.form.addRow(tr("gamelist.developer"), self.developer_edit)
        self.form.addRow(tr("gamelist.description"), self.description_edit)
        self.form.addRow(tr("gamelist.image"), self.image_field)
        self.form.addRow(tr("gamelist.thumbnail"), self.thumbnail_field)

    def _retranslate_form(self) -> None:
        rows = (
            (self.path_edit, "gamelist.path"),
            (self.hidden_check, "gamelist.hidden"),
            (self.name_edit, "gamelist.name"),
            (self.aliases_edit, "gamelist.aliases"),
            (self.genre_edit, "gamelist.genre"),
            (self.genreid_edit, "gamelist.genreid"),
            (self.publisher_edit, "gamelist.publisher"),
            (self.developer_edit, "gamelist.developer"),
            (self.description_edit, "gamelist.description"),
            (self.image_field, "gamelist.image"),
            (self.thumbnail_field, "gamelist.thumbnail"),
        )
        for field, key in rows:
            label = self.form.labelForField(field)
            if isinstance(label, QLabel):
                label.setText(self.translator(key))

    def retranslate_ui(self) -> None:
        tr = self.translator
        self.systems_group.setTitle(tr("gamelist.systems"))
        self.games_group.setTitle(tr("gamelist.games"))
        self.games_list.setHeaderLabels(
            [tr("gamelist.name"), tr("gamelist.cover"), tr("gamelist.hidden")]
        )
        self.games_list.headerItem().setTextAlignment(
            1, Qt.AlignmentFlag.AlignCenter
        )
        self.games_list.headerItem().setTextAlignment(
            2, Qt.AlignmentFlag.AlignCenter
        )
        for row in range(self.games_list.topLevelItemCount()):
            item = self.games_list.topLevelItem(row)
            has_cover = bool(item.data(1, Qt.ItemDataRole.UserRole))
            item.setText(
                1, tr("common.yes") if has_cover else tr("common.no")
            )
            hidden = bool(item.data(2, Qt.ItemDataRole.UserRole))
            item.setText(
                2, tr("common.yes") if hidden else tr("common.no")
            )
        self.editor_group.setTitle(tr("gamelist.properties"))
        self.reload_button.setText(tr("gamelist.reload"))
        self.save_button.setText(tr("gamelist.save"))
        self.new_button.setText(tr("gamelist.new"))
        self.delete_button.setText(tr("gamelist.delete"))
        self.image_field.retranslate_ui()
        self.thumbnail_field.retranslate_ui()
        self.path_edit.retranslate_ui()
        if self.form.rowCount() == 0:
            self._build_form()
        else:
            self._retranslate_form()

    def _load_systems(self) -> None:
        self._operation_kind = "list_systems"
        self.status.setText(self.translator("gamelist.loading_systems"))
        self._start(self.repository.list_systems, self._systems_loaded)

    def _systems_loaded(self, systems: list[str]) -> None:
        self.systems_list.clear()
        self.systems_list.addItems(systems)
        self.status.setText(
            self.translator("gamelist.systems_loaded", count=len(systems))
        )

    def _load_selected_system(self, system: str) -> None:
        if not system or self.busy:
            return
        self._data = None
        self._new_game = False
        self._clear_game()
        self.games_list.clear()
        self._requested_system = system
        self._operation_kind = "load_system"
        self.status.setText(self.translator("gamelist.loading_games", system=system))
        self._start(lambda: self.repository.load_system(system), self._system_loaded)

    def _system_loaded(self, data: GameListData) -> None:
        self._data = data
        self._new_game = False
        self.games_list.blockSignals(True)
        self.games_list.clear()
        for game in data.games:
            has_cover = bool(game.values.get("image", "").strip())
            item = GameListItem(
                [
                    game.display_name,
                    self.translator("common.yes")
                    if has_cover
                    else self.translator("common.no"),
                    self.translator("common.yes")
                    if game.hidden
                    else self.translator("common.no"),
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, game.index)
            item.setData(1, Qt.ItemDataRole.UserRole, has_cover)
            item.setData(2, Qt.ItemDataRole.UserRole, game.hidden)
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
            self.games_list.addTopLevelItem(item)
        self.games_list.blockSignals(False)
        self.status.setText(
            self.translator("gamelist.games_loaded", count=len(data.games))
        )
        self._update_actions()

    def _select_game(self, current: QTreeWidgetItem | None, previous=None) -> None:
        del previous
        if current is None or self._data is None:
            self._clear_game()
            return
        index = int(current.data(0, Qt.ItemDataRole.UserRole))
        if not 0 <= index < len(self._data.games):
            self._clear_game()
            return
        self._game = self._data.games[index]
        self._new_game = False
        self._restore_games_focus = True
        self._show_game(self._game)
        self._load_game_media(self._data, self._game)

    def _show_game(self, game: EditableGame) -> None:
        values = game.values
        self.path_edit.setText(values["path"])
        self.hidden_check.setChecked(game.hidden)
        self.name_edit.setText(values["name"])
        self.aliases_edit.setText(values["aliases"])
        self.genre_edit.setText(values["genre"])
        self.genreid_edit.setText(values["genreid"])
        self.publisher_edit.setText(values["publisher"])
        self.developer_edit.setText(values["developer"])
        self.description_edit.setPlainText(values["desc"])
        self.image_field.set_text(values["image"])
        self.thumbnail_field.set_text(values["thumbnail"])
        self.image_field.set_preview(b"")
        self.thumbnail_field.set_preview(b"")
        self._set_editor_enabled(True)
        self._update_actions()
        self._update_media_delete_buttons()

    def _load_game_media(self, data: GameListData, game: EditableGame) -> None:
        self.status.setText(self.translator("gamelist.loading_media"))
        self._operation_kind = "load_media"
        self._start(
            lambda: self.repository.read_media_pair(data, game),
            self._media_loaded,
        )

    def _media_loaded(self, media: dict[str, bytes]) -> None:
        self.image_field.set_preview(media.get("image", b""))
        self.thumbnail_field.set_preview(media.get("thumbnail", b""))
        self.status.clear()

    def reload_current_game(self) -> None:
        if self._data is None or self._game is None or self._new_game or self.busy:
            return
        data, game = self._data, self._game
        self._operation_kind = "reload_game"
        self.status.setText(self.translator("gamelist.reloading"))
        self._start(
            lambda: self.repository.reload_game(data, game),
            self._reload_completed,
        )

    def _reload_completed(self, result: tuple[GameListData, EditableGame]) -> None:
        data, game = result
        self._data = data
        self._game = game
        self._new_game = False
        self._show_game(game)
        current_item = self.games_list.currentItem()
        if current_item is not None:
            current_item.setData(2, Qt.ItemDataRole.UserRole, game.hidden)
            current_item.setText(
                2,
                self.translator("common.yes")
                if game.hidden
                else self.translator("common.no"),
            )
        self.status.setText(self.translator("gamelist.reloaded"))
        self._after_finish = lambda: self._load_game_media(data, game)

    def save_current_game(self) -> None:
        if self._data is None or self._game is None or self.busy:
            return
        values = self._form_values()
        data, game = self._data, self._game
        is_new = self._new_game
        self._operation_kind = "create_game" if is_new else "save_game"
        self.status.setText(self.translator("gamelist.saving"))
        self._start(
            lambda: (
                self.repository.create_game(
                    data, values, self.hidden_check.isChecked()
                )
                if is_new
                else self.repository.save_game(
                    data, game, values, self.hidden_check.isChecked()
                )
            ),
            lambda updated: self._save_completed(
                updated, len(updated.games) - 1 if is_new else game.index, values
            ),
        )

    def _save_completed(
        self, data: GameListData, selected_index: int, values: dict[str, str]
    ) -> None:
        referenced = {
            posixpath.join(data.system_path, values[field].strip())
            for field in ("image", "thumbnail")
            if values[field].strip()
        }
        preserved = self._pending_uploads & referenced
        self.connection.unregister_cleanup_paths(*preserved)
        self._pending_uploads.difference_update(preserved)
        self._system_loaded(data)
        self._pending_game_selection = selected_index
        message = self.translator("gamelist.saved")
        self.status.setText(message)
        show_information(self, self.translator("gamelist.saved_title"), message)

    def new_game(self) -> None:
        if self._data is None or self.busy:
            return
        self.games_list.clearSelection()
        self.games_list.setCurrentItem(None)
        values = {
            field: ""
            for field in (
                "path",
                "name",
                "aliases",
                "genre",
                "genreid",
                "publisher",
                "developer",
                "desc",
                "image",
                "thumbnail",
            )
        }
        self._game = EditableGame(len(self._data.games), values)
        self._new_game = True
        self._show_game(self._game)
        self.status.setText(self.translator("gamelist.new_hint"))

    def delete_current_game(self) -> None:
        if self._data is None or self._game is None or self.busy:
            return
        if self._new_game:
            self._new_game = False
            self._clear_game()
            return
        delete_files = self._ask_game_deletion_scope(self._game.display_name)
        if delete_files is None:
            return
        if delete_files and not ask_confirmation(
            self,
            self.translator("gamelist.delete_files_title"),
            self.translator(
                "gamelist.delete_files_confirm", name=self._game.display_name
            ),
        ):
            return
        data, game = self._data, self._game
        next_row = min(game.index, max(0, len(data.games) - 2))
        self._operation_kind = "delete_game"
        self.status.setText(self.translator("gamelist.deleting"))
        self._start(
            lambda: self.repository.delete_game(
                data, game, delete_associated_files=delete_files
            ),
            lambda updated: self._delete_completed(updated, next_row),
        )

    def _ask_game_deletion_scope(self, name: str) -> bool | None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(self.translator("gamelist.delete_title"))
        box.setText(self.translator("gamelist.delete_scope", name=name))
        entry_button = QPushButton(self.translator("gamelist.delete_entry_only"))
        files_button = QPushButton(self.translator("gamelist.delete_entry_and_rom"))
        cancel_button = QPushButton(self.translator("common.cancel"))
        entry_button.setProperty("danger", True)
        files_button.setProperty("danger", True)
        box.addButton(entry_button, QMessageBox.ButtonRole.ActionRole)
        box.addButton(files_button, QMessageBox.ButtonRole.ActionRole)
        box.addButton(cancel_button, QMessageBox.ButtonRole.ActionRole)
        for button in (entry_button, files_button):
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()
        button_box = box.findChild(QDialogButtonBox)
        if button_box is not None:
            button_layout = button_box.layout()
            for button in (entry_button, files_button, cancel_button):
                button_layout.removeWidget(button)
                button_layout.addWidget(button)
        box.setDefaultButton(cancel_button)
        box.setEscapeButton(cancel_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is entry_button:
            return False
        if clicked is files_button:
            return True
        return None

    def _delete_completed(self, data: GameListData, next_row: int) -> None:
        self._clear_game()
        self._system_loaded(data)
        if data.games:
            self._pending_game_selection = next_row
        self.status.setText(self.translator("gamelist.deleted"))

    def _choose_image(self, kind: str) -> None:
        if self._data is None or self._game is None or self.busy:
            return
        filters = self.translator("gamelist.image_filter")
        filename, _ = QFileDialog.getOpenFileName(
            self, self.translator("gamelist.select_image"), "", filters
        )
        if not filename:
            return
        reader = QImageReader(filename)
        if not reader.canRead():
            show_error(
                self,
                self.translator("gamelist.error_title"),
                self.translator("gamelist.invalid_image"),
            )
            return
        local_path = Path(filename)
        data = self._data
        self.status.setText(self.translator("gamelist.uploading"))
        self._start(
            lambda: self.repository.upload_image(data, local_path, kind),
            lambda relative: self._upload_completed(kind, relative, local_path),
        )

    def _select_rom_file(self) -> None:
        if self._data is None or self.busy:
            return
        dialog = RemoteFileDialog(
            self.connection,
            self._data.system_path,
            self.translator,
            self,
        )
        if dialog.exec():
            self.path_edit.setText(dialog.selected_path)

    def _select_remote_media(self, kind: str) -> None:
        if self._data is None or self.busy:
            return
        media_root = posixpath.join(self._data.system_path, "media")
        dialog = RemoteFileDialog(
            self.connection,
            media_root,
            self.translator,
            self,
            allowed_extensions=IMAGE_EXTENSIONS,
            title_key="gamelist.media_browser_title",
        )
        if not dialog.exec():
            return
        relative_path = posixpath.join("media", dialog.selected_path)
        data = self._data
        self._operation_kind = "select_media"
        self.status.setText(self.translator("gamelist.loading_media"))
        self._start(
            lambda: self.repository.read_media(data, relative_path),
            lambda content: self._remote_media_selected(
                kind, relative_path, content
            ),
        )

    def _remote_media_selected(
        self, kind: str, relative_path: str, content: bytes
    ) -> None:
        field = self.image_field if kind == "image" else self.thumbnail_field
        field.set_text(relative_path)
        field.set_preview(content)
        self.status.setText(self.translator("gamelist.media_selected"))
        self._update_media_delete_buttons()

    def _upload_completed(self, kind: str, relative: str, local_path: Path) -> None:
        field = self.image_field if kind == "image" else self.thumbnail_field
        field.set_text(relative)
        field.set_preview(local_path.read_bytes())
        if self._data is not None:
            remote_path = posixpath.join(self._data.system_path, relative)
            self.connection.register_cleanup_paths(remote_path)
            self._pending_uploads.add(remote_path)
        self.status.setText(self.translator("gamelist.uploaded"))
        self._update_media_delete_buttons()

    def delete_media(self, kind: str) -> None:
        if self._data is None or self._game is None or self._new_game or self.busy:
            return
        relative_path = self._game.values.get(kind, "").strip()
        if not relative_path:
            return
        if not ask_confirmation(
            self,
            self.translator("gamelist.delete_media_title"),
            self.translator("gamelist.delete_media_confirm", path=relative_path),
        ):
            return
        data, game = self._data, self._game
        self._operation_kind = "delete_media"
        self.status.setText(self.translator("gamelist.deleting_media"))
        self._start(
            lambda: self.repository.delete_media(data, game, kind),
            lambda updated: self._media_deleted(updated, game.index, kind),
        )

    def _media_deleted(
        self, data: GameListData, game_index: int, kind: str
    ) -> None:
        self._data = data
        self._game = data.games[game_index]
        field = self.image_field if kind == "image" else self.thumbnail_field
        field.set_text("")
        field.set_preview(b"")
        current_item = self.games_list.currentItem()
        if current_item is not None and kind == "image":
            current_item.setData(1, Qt.ItemDataRole.UserRole, False)
            current_item.setText(1, self.translator("common.no"))
        self.status.setText(self.translator("gamelist.media_deleted"))
        self._update_media_delete_buttons()

    def _form_values(self) -> dict[str, str]:
        return {
            "path": self.path_edit.text(),
            "name": self.name_edit.text(),
            "aliases": self.aliases_edit.text(),
            "genre": self.genre_edit.text(),
            "genreid": self.genreid_edit.text(),
            "publisher": self.publisher_edit.text(),
            "developer": self.developer_edit.text(),
            "desc": self.description_edit.toPlainText(),
            "image": self.image_field.text(),
            "thumbnail": self.thumbnail_field.text(),
        }

    def _clear_game(self) -> None:
        self._game = None
        self._new_game = False
        for edit in (
            self.path_edit,
            self.name_edit,
            self.aliases_edit,
            self.genre_edit,
            self.genreid_edit,
            self.publisher_edit,
            self.developer_edit,
        ):
            edit.clear()
        self.description_edit.clear()
        self.hidden_check.setChecked(False)
        self.image_field.set_text("")
        self.thumbnail_field.set_text("")
        self.image_field.set_preview(b"")
        self.thumbnail_field.set_preview(b"")
        self._set_editor_enabled(False)
        self._update_actions()
        self._update_media_delete_buttons()

    def _set_editor_enabled(self, enabled: bool) -> None:
        self.editor_body.setEnabled(enabled and not self.busy)
        self.reload_button.setEnabled(enabled and not self._new_game and not self.busy)
        self.save_button.setEnabled(enabled and not self.busy)

    def _update_actions(self) -> None:
        self.new_button.setEnabled(self._data is not None and not self.busy)
        self.delete_button.setEnabled(self._game is not None and not self.busy)

    def _update_media_delete_buttons(self) -> None:
        for kind, field in (
            ("image", self.image_field),
            ("thumbnail", self.thumbnail_field),
        ):
            stored = self._game.values.get(kind, "") if self._game is not None else ""
            allowed = (
                not self.busy
                and not self._new_game
                and bool(stored.strip())
                and field.text().strip() == stored.strip()
            )
            field.set_delete_enabled(allowed)

    def _start(self, operation, success) -> None:
        if self.busy:
            return
        thread = QThread(self)
        worker = RemoteCallAttempt(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        # Conectar siempre a un método del widget garantiza que Qt entregue el
        # resultado en el hilo de la interfaz. Una lambda conectada directamente
        # puede ejecutarse en el hilo remoto y tocar widgets, provocando SIGSEGV.
        self._success_callback = success
        worker.succeeded.connect(self._operation_succeeded)
        worker.failed.connect(self._operation_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._operation_finished)
        self._thread = thread
        self._worker = worker
        self.systems_list.setEnabled(False)
        self.games_list.setEnabled(False)
        self._set_editor_enabled(self._game is not None)
        self._update_actions()
        self._update_media_delete_buttons()
        thread.start()

    def _operation_succeeded(self, result: object) -> None:
        callback = self._success_callback
        if callback is not None:
            callback(result)

    def _operation_failed(self, error: Exception) -> None:
        if (
            isinstance(error, GameListValidationError)
            and error.key == "gamelist.no_gamelist"
            and self._operation_kind == "load_system"
            and self._requested_system
        ):
            system = self._requested_system
            self._after_finish = lambda: self._prompt_create_gamelist(system)
            return
        if isinstance(error, GameListValidationError):
            message = self.translator(error.key, **error.values)
        elif isinstance(error, RemoteFileChangedError):
            message = self.translator("gamelist.concurrent_change")
        elif isinstance(error, FileNotFoundError):
            message = self.translator("gamelist.no_gamelist")
        else:
            message = self.translator("gamelist.remote_error", detail=str(error))
        self.status.setText(message)
        show_error(self, self.translator("gamelist.error_title"), message)

    def _prompt_create_gamelist(self, system: str) -> None:
        if not ask_confirmation(
            self,
            self.translator("gamelist.create_title"),
            self.translator("gamelist.create_question"),
        ):
            self.status.setText(self.translator("gamelist.no_gamelist"))
            return
        self._operation_kind = "create_gamelist"
        self.status.setText(self.translator("gamelist.creating"))
        self._start(
            lambda: self.repository.create_empty(system),
            self._gamelist_created,
        )

    def _gamelist_created(self, data: GameListData) -> None:
        self._system_loaded(data)
        self.status.setText(self.translator("gamelist.created"))

    def _operation_finished(self) -> None:
        after_finish, self._after_finish = self._after_finish, None
        self._thread = None
        self._worker = None
        self._success_callback = None
        self.systems_list.setEnabled(True)
        self.games_list.setEnabled(self._data is not None)
        self._set_editor_enabled(self._game is not None)
        self._update_actions()
        self._update_media_delete_buttons()
        if self._pending_game_selection is not None:
            selected_index, self._pending_game_selection = (
                self._pending_game_selection,
                None,
            )
            for row in range(self.games_list.topLevelItemCount()):
                item = self.games_list.topLevelItem(row)
                if int(item.data(0, Qt.ItemDataRole.UserRole)) == selected_index:
                    self.games_list.setCurrentItem(item)
                    break
        if after_finish is not None:
            QTimer.singleShot(0, after_finish)
        elif self._restore_games_focus and self.games_list.currentItem() is not None:
            self._restore_games_focus = False
            self.games_list.setFocus(Qt.FocusReason.OtherFocusReason)

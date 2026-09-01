from __future__ import annotations

from PySide6.QtGui import QAction, QActionGroup, QCloseEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QStackedWidget, QTabWidget

from .components import EmptyState, EnvironmentPage
from .connection import ConnectionManager, RecalboxConnection
from .dialogs import AboutDialog, EnvironmentsDialog
from .i18n import Translator
from .models import RecalboxEnvironment
from .paths import AppPaths
from .settings import UserSettings
from .themes import Theme
from .utils import ask_confirmation, show_error, show_information


class MainWindow(QMainWindow):
    def __init__(self, translator: Translator, settings: UserSettings, themes: dict[str, Theme]) -> None:
        super().__init__()
        self.translator = translator
        self.settings = settings
        self.themes = themes
        self._allow_close = False
        self._environment_names: dict[str, str] = {}

        known_hosts = AppPaths.discover().data / "ssh" / "known_hosts"
        self.connection_manager = ConnectionManager(known_hosts, self)
        self.connection_manager.connected.connect(self._connection_succeeded)
        self.connection_manager.failed.connect(self._connection_failed)
        self.connection_manager.attemptFinished.connect(
            self._connection_attempt_finished
        )
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.connection_manager.close_all)

        self.resize(1100, 720)
        self.home = EmptyState("", "")
        self.environment_tabs = QTabWidget()
        self.environment_tabs.setTabsClosable(True)
        self.environment_tabs.setMovable(True)
        self.environment_tabs.tabCloseRequested.connect(self._close_environment_tab)
        self.workspace = QStackedWidget()
        self.workspace.addWidget(self.home)
        self.workspace.addWidget(self.environment_tabs)
        self.setCentralWidget(self.workspace)

        self._create_actions()
        self._create_menus()
        self.retranslate_ui()

    def restore_saved_geometry(self) -> bool:
        geometry = self.settings.window_geometry()
        return bool(geometry is not None and self.restoreGeometry(geometry))

    def _create_actions(self) -> None:
        self.environments_action = QAction(self)
        self.environments_action.triggered.connect(self._manage_environments)
        self.about_action = QAction(self)
        self.about_action.triggered.connect(self._show_about)
        self.exit_action = QAction(self)
        self.exit_action.triggered.connect(self.close)

    def _create_menus(self) -> None:
        self.application_menu = self.menuBar().addMenu("")
        self.preferences_menu = QMenu(self)
        self.language_menu = QMenu(self)
        self.theme_menu = QMenu(self)
        self.connect_menu = QMenu(self)
        self.preferences_menu.addMenu(self.language_menu)
        self.preferences_menu.addMenu(self.theme_menu)
        self.application_menu.addAction(self.environments_action)
        self.application_menu.addMenu(self.connect_menu)
        self.application_menu.addSeparator()
        self.application_menu.addMenu(self.preferences_menu)
        self.application_menu.addSeparator()
        self.application_menu.addAction(self.about_action)
        self.application_menu.addSeparator()
        self.application_menu.addAction(self.exit_action)

    def retranslate_ui(self) -> None:
        tr = self.translator
        self.setWindowTitle(tr("app.name"))
        self.application_menu.setTitle(tr("menu.application"))
        self.preferences_menu.setTitle(tr("menu.preferences"))
        self.language_menu.setTitle(tr("menu.language"))
        self.theme_menu.setTitle(tr("menu.theme"))
        self.environments_action.setText(tr("menu.environments"))
        self.connect_menu.setTitle(tr("menu.connect"))
        self.about_action.setText(tr("menu.about"))
        self.exit_action.setText(tr("menu.exit"))
        self.home.set_content(tr("home.title"), tr("home.description"))
        self.statusBar().showMessage(tr("app.ready"))
        for index in range(self.environment_tabs.count()):
            page = self.environment_tabs.widget(index)
            if isinstance(page, EnvironmentPage):
                page.retranslate_ui()
        self._rebuild_language_menu()
        self._rebuild_theme_menu()
        self._rebuild_connect_menu()

    def _rebuild_language_menu(self) -> None:
        self.language_menu.clear()
        group = QActionGroup(self.language_menu)
        group.setExclusive(True)
        for code, language in sorted(self.translator.languages.items()):
            action = self.language_menu.addAction(language.name)
            action.setCheckable(True)
            action.setChecked(code == self.translator.language)
            action.triggered.connect(lambda checked=False, value=code: self._select_language(value))
            group.addAction(action)

    def _rebuild_theme_menu(self) -> None:
        self.theme_menu.clear()
        group = QActionGroup(self.theme_menu)
        group.setExclusive(True)
        for identifier, theme in self.themes.items():
            action = self.theme_menu.addAction(theme.display_name(self.translator.language))
            action.setCheckable(True)
            action.setChecked(identifier == self.settings.theme)
            action.triggered.connect(lambda checked=False, value=identifier: self._select_theme(value))
            group.addAction(action)

    def _rebuild_connect_menu(self) -> None:
        self.connect_menu.clear()
        environments = self.settings.environments()
        self._environment_names.update({item.identifier: item.name for item in environments})
        if not environments:
            action = self.connect_menu.addAction(self.translator("menu.no_environments"))
            action.setEnabled(False)
            return
        for environment in environments:
            unavailable = (
                self.connection_manager.is_connected(environment.identifier)
                or self.connection_manager.is_pending(environment.identifier)
            )
            action = self.connect_menu.addAction(environment.name)
            action.setCheckable(True)
            action.setChecked(unavailable)
            action.setEnabled(not unavailable)
            action.triggered.connect(lambda checked=False, item=environment: self._connect_environment(item))

    def _select_language(self, code: str) -> None:
        if code == self.translator.language:
            return
        self.translator.language = code
        self.settings.language = code
        self.settings.sync()
        self.retranslate_ui()

    def _select_theme(self, identifier: str) -> None:
        theme = self.themes.get(identifier)
        app = QApplication.instance()
        if theme is None or app is None:
            return
        app.setStyleSheet(theme.stylesheet)
        self.settings.theme = identifier
        self.settings.sync()
        self._rebuild_theme_menu()

    def _manage_environments(self) -> None:
        dialog = EnvironmentsDialog(self.translator, self.settings.environments(), self)
        if dialog.exec():
            self.settings.save_environments(dialog.environments)
            self._rebuild_connect_menu()

    def _connect_environment(self, environment: RecalboxEnvironment) -> None:
        identifier = environment.identifier
        if self.connection_manager.is_connected(
            identifier
        ) or self.connection_manager.is_pending(identifier):
            return
        self._environment_names[identifier] = environment.name
        self.statusBar().showMessage(self.translator("connection.connecting", name=environment.name))
        self.connection_manager.connect_environment(environment)
        self._rebuild_connect_menu()

    def _connection_succeeded(self, identifier: str, connection: RecalboxConnection) -> None:
        page = EnvironmentPage(connection, self.translator)
        page.recalboxRestartScheduled.connect(
            lambda current=page: self._close_restarting_environment(current)
        )
        page.recalboxShutdownScheduled.connect(
            lambda current=page: self._close_restarting_environment(current)
        )
        index = self.environment_tabs.addTab(page, connection.environment.name)
        self.environment_tabs.setCurrentIndex(index)
        self.workspace.setCurrentWidget(self.environment_tabs)
        self.statusBar().showMessage(
            self.translator("connection.connected", name=connection.environment.name)
        )

    def _connection_failed(self, identifier: str, error_key: str, detail: str) -> None:
        name = self._environment_names.get(identifier, identifier)
        reason = self.translator(error_key, detail=detail)
        show_error(
            self,
            self.translator("connection.error_title"),
            self.translator("connection.error_message", name=name, reason=reason),
        )

    def _connection_attempt_finished(self, identifier: str) -> None:
        self._rebuild_connect_menu()
        if not self.connection_manager.is_connected(identifier):
            self.statusBar().showMessage(self.translator("app.ready"))

    def _close_environment_tab(self, index: int) -> None:
        page = self.environment_tabs.widget(index)
        if not isinstance(page, EnvironmentPage):
            return
        if page.busy:
            show_information(
                self,
                self.translator("utility.busy_title"),
                self.translator("utility.busy_close_message"),
            )
            return
        if not ask_confirmation(
            self,
            self.translator("connection.close_title"),
            self.translator("connection.close_confirm", name=page.environment_name),
        ):
            return
        self.connection_manager.close_connection(page.environment_identifier)
        self.environment_tabs.removeTab(index)
        page.deleteLater()
        self._rebuild_connect_menu()
        if self.environment_tabs.count() == 0:
            self.workspace.setCurrentWidget(self.home)
            self.statusBar().showMessage(self.translator("app.ready"))

    def _close_restarting_environment(self, page: EnvironmentPage) -> None:
        index = self.environment_tabs.indexOf(page)
        if index < 0:
            return
        self.connection_manager.close_connection(page.environment_identifier)
        self.environment_tabs.removeTab(index)
        page.deleteLater()
        self._rebuild_connect_menu()
        if self.environment_tabs.count() == 0:
            self.workspace.setCurrentWidget(self.home)
        self.statusBar().showMessage(self.translator("app.ready"))

    def _show_about(self) -> None:
        AboutDialog(self.translator, self).exec()

    def _close_connections(self) -> None:
        self.connection_manager.close_all()

    def closeEvent(self, event: QCloseEvent) -> None:
        utility_running = any(
            isinstance(self.environment_tabs.widget(index), EnvironmentPage)
            and self.environment_tabs.widget(index).busy
            for index in range(self.environment_tabs.count())
        )
        if self.connection_manager.has_pending_attempts or utility_running:
            show_information(
                self,
                self.translator("connection.wait_title"),
                self.translator(
                    "utility.wait_message" if utility_running else "connection.wait_message"
                ),
            )
            event.ignore()
            return
        if self._allow_close:
            self._close_connections()
            self.settings.save_window_geometry(self.saveGeometry())
            event.accept()
            return
        if ask_confirmation(self, self.translator("exit.title"), self.translator("exit.confirm")):
            self._allow_close = True
            self._close_connections()
            self.settings.save_window_geometry(self.saveGeometry())
            event.accept()
        else:
            event.ignore()

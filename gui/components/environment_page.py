from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from ..connection import RecalboxConnection
from ..i18n import Translator
from .utilities_page import UtilitiesPage


class EnvironmentPage(QWidget):
    recalboxRestartScheduled = Signal()
    recalboxShutdownScheduled = Signal()

    def __init__(self, connection: RecalboxConnection, translator: Translator, parent=None) -> None:
        super().__init__(parent)
        environment = connection.environment
        self.environment_identifier = environment.identifier
        self.environment_name = environment.name
        self._translator = translator
        self.tabs = QTabWidget()
        self.utilities_page = UtilitiesPage(connection, translator)
        self.utilities_page.recalboxRestartScheduled.connect(
            self.recalboxRestartScheduled.emit
        )
        self.utilities_page.recalboxShutdownScheduled.connect(
            self.recalboxShutdownScheduled.emit
        )
        self.tabs.addTab(self.utilities_page, "")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)
        self.retranslate_ui()

    @property
    def busy(self) -> bool:
        return self.utilities_page.busy

    def retranslate_ui(self) -> None:
        self.tabs.setTabText(0, self._translator("environment.utilities_tab"))
        self.utilities_page.retranslate_ui()

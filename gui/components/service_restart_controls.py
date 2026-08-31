from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ..i18n import Translator


class ServiceRestartControls(QWidget):
    restartEmulationStationRequested = Signal()
    restartRecalboxRequested = Signal()
    shutdownRecalboxRequested = Signal()

    def __init__(self, translator: Translator, parent=None) -> None:
        super().__init__(parent)
        self.translator = translator
        self.emulationstation_description = QLabel()
        self.emulationstation_description.setWordWrap(True)
        self.emulationstation_button = QPushButton()
        self.recalbox_description = QLabel()
        self.recalbox_description.setWordWrap(True)
        self.recalbox_button = QPushButton()
        self.recalbox_button.setProperty("danger", True)
        self.shutdown_description = QLabel()
        self.shutdown_description.setWordWrap(True)
        self.shutdown_button = QPushButton()
        self.shutdown_button.setProperty("danger", True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.emulationstation_description)
        layout.addWidget(self.emulationstation_button)
        layout.addSpacing(14)
        layout.addWidget(self.recalbox_description)
        layout.addWidget(self.recalbox_button)
        layout.addSpacing(14)
        layout.addWidget(self.shutdown_description)
        layout.addWidget(self.shutdown_button)
        layout.addStretch()

        self.emulationstation_button.clicked.connect(
            self.restartEmulationStationRequested
        )
        self.recalbox_button.clicked.connect(self.restartRecalboxRequested)
        self.shutdown_button.clicked.connect(self.shutdownRecalboxRequested)
        self.retranslate_ui()

    def set_busy(self, busy: bool) -> None:
        self.emulationstation_button.setEnabled(not busy)
        self.recalbox_button.setEnabled(not busy)
        self.shutdown_button.setEnabled(not busy)

    def retranslate_ui(self) -> None:
        tr = self.translator
        self.emulationstation_description.setText(
            tr("utility.services.emulationstation_description")
        )
        self.emulationstation_button.setText(
            tr("utility.services.restart_emulationstation")
        )
        self.recalbox_description.setText(
            tr("utility.services.recalbox_description")
        )
        self.recalbox_button.setText(tr("utility.services.restart_recalbox"))
        self.shutdown_description.setText(
            tr("utility.services.shutdown_description")
        )
        self.shutdown_button.setText(tr("utility.services.shutdown_recalbox"))

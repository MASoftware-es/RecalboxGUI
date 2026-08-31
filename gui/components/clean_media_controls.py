from PySide6.QtCore import Signal
from PySide6.QtWidgets import QProgressBar, QPushButton, QVBoxLayout, QWidget

from ..i18n import Translator
from .directory_checklist import DirectoryChecklist


class CleanMediaControls(QWidget):
    testRequested = Signal()
    executeRequested = Signal()

    def __init__(self, translator: Translator, parent=None) -> None:
        super().__init__(parent)
        self.translator = translator
        self.directories = DirectoryChecklist(translator)
        self.test_button = QPushButton()
        self.execute_button = QPushButton()
        self.execute_button.setProperty("danger", True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.directories.button_layout.addWidget(self.test_button)
        self.directories.button_layout.addWidget(self.execute_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.directories)
        layout.addWidget(self.progress)
        self.test_button.clicked.connect(self.testRequested)
        self.execute_button.clicked.connect(self.executeRequested)
        self.directories.selectionChanged.connect(self._update_actions)
        self.retranslate_ui()
        self.set_busy(False)

    def selected_directories(self) -> list[str]:
        return self.directories.selected_directories()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.directories.set_controls_enabled(not busy)
        self._update_actions()

    def reset_progress(self) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

    def set_progress_plan(self, total: int) -> None:
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(0)

    def set_progress_value(self, value: int) -> None:
        self.progress.setValue(min(value, self.progress.maximum()))

    def _update_actions(self) -> None:
        enabled = bool(self.selected_directories()) and not self._busy
        self.test_button.setEnabled(enabled)
        self.execute_button.setEnabled(enabled)

    def retranslate_ui(self) -> None:
        self.directories.retranslate_ui()
        self.test_button.setText(self.translator("utility.test"))
        self.execute_button.setText(self.translator("utility.execute"))

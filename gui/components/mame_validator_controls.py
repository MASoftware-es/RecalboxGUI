from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QProgressBar, QPushButton, QVBoxLayout, QWidget

from ..i18n import Translator


class RomValidatorControls(QWidget):
    analyzeRequested = Signal()
    correctRequested = Signal()
    openFolderRequested = Signal()

    def __init__(
        self, translator: Translator, translation_prefix: str, parent=None
    ) -> None:
        super().__init__(parent)
        self.translator = translator
        self.translation_prefix = translation_prefix
        self._busy = False
        self._report_ready = False
        self.analyze_button = QPushButton()
        self.correct_button = QPushButton()
        self.open_folder_button = QPushButton()
        self.correct_button.setProperty("danger", True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

        center_buttons = QWidget()
        center_layout = QHBoxLayout(center_buttons)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(self.analyze_button)
        center_layout.addWidget(self.correct_button)
        self.button_layout = QGridLayout()
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setColumnStretch(0, 1)
        self.button_layout.setColumnStretch(2, 1)
        self.button_layout.addWidget(center_buttons, 0, 1)
        self.button_layout.addWidget(
            self.open_folder_button, 0, 2, alignment=Qt.AlignmentFlag.AlignRight
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.addLayout(self.button_layout)
        layout.addWidget(self.progress)

        self.analyze_button.clicked.connect(self.analyzeRequested)
        self.correct_button.clicked.connect(self.correctRequested)
        self.open_folder_button.clicked.connect(self.openFolderRequested)
        self.retranslate_ui()
        self._update_actions()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_actions()

    def set_report_ready(self, ready: bool) -> None:
        self._report_ready = ready
        self._update_actions()

    def reset_progress(self) -> None:
        self.progress.setRange(0, 0)

    def set_progress_plan(self, total: int) -> None:
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(0)

    def set_progress_value(self, value: int) -> None:
        if self.progress.maximum() == 0:
            return
        self.progress.setValue(min(value, self.progress.maximum()))

    def _update_actions(self) -> None:
        self.analyze_button.setEnabled(not self._busy)
        self.correct_button.setEnabled(not self._busy and self._report_ready)
        self.open_folder_button.setEnabled(not self._busy)

    def retranslate_ui(self) -> None:
        prefix = self.translation_prefix
        self.analyze_button.setText(self.translator(f"{prefix}.analyze"))
        self.correct_button.setText(self.translator(f"{prefix}.correct"))
        self.open_folder_button.setText(
            self.translator(f"{prefix}.open_folder")
        )
        side_width = self.open_folder_button.sizeHint().width()
        self.button_layout.setColumnMinimumWidth(0, side_width)
        self.button_layout.setColumnMinimumWidth(2, side_width)
        self.progress.setFormat(self.translator(f"{prefix}.progress"))

    def set_translation_prefix(self, prefix: str) -> None:
        self.translation_prefix = prefix
        self.retranslate_ui()


class MameValidatorControls(RomValidatorControls):
    """Alias compatible para código externo anterior."""

    def __init__(self, translator: Translator, parent=None) -> None:
        super().__init__(translator, "utility.mame", parent)

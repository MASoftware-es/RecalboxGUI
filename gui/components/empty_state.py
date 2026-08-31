from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .page_title import PageTitle


class EmptyState(QWidget):
    def __init__(self, title: str, description: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addStretch()
        self.title_label = PageTitle(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label = QLabel(description)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label.setWordWrap(True)
        self.description_label.setProperty("role", "muted")
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addStretch()

    def set_content(self, title: str, description: str) -> None:
        self.title_label.setText(title)
        self.description_label.setText(description)

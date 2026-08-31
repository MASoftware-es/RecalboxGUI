from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialogButtonBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import PROJECT_LAST_MODIFIED, __version__
from ..assets import APP_ICON_PATH
from ..i18n import Translator
from .base_dialog import ModalDialog


class AboutDialog(ModalDialog):
    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("dialogSound", True)
        self.setWindowTitle(translator("about.title"))
        self.setModal(True)
        self.setMinimumWidth(430)

        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        pixmap = QPixmap(str(APP_ICON_PATH))
        icon.setPixmap(
            pixmap.scaled(
                128,
                128,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        content = QLabel(
            translator(
                "about.content",
                version=__version__,
                date=PROJECT_LAST_MODIFIED,
            )
        )
        content.setTextFormat(Qt.TextFormat.RichText)
        content.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        content.setOpenExternalLinks(True)
        content.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        body = QHBoxLayout()
        body.setSpacing(24)
        body.addWidget(icon)
        body.addWidget(content, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(translator("common.close"))
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(body)
        layout.addWidget(buttons)

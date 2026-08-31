from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import __version__
from .assets import APP_ICON_PATH
from .dialog_sound import DialogSoundEventFilter
from .i18n import Translator, discover_languages
from .main_window import MainWindow
from .paths import AppPaths
from .settings import UserSettings
from .themes import discover_themes
from .utils import configure_dialog_translation


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("RecalboxGUI")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("RecalboxGUI")
    app.setWindowIcon(QIcon(str(APP_ICON_PATH)))

    dialog_sound_filter = DialogSoundEventFilter(app)
    app.installEventFilter(dialog_sound_filter)

    AppPaths.discover().ensure()

    settings = UserSettings()
    translator = Translator(discover_languages(), settings.language)
    configure_dialog_translation(translator)
    themes = discover_themes()
    theme = themes.get(settings.theme) or themes.get("default")
    if theme:
        app.setStyleSheet(theme.stylesheet)

    window = MainWindow(translator, settings, themes)
    if not window.restore_saved_geometry():
        screen = app.primaryScreen()
        if screen is not None:
            frame = window.frameGeometry()
            frame.moveCenter(screen.availableGeometry().center())
            window.move(frame.topLeft())
    window.show()
    return app.exec()

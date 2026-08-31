from PySide6.QtWidgets import QLabel


class PageTitle(QLabel):
    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("pageTitle")

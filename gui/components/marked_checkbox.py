from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton


class MarkedCheckBox(QCheckBox):
    """Checkbox tematizable que conserva una marca visible al seleccionarlo."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self.isChecked():
            return

        option = QStyleOptionButton()
        self.initStyleOption(option)
        indicator = self.style().subElementRect(
            QStyle.SubElement.SE_CheckBoxIndicator, option, self
        )
        if not indicator.isValid():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#ffffff"))
        pen.setWidthF(max(1.8, indicator.width() / 7.0))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        left = indicator.left()
        top = indicator.top()
        width = indicator.width()
        height = indicator.height()
        painter.drawPolyline(
            [
                QPointF(left + width * 0.22, top + height * 0.52),
                QPointF(left + width * 0.43, top + height * 0.73),
                QPointF(left + width * 0.79, top + height * 0.28),
            ]
        )

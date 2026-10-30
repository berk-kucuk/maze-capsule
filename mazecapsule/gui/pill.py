"""Fully rounded status pills.

Painted, not styled: Qt drops `border-radius` altogether when it exceeds half
the widget's height, which is exactly what a pill needs, so a QSS pill renders
as a sharp-cornered box at most font sizes.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

# variant → (fill, text, border, dashed)
_STYLES = {
    "installed": ("rgba(255,255,255,0.05)", "#b4b4ba", "rgba(255,255,255,0.12)", False),
    "update":    ("#f2f2f4",                "#000000", "#f2f2f4",                False),
    "busy":      ("rgba(255,255,255,0.0)",  "#bdbdc2", "rgba(255,255,255,0.45)", True),
    "local":     ("rgba(255,255,255,0.04)", "#9a9a9f", "rgba(255,255,255,0.12)", False),
    "chip":      ("rgba(255,255,255,0.04)", "#cfcfd4", "rgba(255,255,255,0.09)", False),
}


def _color(spec: str) -> QColor:
    if spec.startswith("rgba("):
        r, g, b, a = (float(x) for x in spec[5:-1].split(","))
        c = QColor(int(r), int(g), int(b))
        c.setAlphaF(a)
        return c
    return QColor(spec)


class Pill(QWidget):
    def __init__(self, text: str, variant: str = "installed", size: str = "small",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._text = text
        self._variant = variant
        self._font = QFont(self.font())
        if size == "small":
            self._font.setPixelSize(10)
            self._font.setBold(True)
            self._font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
            self._h, self._pad = 20, 9
        else:
            self._font.setPixelSize(12)
            self._font.setWeight(QFont.Weight.DemiBold)
            self._h, self._pad = 30, 14
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(self.sizeHint())

    def sizeHint(self) -> QSize:
        w = QFontMetrics(self._font).horizontalAdvance(self._text)
        return QSize(w + 2 * self._pad + 2, self._h)

    def paintEvent(self, _ev) -> None:
        fill, text, border, dashed = _STYLES.get(self._variant, _STYLES["installed"])
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(path, _color(fill))
        pen = QPen(_color(border), 1.0)
        if dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawPath(path)
        p.setPen(_color(text))
        p.setFont(self._font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)
        p.end()

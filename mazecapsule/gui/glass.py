"""Glass surfaces.

Glassmorphism needs something behind the glass. The window background is still
OLED black almost everywhere, with a few large, very soft fields of white
light — monochrome, like the rest of Maze — that the translucent
panels sit on. The fields are radial gradients, so they are already as blurred
as a frosted pane would make them — no live blur pass is needed, which keeps
scrolling cheap.

Panels are painted rather than styled: QSS cannot give one rounded border a
gradient that is bright along the top edge and fades down the sides, and that
rim of light is most of what makes a pane read as glass.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen,
                         QPixmap, QRadialGradient)
from PyQt6.QtWidgets import QFrame, QWidget

# (x, y, radius) as fractions of the window, colour, peak alpha
_ORBS = [
    ((0.12, 0.00, 0.55), "#ffffff", 0.055),
    ((0.95, 0.25, 0.50), "#ffffff", 0.035),
    ((0.60, 1.05, 0.60), "#ffffff", 0.03),
]


class GlassBackground(QWidget):
    """Black window background with soft light fields behind the glass."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("root")
        self._cache: QPixmap | None = None

    def resizeEvent(self, ev) -> None:
        self._cache = None
        super().resizeEvent(ev)

    def _render(self) -> QPixmap:
        w, h = max(1, self.width()), max(1, self.height())
        dpr = self.devicePixelRatioF()
        pm = QPixmap(int(w * dpr), int(h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(QColor("#000000"))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        span = max(w, h)
        for (fx, fy, fr), colour, alpha in _ORBS:
            c = QPointF(fx * w, fy * h)
            r = fr * span
            g = QRadialGradient(c, r)
            base = QColor(colour)
            for stop, a in ((0.0, alpha), (0.35, alpha * 0.45), (0.7, alpha * 0.12), (1.0, 0.0)):
                col = QColor(base)
                col.setAlphaF(a)
                g.setColorAt(stop, col)
            p.fillRect(QRectF(0, 0, w, h), QBrush(g))
        p.end()
        return pm

    def paintEvent(self, _ev) -> None:
        if self._cache is None or self._cache.size() != self.size() * self.devicePixelRatioF():
            self._cache = self._render()
        p = QPainter(self)
        p.drawPixmap(0, 0, self._cache)


class GlassFrame(QFrame):
    """A translucent rounded pane with a light rim.

    tint: optional colour mixed into the fill (the hero uses white, for a brighter pane).
    interactive: brightens on hover, for clickable cards.
    """

    def __init__(self, radius: float = 16, tint: str | None = None,
                 interactive: bool = False, strength: float = 1.0,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._radius = radius
        self._tint = QColor(tint) if tint else None
        self._interactive = interactive
        self._strength = strength
        self._hover = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, interactive)
        # No setStyleSheet() here: a sheet set on this widget cascades into
        # every child and strips the buttons and pills inside the card. A bare
        # QFrame with no frame shape draws nothing, so paintEvent is all of it.

    def enterEvent(self, ev) -> None:
        if self._interactive:
            self._hover = True
            self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev) -> None:
        if self._interactive:
            self._hover = False
            self.update()
        super().leaveEvent(ev)

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, self._radius, self._radius)

        k = self._strength * (1.7 if self._hover else 1.0)

        # Body: a little more light top-left than bottom-right, like a pane
        # catching an overhead source.
        fill = QLinearGradient(r.topLeft(), r.bottomRight())
        top = QColor(self._tint) if self._tint else QColor(255, 255, 255)
        top.setAlphaF(min(1.0, (0.055 if self._tint else 0.038) * k))
        bottom = QColor(255, 255, 255)
        bottom.setAlphaF(min(1.0, 0.008 * k))
        fill.setColorAt(0.0, top)
        fill.setColorAt(1.0, bottom)
        # A dark base under the light so text stays legible over the bright
        # parts of the background.
        p.fillPath(path, QColor(0, 0, 0, 170))
        p.fillPath(path, QBrush(fill))

        # Sheen: a thin band of reflected light across the top.
        sheen = QLinearGradient(r.topLeft(), QPointF(r.left(), r.top() + min(60.0, r.height() * 0.5)))
        s0 = QColor(255, 255, 255)
        s0.setAlphaF(0.025 * k)
        s1 = QColor(255, 255, 255, 0)
        sheen.setColorAt(0.0, s0)
        sheen.setColorAt(1.0, s1)
        p.fillPath(path, QBrush(sheen))

        # Rim: bright along the top edge, fading down the sides.
        rim = QLinearGradient(r.topLeft(), r.bottomLeft())
        c0 = QColor(255, 255, 255)
        c0.setAlphaF(min(1.0, 0.13 * k))
        c1 = QColor(255, 255, 255)
        c1.setAlphaF(min(1.0, 0.035 * k))
        c2 = QColor(self._tint) if self._tint else QColor(255, 255, 255)
        c2.setAlphaF(min(1.0, (0.07 if self._tint else 0.045) * k))
        rim.setColorAt(0.0, c0)
        rim.setColorAt(0.5, c1)
        rim.setColorAt(1.0, c2)
        p.setPen(QPen(QBrush(rim), 1.0))
        p.drawPath(path)
        p.end()

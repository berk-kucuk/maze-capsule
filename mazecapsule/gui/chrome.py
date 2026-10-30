"""Window chrome shared by the main window: frameless title bar, window
buttons and edge resizing — the same as Maze Store, Maze Donate and Maze Cloak.
"""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QSize, QTimer, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QWidget

from mazecapsule.gui.glyphs import glyph
from mazecapsule.gui.i18n import t

_RESIZE_MARGIN = 6


def label(text: str, name: str, wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


def button(text: str, name: str, icon: str | None = None, icon_color: str | None = None,
           tip: str | None = None) -> QPushButton:
    b = QPushButton(text, objectName=name)
    if icon:
        colour = icon_color or ("#000000" if name in ("get", "get_lg") else
                                "#bdbdc2" if name == "ghost" else "#f2f2f4")
        b.setIcon(glyph(icon, 15, colour))
        b.setIconSize(QSize(15, 15))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if tip:
        b.setToolTip(tip)
    return b


class TitleBar(QWidget):
    """Draggable header. startSystemMove() is what makes this work on Wayland."""

    def __init__(self, window: QWidget, name: str = "header"):
        super().__init__(objectName=name)
        self._window = window
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle:
                handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        w = self._window
        if event.button() == Qt.MouseButton.LeftButton and isinstance(w, QMainWindow):
            w.showNormal() if w.isMaximized() else w.showMaximized()
        super().mouseDoubleClickEvent(event)


class WindowButton(QPushButton):
    """─ □ ✕ as drawn glyphs; the close button inverts to black on white."""

    def __init__(self, kind: str, tooltip: str):
        super().__init__(objectName="win_close" if kind == "win_close" else "win_btn")
        self._kind = kind
        self.setToolTip(tooltip)
        self.setIconSize(QSize(16, 16))
        self._paint(False)

    def set_kind(self, kind: str) -> None:
        self._kind = kind
        self._paint(self.underMouse())

    def _paint(self, hover: bool) -> None:
        colour = "#000000" if hover and self._kind == "win_close" else (
            "#f2f2f4" if hover else "#9a9aa0")
        self.setIcon(glyph(self._kind, 16, colour))

    def enterEvent(self, ev) -> None:
        self._paint(True)
        super().enterEvent(ev)

    def leaveEvent(self, ev) -> None:
        self._paint(False)
        super().leaveEvent(ev)


class EdgeResizer(QObject):
    """Resize a frameless window from its edges (see Maze Store)."""

    def __init__(self, window: QMainWindow):
        super().__init__(window)
        self._w = window
        self._cursor_set = False

    def _edges(self, gpos) -> Qt.Edge:
        if self._w.isMaximized() or self._w.isFullScreen():
            return Qt.Edge(0)
        r = self._w.frameGeometry()
        m = _RESIZE_MARGIN
        e = Qt.Edge(0)
        if gpos.x() - r.left() < m:
            e |= Qt.Edge.LeftEdge
        if r.right() - gpos.x() < m:
            e |= Qt.Edge.RightEdge
        if gpos.y() - r.top() < m:
            e |= Qt.Edge.TopEdge
        if r.bottom() - gpos.y() < m:
            e |= Qt.Edge.BottomEdge
        return e

    @staticmethod
    def _shape(e: Qt.Edge) -> Qt.CursorShape | None:
        L, R, T, B = Qt.Edge.LeftEdge, Qt.Edge.RightEdge, Qt.Edge.TopEdge, Qt.Edge.BottomEdge
        if e in (L | T, R | B):
            return Qt.CursorShape.SizeFDiagCursor
        if e in (R | T, L | B):
            return Qt.CursorShape.SizeBDiagCursor
        if e & (L | R):
            return Qt.CursorShape.SizeHorCursor
        if e & (T | B):
            return Qt.CursorShape.SizeVerCursor
        return None

    def eventFilter(self, obj, ev) -> bool:
        t_ = ev.type()
        if t_ not in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress, QEvent.Type.HoverMove):
            return False
        if not isinstance(obj, QWidget) or obj.window() is not self._w:
            return False
        gpos = QCursor.pos()
        edges = self._edges(gpos)
        shape = self._shape(edges)
        if t_ == QEvent.Type.MouseButtonPress and shape is not None \
                and ev.button() == Qt.MouseButton.LeftButton:
            handle = self._w.windowHandle()
            if handle and handle.startSystemResize(edges):
                return True
        if shape is not None:
            if not self._cursor_set:
                QApplication.setOverrideCursor(shape)
                self._cursor_set = True
            else:
                QApplication.changeOverrideCursor(shape)
        elif self._cursor_set:
            QApplication.restoreOverrideCursor()
            self._cursor_set = False
        return False


class CopyButton(QPushButton):
    """Copies a value and says so for two seconds."""

    def __init__(self, text: str, value: str, primary: bool = False):
        super().__init__(text, objectName="get" if primary else "secondary")
        self._text = text
        self._value = value
        self._primary = primary
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(15, 15))
        self._set_icon("copy")
        self._reset = QTimer(self, singleShot=True, interval=2000)
        self._reset.timeout.connect(self._restore)
        self.clicked.connect(self._copy)

    def _set_icon(self, name: str) -> None:
        self.setIcon(glyph(name, 15, "#000000" if self._primary else "#f2f2f4"))

    def _copy(self) -> None:
        QApplication.clipboard().setText(self._value)
        if self._text:
            self.setText(t("btn_copied"))
        self._set_icon("check")
        self._reset.start()

    def _restore(self) -> None:
        self.setText(self._text)
        self._set_icon("copy")

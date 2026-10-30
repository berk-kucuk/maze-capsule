"""A wrapping layout: cards fill a row, then continue on the next.

Qt ships no flow layout. This one also stretches cards to share the row width
evenly, so a grid of fixed-minimum cards never leaves a ragged gap on the right.
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout, QLayoutItem, QWidget


class FlowLayout(QLayout):
    def __init__(self, parent: QWidget | None = None, spacing: int = 14,
                 min_item_width: int = 300):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._spacing = spacing
        self._min_w = min_item_width
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i: int) -> QLayoutItem | None:
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i: int) -> QLayoutItem | None:
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, apply=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        h = max((it.sizeHint().height() for it in self._items), default=0)
        return QSize(self._min_w, h)

    def _do_layout(self, rect: QRect, apply: bool) -> int:
        if not self._items:
            return 0
        sp = self._spacing
        cols = max(1, (rect.width() + sp) // (self._min_w + sp))
        cols = min(cols, len(self._items))
        w = (rect.width() - sp * (cols - 1)) // cols
        y = rect.y()
        for row_start in range(0, len(self._items), cols):
            row = self._items[row_start:row_start + cols]
            row_h = max(it.widget().heightForWidth(w) if it.widget() and
                        it.widget().hasHeightForWidth() else it.sizeHint().height()
                        for it in row)
            row_h = max(row_h, max(it.sizeHint().height() for it in row))
            for c, it in enumerate(row):
                if apply:
                    it.setGeometry(QRect(QPoint(rect.x() + c * (w + sp), y), QSize(w, row_h)))
            y += row_h + sp
        return y - sp - rect.y()

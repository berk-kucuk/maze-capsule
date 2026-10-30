"""Monochrome line glyphs for the chrome (title bar, cards, buttons).

Drawn here as tiny SVGs on a 24-unit grid with one stroke weight, so every
glyph matches and recolours cleanly; no icon theme is consulted, because a
user's Breeze/Papirus colours would break the black-and-white look.
"""
from __future__ import annotations

from functools import lru_cache

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

_PATHS: dict[str, str] = {
    "capsule": '<rect x="3.5" y="3.5" width="17" height="17"/><rect x="7.5" y="7.5" width="9" height="9" '
               'fill="{color}"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>'
            '<path d="M12 14.5v2.5"/>',
    "unlock": '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 7.6-1.7"/>'
              '<path d="M12 14.5v2.5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "folder": '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.2h7a2 2 0 0 1 2 2v8.8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z"/>',
    "add_files": '<path d="M14 3.5H7A2 2 0 0 0 5 5.5v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-10Z"/><path d="M14 3.5v5h5M12 11.5v6M9 14.5h6"/>',
    "terminal": '<rect x="3" y="4.5" width="18" height="15" rx="2.2"/><path d="m7 9.5 3 2.5-3 2.5M12.5 15h4.5"/>',
    "more": '<path d="M6 12h.01M12 12h.01M18 12h.01" stroke-width="3"/>',
    "import": '<path d="M12 3.5v11M7.5 10l4.5 4.5 4.5-4.5"/><path d="M4.5 15.5v3a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3"/>',
    "export": '<path d="M12 14.5v-11M7.5 8 12 3.5 16.5 8"/><path d="M4.5 15.5v3a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="m10.8 12.2 8.7-8.7M16.5 6.5l2.5 2.5M14 9l2 2"/>',
    "shield_ok": '<path d="M12 3 19 6v5.5c0 4.4-3 8-7 9.5-4-1.5-7-5.1-7-9.5V6Z"/><path d="m9 12 2 2 4-4"/>',
    "shield_bad": '<path d="M12 3 19 6v5.5c0 4.4-3 8-7 9.5-4-1.5-7-5.1-7-9.5V6Z"/><path d="M12 8.5v4.5M12 16h.01"/>',
    "warn": '<path d="M12 4 21 19.5H3Z"/><path d="M12 10v4.5M12 17h.01"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "copy": '<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2.2"/><path d="M15.5 8.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7.5a2 2 0 0 0 2 2h2.5"/>',
    "save": '<path d="M5 4.5h11l3.5 3.5v11a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 19V6A1.5 1.5 0 0 1 5 4.5Z"/><path d="M7.5 4.5v4.5h7v-4.5M7.5 20.5v-6h9v6"/>',
    "trash": '<path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13"/><path d="M10 11v5.5M14 11v5.5"/>',
    "restore": '<path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3L4.5 9"/><path d="M4.5 4.5V9H9"/>',
    "edit": '<path d="M4.5 19.5h4l10-10a2.8 2.8 0 0 0-4-4l-10 10Z"/><path d="m13.5 6.5 4 4"/>',
    "pulse": '<path d="M3 12h4l2.5-6 5 12 2.5-6h4"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M5.5 18.5l1.7-1.7M16.8 7.2l1.7-1.7"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/>',
    "eye_off": '<path d="M3.5 3.5l17 17"/><path d="M10 6a9.6 9.6 0 0 1 2-.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-2.6 3.4M6.5 7.2C4 9 2.5 12 2.5 12S6 18.5 12 18.5a9 9 0 0 0 4.3-1.1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    "external": '<path d="M14 4h6v6M20 4l-8.5 8.5"/><path d="M18 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10"/>',
    "point": '<path d="M5 12h13M13 7l5 5-5 5"/>',
    "drop": '<path d="M12 4v10M8 10.5l4 4 4-4"/><path d="M4 17.5h16" stroke-dasharray="2 2.5"/>',
    "usb": '<rect x="7" y="9.5" width="10" height="11" rx="1.8"/><path d="M9 9.5V3.5h6v6M10.5 6h.01M13.5 6h.01"/>',
    "globe": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.5 3.5 5.5 3.5 8.5s-1 6-3.5 8.5c-2.5-2.5-3.5-5.5-3.5-8.5s1-6 3.5-8.5Z"/>',
    "win_min": '<path d="M6.5 12h11"/>',
    "win_max": '<rect x="6.5" y="6.5" width="11" height="11" rx="1"/>',
    "win_restore": '<rect x="5.5" y="8.5" width="10" height="10" rx="1"/><path d="M8.5 8.5V6.5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1h-2"/>',
    "win_close": '<path d="m6.5 6.5 11 11M17.5 6.5l-11 11"/>',
}


@lru_cache(maxsize=256)
def glyph_pixmap(name: str, size: int, color: str = "#f2f2f4", dpr: float = 2.0) -> QPixmap:
    body = _PATHS[name].replace("{color}", color)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="1.7" stroke-linecap="round" '
           f'stroke-linejoin="round">{body}</svg>')
    px = int(size * dpr)
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(p, QRectF(0, 0, px, px))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def glyph(name: str, size: int = 18, color: str = "#f2f2f4") -> QIcon:
    return QIcon(glyph_pixmap(name, size, color))

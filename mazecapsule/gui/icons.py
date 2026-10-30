"""The Maze Capsule mark, drawn from its SVG at the screen's pixel density."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[2]
LOGO_SVG_CANDIDATES = [ROOT / "maze-capsule-logo.svg",
                       Path("/usr/share/icons/hicolor/scalable/apps/maze-capsule.svg")]
APP_LOGO_PNG = ROOT / "MAZE-CAPSULE.png"


def _screen_dpr() -> float:
    screen = QGuiApplication.primaryScreen()
    # Never below 2: fractional scales look soft if the art was drawn at 1x.
    return max(2.0, screen.devicePixelRatio() if screen else 1.0)


@lru_cache(maxsize=16)
def logo_pixmap(size: int) -> QPixmap:
    dpr = _screen_dpr()
    px = int(round(size * dpr))
    for svg in LOGO_SVG_CANDIDATES:
        if svg.is_file():
            renderer = QSvgRenderer(QByteArray(svg.read_bytes()))
            if renderer.isValid():
                pm = QPixmap(px, px)
                pm.fill(Qt.GlobalColor.transparent)
                p = QPainter(pm)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                renderer.render(p, QRectF(0, 0, px, px))
                p.end()
                pm.setDevicePixelRatio(dpr)
                return pm
    pm = app_logo().pixmap(px, px)
    pm.setDevicePixelRatio(dpr)
    return pm


def app_logo() -> QIcon:
    themed = QIcon.fromTheme("maze-capsule")
    if not themed.isNull():
        return themed
    for path in (APP_LOGO_PNG, *LOGO_SVG_CANDIDATES):
        if path.is_file():
            return QIcon(str(path))
    return QIcon()

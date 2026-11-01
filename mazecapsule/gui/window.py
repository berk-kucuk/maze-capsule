"""Main window: the capsule grid, the trash, and every action on a capsule.

Frameless with its own 50px title bar, like Maze Store, Maze Donate and Maze
Cloak. The page is rebuilt from the kernel's mount table and the capsule
folders on every change; the window never keeps its own idea of what is
unlocked, so it cannot disagree with reality (see core/mounts.py).
"""
from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, QSize, QTimer, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel,
                             QMainWindow, QMenu, QPushButton, QScrollArea, QVBoxLayout,
                             QWidget)

from mazecapsule import __version__
from mazecapsule.core import gocrypt, sandbox, settings, store, transfer
from mazecapsule.core.store import Capsule, CapsuleError, Trashed
from mazecapsule.gui import worker
from mazecapsule.gui.chrome import EdgeResizer, TitleBar, WindowButton, button, label
from mazecapsule.gui.dialogs import (ChangePasswordDialog, ChoiceDialog, ConfirmDialog,
                                     MessageDialog, NewCapsuleDialog, PasswordAskDialog,
                                     ProgressDialog, RecoveryKeyDialog, SettingsDialog,
                                     TextDialog, UnlockDialog)
from mazecapsule.gui.flow import FlowLayout
from mazecapsule.gui.glass import GlassBackground, GlassFrame
from mazecapsule.gui.glyphs import glyph, glyph_pixmap
from mazecapsule.gui.i18n import err, human_size, language, set_language, t
from mazecapsule.gui.icons import app_logo, logo_pixmap
from mazecapsule.gui.pill import Pill

LOW_SPACE = 1_000_000_000  # warn below 1 GB free


def _elide(lb: QLabel, text: str, width: int) -> None:
    lb.setText(lb.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, width))
    lb.setToolTip(text)


class CapsuleCard(GlassFrame):
    def __init__(self, c: Capsule, win: "MainWindow"):
        unlocked = c.unlocked
        super().__init__(radius=18, interactive=unlocked, strength=1.25 if unlocked else 1.0)
        self.c = c
        self.win = win
        self._mp = c.mountpoint
        self._ro = c.read_only
        self.setAcceptDrops(unlocked and not self._ro)
        self.setMinimumHeight(250)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(glyph_pixmap("unlock" if unlocked else "lock", 20,
                                  "#f2f2f4" if unlocked else "#8f8f95"))
        head.addWidget(ic)
        name = label(c.name, "card_title")
        name.setMinimumWidth(40)
        head.addWidget(name, 1)
        if not c.available:
            head.addWidget(Pill(t("pill_offline"), "busy"))
        elif unlocked:
            head.addWidget(Pill(t("pill_ro") if self._ro else t("pill_unlocked"), "update"))
        else:
            head.addWidget(Pill(t("pill_locked"), "installed"))
        v.addLayout(head)

        self.meta = label(t("created", date=store.created_text(c)), "meta")
        v.addWidget(self.meta)
        if c.available:
            size = win.sizes.get(c.id)
            self._set_size(size)
        loc = label("", "path")
        if not c.available:
            loc = label(t("loc_offline", path=str(c.root)), "tagline", wrap=True)
        elif c.linked:
            _elide(loc, t("loc_linked", path=str(c.root)), 300)
        else:
            loc.setText(t("loc_default"))
            loc.setObjectName("meta")
        v.addWidget(loc)
        if unlocked and self._mp:
            mp = label("", "path")
            _elide(mp, t("mounted_at", path=str(self._mp)), 300)
            v.addWidget(mp)

        if c.available:
            free = win.free.get(c.id)
            if free is not None and free < LOW_SPACE:
                v.addWidget(self._warn(t("low_space", free=human_size(free))))
        if c.available and not c.recovery_confirmed:
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(self._warn(t("no_recovery")), 1)
            save = button(t("btn_save_now"), "ghost", "key")
            save.clicked.connect(lambda: win.save_recovery(c))
            row.addWidget(save)
            v.addLayout(row)

        v.addStretch(1)
        if unlocked and not self._ro:
            hint = QHBoxLayout()
            hint.setSpacing(6)
            di = QLabel()
            di.setPixmap(glyph_pixmap("drop", 14, "#6f6f75"))
            hint.addWidget(di)
            hint.addWidget(label(t("drop_hint"), "drop"), 1)
            v.addLayout(hint)

        main = QHBoxLayout()
        main.setSpacing(8)
        more = QPushButton(objectName="round")
        more.setIcon(glyph("more", 16))
        more.setIconSize(QSize(16, 16))
        more.setFixedSize(40, 40)
        more.setCursor(Qt.CursorShape.PointingHandCursor)
        more.setToolTip(t("tip_more"))
        more.clicked.connect(lambda: self._menu(more))
        if not c.available:
            main.addStretch(1)
        elif unlocked:
            op = button(t("btn_open"), "get_lg", "folder")
            op.clicked.connect(lambda: win.open_capsule(c))
            main.addWidget(op, 1)
            lk = button(t("btn_lock"), "secondary_lg", "lock")
            lk.clicked.connect(lambda: win.lock(c))
            main.addWidget(lk)
        else:
            un = button(t("btn_unlock"), "get_lg", "unlock")
            un.clicked.connect(lambda: win.unlock(c))
            main.addWidget(un, 1)
        main.addWidget(more)
        v.addLayout(main)

        if unlocked:
            row = QHBoxLayout()
            row.setSpacing(8)
            add = button(t("btn_add_files"), "secondary", "add_files")
            add.clicked.connect(lambda: win.add_files(c))
            add.setEnabled(not self._ro)
            sh = button(t("btn_shell"), "secondary", "terminal")
            sh.clicked.connect(lambda: win.shell(c))
            for b in (add, sh):
                row.addWidget(b, 1)
            v.addLayout(row)

    def _warn(self, text: str) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        ic = QLabel()
        ic.setPixmap(glyph_pixmap("warn", 14, "#e6e6ea"))
        h.addWidget(ic)
        h.addWidget(label(text, "warnline", wrap=True), 1)
        return w

    def _set_size(self, size: int | None) -> None:
        base = t("created", date=store.created_text(self.c))
        extra = t("size_pending") if size is None else t("size", size=human_size(size))
        self.meta.setText(f"{base}  ·  {extra}")

    def _menu(self, anchor: QWidget) -> None:
        c, win = self.c, self.win
        m = QMenu(self)
        unlocked = self._mp is not None

        def add(text: str, icon: str, fn, enabled: bool = True) -> None:
            a = m.addAction(glyph(icon, 16), text)
            a.setEnabled(enabled)
            a.triggered.connect(fn)
        if c.available:
            add(t("m_rename"), "edit", lambda: win.rename(c))
            add(t("m_password"), "key", lambda: win.change_password(c))
            add(t("m_recovery"), "eye", lambda: win.show_recovery(c))
            add(t("m_check"), "pulse", lambda: win.check(c))
            add(t("m_export"), "export", lambda: win.export(c), not unlocked and not c.bare)
            add(t("m_location"), "folder", lambda: win.show_location(c))
            if unlocked:
                add(t("btn_add_folder"), "add_files", lambda: win.add_folder(c), not self._ro)
                add(t("m_lock_force"), "lock", lambda: win.lock(c, lazy=True))
            m.addSeparator()
        if c.linked:
            add(t("m_forget"), "trash", lambda: win.forget(c), not unlocked)
        else:
            add(t("m_delete"), "trash", lambda: win.delete(c), not unlocked)
        m.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    # drag & drop into an unlocked capsule
    def dragEnterEvent(self, ev) -> None:
        if ev.mimeData().hasUrls() and all(u.isLocalFile() for u in ev.mimeData().urls()):
            ev.acceptProposedAction()

    def dropEvent(self, ev) -> None:
        paths = [Path(u.toLocalFile()) for u in ev.mimeData().urls() if u.isLocalFile()]
        if paths:
            ev.acceptProposedAction()
            QTimer.singleShot(0, lambda: self.win.copy_in(self.c, paths))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Maze Capsule")
        self.setWindowIcon(app_logo())
        self.resize(1120, 840)
        self.setMinimumSize(760, 560)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setMouseTracking(True)
        self._resizer = EdgeResizer(self)
        QApplication.instance().installEventFilter(self._resizer)

        self.sizes: dict[str, int] = {}
        self.free: dict[str, int] = {}
        self._cards: dict[str, CapsuleCard] = {}
        self._signature: tuple = ()
        self._capsules: list[Capsule] = []
        self._trash: list[Trashed] = []
        self._show_trash = False
        self._gv = gocrypt.version()

        self._build_chrome()
        self.refresh(force=True)
        self._poll = QTimer(self, interval=2000)
        self._poll.timeout.connect(self.refresh)
        self._poll.start()
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_capsule)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.lock_all)
        QShortcut(QKeySequence("F5"), self, activated=lambda: self.refresh(force=True))

    # ── chrome ─────────────────────────────────────────────────────────────
    def _build_chrome(self) -> None:
        root = GlassBackground()
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = TitleBar(self)
        header.setFixedHeight(50)
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 0, 0, 0)
        h.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(28))
        h.addWidget(logo)
        h.addWidget(label("MAZE CAPSULE", "wordmark"))
        h.addStretch(1)
        for code, text in (("en", "EN"), ("tr", "TR")):
            b = QPushButton(text, objectName="seg_on" if language() == code else "seg")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(t("tip_language"))
            b.clicked.connect(lambda _=False, c=code: self.set_lang(c))
            h.addWidget(b)
        gear = QPushButton(objectName="win_btn")
        gear.setIcon(glyph("gear", 16, "#9a9aa0"))
        gear.setIconSize(QSize(16, 16))
        gear.setToolTip(t("tip_settings"))
        gear.clicked.connect(self.open_settings)
        h.addSpacing(4)
        h.addWidget(gear)
        sep = QFrame(objectName="vline")
        sep.setFixedSize(1, 22)
        h.addWidget(sep)
        self._max_btn = WindowButton("win_max", t("tip_maximize"))
        self._max_btn.clicked.connect(
            lambda: self.showNormal() if self.isMaximized() else self.showMaximized())
        mn = WindowButton("win_min", t("tip_minimize"))
        mn.clicked.connect(self.showMinimized)
        cl = WindowButton("win_close", t("tip_close"))
        cl.clicked.connect(self.close)
        for b in (mn, self._max_btn, cl):
            h.addWidget(b)
        v.addWidget(header)

        # The vault: a toolbar, the grid of capsules, and the trash as a
        # drawer on the right that slides in only when asked for.
        self._toolbar = QWidget()
        v.addWidget(self._toolbar)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.viewport().setAutoFillBackground(False)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.addWidget(self._scroll, 1)
        self._drawer = QWidget()
        self._drawer.hide()
        body.addWidget(self._drawer)
        v.addLayout(body, 1)

        footer = QWidget(objectName="footer")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        footer.setFixedHeight(30)
        fh = QHBoxLayout(footer)
        fh.setContentsMargins(22, 0, 22, 0)
        self._status = label("", "statusbar")
        fh.addWidget(self._status, 1)
        right = f"gocryptfs {self._gv}  ·  " if self._gv else ""
        fh.addWidget(label(f"{right}Maze Capsule {__version__}", "statusbar"))
        v.addWidget(footer)

        self.setCentralWidget(root)
        self._flash_timer = QTimer(self, singleShot=True, interval=9000)
        self._flash_timer.timeout.connect(self._update_status)

    def changeEvent(self, ev) -> None:
        if ev.type() == QEvent.Type.WindowStateChange:
            self._max_btn.set_kind("win_restore" if self.isMaximized() else "win_max")
        super().changeEvent(ev)

    def set_lang(self, code: str) -> None:
        if code == language():
            return
        set_language(code)
        settings.save(language=code)
        self._build_chrome()
        self.refresh(force=True)

    def open_settings(self) -> None:
        d = SettingsDialog(self)
        d.language_changed.connect(lambda c: QTimer.singleShot(0, lambda: self._apply_lang(c)))
        d.exec()

    def _apply_lang(self, code: str) -> None:
        set_language(code)
        self._build_chrome()
        self.refresh(force=True)

    # ── status ─────────────────────────────────────────────────────────────
    def flash(self, text: str) -> None:
        self._status.setText(text)
        self._status.setToolTip(text)
        self._flash_timer.start()

    def _update_status(self) -> None:
        if not gocrypt.available():
            self._status.setText(t("no_gocryptfs"))
            return
        u = sum(1 for c in self._capsules if c.unlocked)
        self._status.setText(t("status_ready", n=len(self._capsules), u=u))

    # ── data ───────────────────────────────────────────────────────────────
    def refresh(self, force: bool = False) -> None:
        # Never rebuild under an open menu or dialog: it would delete the
        # widgets they belong to.
        if not force and (QApplication.activePopupWidget() is not None
                          or QApplication.activeModalWidget() is not None):
            return
        try:
            caps = store.list_capsules()
            trash = store.list_trash()
        except OSError as e:
            self.flash(err(e))
            return
        sig = (tuple((c.id, c.name, c.available, c.recovery_confirmed, c.linked,
                      str(c.mountpoint), c.read_only) for c in caps),
               tuple((x.path.name, x.name) for x in trash), language(), self._show_trash)
        if not force and sig == self._signature:
            return
        self._signature = sig
        self._capsules, self._trash = caps, trash
        self._render()
        self._measure()

    def _measure(self) -> None:
        caps = [c for c in self._capsules if c.available]
        if not caps:
            return

        def job() -> dict[str, tuple[int, int | None]]:
            return {c.id: (store.size_of(c), store.free_space(c)) for c in caps}

        def done(res: dict) -> None:
            for cid, (size, free) in res.items():
                self.sizes[cid] = size
                if free is not None:
                    self.free[cid] = free
                card = self._cards.get(cid)
                if card is not None:
                    try:
                        card._set_size(size)
                    except RuntimeError:
                        pass
        worker.run(job, on_done=done, on_fail=lambda _e: None, critical=False)

    # ── page ───────────────────────────────────────────────────────────────
    def _render(self) -> None:
        y = self._scroll.verticalScrollBar().value()
        self._swap_toolbar(self._build_toolbar())
        self._swap_drawer(self._build_drawer() if self._show_trash else None)

        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(24, 22, 24, 26)
        v.setSpacing(16)
        if not gocrypt.available():
            v.addWidget(self._banner(t("no_gocryptfs")))

        self._cards = {}
        if self._capsules:
            grid = QWidget()
            flow = FlowLayout(grid, spacing=16, min_item_width=310)
            for c in self._capsules:
                card = CapsuleCard(c, self)
                self._cards[c.id] = card
                flow.addWidget(card)
            v.addWidget(grid)
            v.addStretch(1)
        else:
            v.addStretch(1)
            v.addWidget(self._onboarding(), 0, Qt.AlignmentFlag.AlignHCenter)
            v.addStretch(2)

        self._scroll.setWidget(page)
        QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(y))
        self._update_status()

    def _swap_toolbar(self, new: QWidget) -> None:
        layout = self.centralWidget().layout()
        layout.replaceWidget(self._toolbar, new)
        self._toolbar.hide()
        self._toolbar.deleteLater()
        self._toolbar = new

    def _swap_drawer(self, new: QWidget | None) -> None:
        holder = self._drawer.parentWidget().layout()
        replacement = new or QWidget()
        for i in range(holder.count()):
            lay = holder.itemAt(i).layout()
            if lay is not None and lay.indexOf(self._drawer) >= 0:
                lay.replaceWidget(self._drawer, replacement)
                break
        self._drawer.hide()
        self._drawer.deleteLater()
        self._drawer = replacement
        self._drawer.setVisible(new is not None)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget(objectName="toolbar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setFixedHeight(64)
        h = QHBoxLayout(bar)
        h.setContentsMargins(24, 0, 18, 0)
        h.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(glyph_pixmap("capsule", 22, "#f2f2f4"))
        h.addWidget(ic)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(label(t("tb_capsules"), "tb_title"))
        u = sum(1 for c in self._capsules if c.unlocked)
        titles.addWidget(label(t("status_ready", n=len(self._capsules), u=u), "meta"))
        h.addLayout(titles)
        h.addStretch(1)
        if u:
            la = button(t("btn_lock_all"), "ghost", "lock")
            la.clicked.connect(self.lock_all)
            h.addWidget(la)
        add = button(t("btn_add_existing"), "secondary", "import")
        add.clicked.connect(lambda: self._add_existing_menu(add))
        h.addWidget(add)
        new = button(t("btn_new"), "get", "plus")
        new.clicked.connect(self.new_capsule)
        new.setEnabled(gocrypt.available())
        h.addWidget(new)
        sep = QFrame(objectName="vline")
        sep.setFixedSize(1, 22)
        h.addSpacing(4)
        h.addWidget(sep)
        trash = button(f"{t('btn_trash')}  {len(self._trash)}" if self._trash else t("btn_trash"),
                       "seg_on" if self._show_trash else "ghost", "trash",
                       icon_color="#000000" if self._show_trash else None)
        trash.clicked.connect(self._toggle_trash)
        h.addWidget(trash)
        return bar

    def _onboarding(self) -> QWidget:
        """What a capsule is, said once — while there are none yet."""
        box = QWidget()
        # A fixed width: word-wrapped labels in a centred, shrink-to-fit box
        # are sized to one line and cut the rest off.
        box.setFixedWidth(600)
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        mark = QLabel()
        mark.setPixmap(logo_pixmap(96))
        v.addWidget(mark, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(6)
        v.addWidget(label(t("eyebrow"), "eyebrow"), 0, Qt.AlignmentFlag.AlignHCenter)
        title = label(t("hero_title"), "onboard_title")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(title)
        sub = label(t("hero_sub"), "hero_sub", wrap=True)
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(sub)
        v.addSpacing(8)
        for key in ("point_1", "point_2", "point_3"):
            row = QHBoxLayout()
            row.setSpacing(10)
            ic = QLabel()
            ic.setPixmap(glyph_pixmap("check", 15, "#9a9aa0"))
            ic.setFixedWidth(16)
            row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(label(t(key), "point", wrap=True), 1)
            v.addLayout(row)
        v.addSpacing(14)
        btns = QHBoxLayout()
        btns.addStretch(1)
        new = button(t("btn_new"), "get_lg", "plus")
        new.clicked.connect(self.new_capsule)
        new.setEnabled(gocrypt.available())
        btns.addWidget(new)
        btns.addStretch(1)
        v.addLayout(btns)
        return box

    def _build_drawer(self) -> QWidget:
        drawer = QWidget(objectName="drawer")
        drawer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        drawer.setFixedWidth(360)
        v = QVBoxLayout(drawer)
        v.setContentsMargins(20, 18, 16, 18)
        v.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(label(t("sec_trash"), "section"))
        head.addSpacing(6)
        head.addWidget(label(str(len(self._trash)), "meta"))
        head.addStretch(1)
        close = QPushButton(objectName="round")
        close.setIcon(glyph("win_close", 14, "#bdbdc2"))
        close.setFixedSize(30, 30)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self._toggle_trash)
        head.addWidget(close)
        v.addLayout(head)
        v.addWidget(label(t("drawer_hint"), "hint", wrap=True))
        v.addSpacing(8)
        if not self._trash:
            v.addWidget(label(t("trash_empty"), "tagline"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(0)
        for tr in self._trash:
            row = QWidget(objectName="trashrow")
            row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            rv = QVBoxLayout(row)
            rv.setContentsMargins(0, 12, 0, 12)
            rv.setSpacing(6)
            top = QHBoxLayout()
            top.setSpacing(10)
            ic = QLabel()
            ic.setPixmap(glyph_pixmap("capsule", 18, "#8f8f95"))
            top.addWidget(ic)
            txt = QVBoxLayout()
            txt.setSpacing(1)
            txt.addWidget(label(tr.name, "title"))
            txt.addWidget(label(t("trash_row", date=datetime.fromtimestamp(tr.trashed_at)
                                  .strftime("%Y-%m-%d %H:%M")), "meta"))
            top.addLayout(txt, 1)
            rv.addLayout(top)
            acts = QHBoxLayout()
            acts.setSpacing(6)
            rs = button(t("btn_restore"), "secondary", "restore")
            rs.clicked.connect(lambda _=False, x=tr: self.restore(x))
            acts.addWidget(rs)
            pg = button(t("btn_purge"), "ghost", "trash")
            pg.clicked.connect(lambda _=False, x=tr: self.purge(x))
            acts.addWidget(pg)
            acts.addStretch(1)
            rv.addLayout(acts)
            iv.addWidget(row)
        iv.addStretch(1)
        scroll.setWidget(inner)
        v.addWidget(scroll, 1)
        return drawer

    def _banner(self, text: str) -> QFrame:
        box = GlassFrame(radius=16)
        h = QHBoxLayout(box)
        h.setContentsMargins(18, 14, 18, 14)
        ic = QLabel()
        ic.setPixmap(glyph_pixmap("shield_bad", 26))
        h.addWidget(ic)
        h.addWidget(label(text, "banner_title", wrap=True), 1)
        return box

    def _toggle_trash(self) -> None:
        self._show_trash = not self._show_trash
        # Deferred: this runs inside the clicked() of a toolbar or drawer
        # button that the refresh replaces.
        QTimer.singleShot(0, lambda: self.refresh(force=True))

    # ── create / add ───────────────────────────────────────────────────────
    def new_capsule(self) -> None:
        if not gocrypt.available():
            self.flash(t("no_gocryptfs"))
            return
        d = NewCapsuleDialog(self)
        if not d.exec() or d.result_value is None:
            return
        capsule, key, mp = d.result_value
        d.result_value = None
        self.refresh(force=True)
        rk = RecoveryKeyDialog(self, capsule, key, new=True)
        if rk.exec():
            self._confirm_recovery(capsule)
        del key
        if mp is not None:
            self.flash(t("unlocked_msg", name=capsule.name))
        self.refresh(force=True)

    def _confirm_recovery(self, c: Capsule) -> None:
        try:
            store.confirm_recovery(c)
        except (CapsuleError, OSError) as e:
            self.flash(err(e))

    def _add_existing_menu(self, anchor: QWidget) -> None:
        m = QMenu(self)
        a = m.addAction(glyph("import", 16), t("menu_import"))
        a.triggered.connect(self.import_backup)
        b = m.addAction(glyph("usb", 16), t("menu_link"))
        b.triggered.connect(self.link_folder)
        c = m.addAction(glyph("link", 16), t("menu_link_bare"))
        c.triggered.connect(self.link_folder)
        m.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def import_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, t("menu_import"), str(Path.home()),
                                              t("imp_filter"))
        if not path:
            return
        self.flash(t("verifying"))
        worker.run(store.import_backup, Path(path),
                   on_done=lambda c: (self.flash(t("imp_done", name=c.name)), self.refresh(force=True)),
                   on_fail=lambda e: self.flash(err(e)))

    def link_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, t("menu_link"), str(Path.home()))
        if not d:
            return
        try:
            c = store.link_folder(Path(d))
        except (CapsuleError, OSError) as e:
            self.flash(err(e))
            return
        self.flash(t("link_done", name=c.name))
        self.refresh(force=True)

    # ── unlock / lock / open ───────────────────────────────────────────────
    def unlock(self, c: Capsule, start_with_key: bool = False) -> None:
        d = UnlockDialog(self, c, settings.load()["idle_minutes"], start_with_key)
        if not d.exec() or d.mountpoint is None:
            return
        self.flash(t("unlocked_msg", name=c.name))
        self.refresh(force=True)
        if d.used_key is not None:
            ch = ChoiceDialog(self, t("after_rk_title"), t("after_rk_body", name=c.name),
                              [("later", t("after_rk_later"), "secondary_lg"),
                               ("set", t("after_rk_btn"), "get_lg")], icon="key")
            if ch.exec() and ch.choice == "set":
                cp = ChangePasswordDialog(self, c, master_key=d.used_key)
                if cp.exec():
                    self.flash(t("cp_done", name=c.name))
            d.used_key = None

    def open_capsule(self, c: Capsule) -> None:
        mp = c.mountpoint
        if mp is None:
            self.refresh(force=True)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(mp)))

    def show_location(self, c: Capsule) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(c.root)))

    def lock(self, c: Capsule, lazy: bool = False) -> None:
        def done(_r) -> None:
            self.flash(t("locked_msg", name=c.name))
            self.refresh(force=True)

        def fail(e: BaseException) -> None:
            if getattr(e, "reason", "") == "busy":
                ch = ChoiceDialog(self, t("busy_title", name=c.name), t("busy_body"),
                                  [("cancel", t("btn_cancel"), "secondary_lg"),
                                   ("lazy", t("busy_lazy"), "get_lg")], icon="warn")
                if ch.exec() and ch.choice == "lazy":
                    self.lock(c, lazy=True)
            else:
                self.flash(err(e))
            self.refresh(force=True)
        worker.run(store.lock, c, lazy, on_done=done, on_fail=fail)

    def lock_all(self) -> None:
        for c in self._capsules:
            if c.unlocked:
                self.lock(c)

    # ── files in ───────────────────────────────────────────────────────────
    def add_files(self, c: Capsule) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, t("pick_files", name=c.name), str(Path.home()))
        if files:
            self.copy_in(c, [Path(f) for f in files])

    def add_folder(self, c: Capsule) -> None:
        d = QFileDialog.getExistingDirectory(self, t("pick_folder", name=c.name), str(Path.home()))
        if d:
            self.copy_in(c, [Path(d)])

    def copy_in(self, c: Capsule, paths: list[Path]) -> None:
        mp = c.mountpoint
        if mp is None or c.read_only:
            self.refresh(force=True)
            return
        dlg = ProgressDialog(self, t("cp_in_title", name=c.name))
        last = [0.0]

        def job(progress) -> transfer.CopyReport:
            def report(done: int, total: int, name: str) -> None:
                now = time.monotonic()
                if now - last[0] > 0.08 or done >= total:
                    last[0] = now
                    progress(done, total, name)
            return transfer.copy_into(paths, mp, progress=report, cancelled=dlg.cancel_event.is_set)

        def done(r: transfer.CopyReport) -> None:
            dlg.finish()
            msg = t("cp_in_done", files=r.files, size=human_size(r.bytes), name=c.name)
            if r.errors:
                msg += "  " + t("cp_in_errors", n=len(r.errors), first=f"{Path(r.errors[0][0]).name}: {r.errors[0][1]}")
            self.flash(msg)
            self.sizes.pop(c.id, None)
            self._measure()

        def fail(e: BaseException) -> None:
            dlg.finish()
            self.flash(t("cp_in_cancelled") if isinstance(e, transfer.Cancelled) else err(e))
            self._measure()
        worker.run(job, with_progress=True, on_progress=lambda v: dlg.set_progress(*v),
                   on_done=done, on_fail=fail)
        dlg.exec()

    def shell(self, c: Capsule) -> None:
        mp = c.mountpoint
        if mp is None:
            return
        net = settings.load()["sandbox_network"]
        try:
            if not sandbox.available():
                raise RuntimeError
            argv = sandbox.terminal_argv(mp, c.name, network=net)
            subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (RuntimeError, OSError):
            self.flash(t("sb_missing"))
            return
        self.flash(t("sb_opened", name=c.name, net=t("sb_net_on" if net else "sb_net_off")))

    # ── manage ─────────────────────────────────────────────────────────────
    def rename(self, c: Capsule) -> None:
        d = TextDialog(self, t("rn_title"), t("f_name"), c.name, store.clean_name)
        if d.exec() and d.value and d.value != c.name:
            try:
                store.rename(c, d.value)
            except (CapsuleError, OSError) as e:
                self.flash(err(e))
            self.refresh(force=True)

    def change_password(self, c: Capsule) -> None:
        if ChangePasswordDialog(self, c).exec():
            self.flash(t("cp_done", name=c.name))

    def show_recovery(self, c: Capsule) -> None:
        self._recovery_flow(c, new=False)

    def save_recovery(self, c: Capsule) -> None:
        self._recovery_flow(c, new=True)

    def _recovery_flow(self, c: Capsule, new: bool) -> None:
        d = PasswordAskDialog(self, c, t("ask_pw_recovery"), t("verifying"),
                              lambda pw: store.recovery_key(c, pw), t("btn_continue"))
        if not d.exec() or not d.result_value:
            return
        key = d.result_value
        d.result_value = None
        rk = RecoveryKeyDialog(self, c, key, new=new)
        if rk.exec() and new:
            self._confirm_recovery(c)
            self.refresh(force=True)

    def check(self, c: Capsule) -> None:
        d = PasswordAskDialog(self, c, t("ask_pw_check"), t("checking"),
                              lambda pw: store.check_integrity(c, pw), t("btn_continue"))
        if not d.exec() or d.result_value is None:
            return
        ok, report = d.result_value
        if ok:
            MessageDialog(self, t("ck_ok_title"), t("ck_ok_body", name=c.name), "shield_ok").exec()
        else:
            MessageDialog(self, t("ck_bad_title"), t("ck_bad_body", name=c.name), "shield_bad",
                          report=report).exec()

    def export(self, c: Capsule) -> None:
        safe = store._folder_name(c.name)
        stamp = datetime.now().strftime("%Y-%m-%d")
        path, _ = QFileDialog.getSaveFileName(
            self, t("exp_title"), str(Path.home() / f"{safe} {stamp}{store.BACKUP_SUFFIX}"),
            t("exp_filter"))
        if not path:
            return
        dest = Path(path)
        if dest.exists():
            # The file dialog already asked to replace it; exports never
            # overwrite, so pick a free name next to it instead.
            n = 2
            base = dest.name.removesuffix(store.BACKUP_SUFFIX)
            while dest.exists():
                dest = dest.with_name(f"{base} ({n}){store.BACKUP_SUFFIX}")
                n += 1
        dlg = ProgressDialog(self, t("exp_title"))
        dlg.cancel.hide()
        dlg.current.setText(str(dest))

        def done(out: Path) -> None:
            dlg.finish()
            MessageDialog(self, t("exp_title"), t("exp_done", path=str(out)), "shield_ok").exec()

        def fail(e: BaseException) -> None:
            dlg.finish()
            self.flash(err(e))
        worker.run(store.export_backup, c, dest, with_progress=True,
                   on_progress=lambda v: dlg.set_progress(v[0], v[1]), on_done=done, on_fail=fail)
        dlg.exec()

    def delete(self, c: Capsule) -> None:
        d = ConfirmDialog(self, t("del_title", name=c.name), t("del_body"), t("del_btn"),
                          icon="trash")
        if not d.exec():
            return
        try:
            store.trash(c)
        except (CapsuleError, OSError) as e:
            self.flash(err(e))
        self.refresh(force=True)

    def forget(self, c: Capsule) -> None:
        d = ConfirmDialog(self, t("forget_title", name=c.name),
                          t("forget_body", path=str(c.root)), t("forget_btn"), icon="link")
        if not d.exec():
            return
        try:
            store.trash(c)
        except (CapsuleError, OSError) as e:
            self.flash(err(e))
        self.refresh(force=True)

    def restore(self, tr: Trashed) -> None:
        try:
            store.restore(tr)
        except (CapsuleError, OSError) as e:
            self.flash(err(e))
        self.refresh(force=True)

    def purge(self, tr: Trashed) -> None:
        d = ConfirmDialog(self, t("purge_title", name=tr.name), t("purge_body"), t("purge_btn"),
                          danger=True, typed=tr.name, icon="warn")
        if not d.exec():
            return
        try:
            store.purge(tr)
        except (CapsuleError, OSError) as e:
            self.flash(err(e))
        self.refresh(force=True)

    # ── quit ───────────────────────────────────────────────────────────────
    def closeEvent(self, ev) -> None:
        if worker.busy():
            # A copy, export or key operation is running: finishing it beats
            # interrupting it.
            ev.ignore()
            return
        open_caps = [c for c in store.list_capsules() if c.unlocked]
        if not open_caps:
            ev.accept()
            return
        ch = ChoiceDialog(self, t("quit_title"), t("quit_body", n=len(open_caps)),
                          [("cancel", t("btn_cancel"), "ghost"),
                           ("keep", t("quit_keep"), "secondary_lg"),
                           ("lock", t("quit_lock"), "get_lg")], icon="lock")
        if not ch.exec() or ch.choice == "cancel":
            ev.ignore()
            return
        if ch.choice == "lock":
            failed = store.lock_all()
            if failed:
                self.flash(t("quit_fail", names=", ".join(c.name for c, _ in failed)))
                self.refresh(force=True)
                ev.ignore()
                return
        ev.accept()

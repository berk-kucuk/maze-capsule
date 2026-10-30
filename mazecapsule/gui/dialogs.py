"""Every dialog of Maze Capsule, on one frameless black base.

Slow work (scrypt key derivation, mounting, re-keying) runs in a worker while
the dialog shows what it is doing; a busy dialog cannot be closed, so nothing
is ever left half done behind a closed window.
"""
from __future__ import annotations

import math
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QRectF, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QPainter, QPen
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
                             QPushButton, QRadioButton, QScrollArea, QFrame, QVBoxLayout,
                             QWidget)

from mazecapsule import __version__
from mazecapsule.core import atomic, gocrypt, settings, store
from mazecapsule.core.store import Capsule
from mazecapsule.gui import worker
from mazecapsule.gui.chrome import CopyButton, TitleBar, WindowButton, button, label
from mazecapsule.gui.glyphs import glyph, glyph_pixmap
from mazecapsule.gui.i18n import err, language, t

MIN_PASSWORD = 8
AUTOLOCK_CHOICES = (0, 15, 30, 60, 240)


def autolock_text(minutes: int) -> str:
    if minutes == 0:
        return t("autolock_off")
    if minutes < 60:
        return t("autolock_m", n=minutes)
    h = minutes // 60
    return t("autolock_h" if h == 1 else "autolock_hs", n=h)


def autolock_combo(current: int) -> QComboBox:
    box = QComboBox()
    for m in AUTOLOCK_CHOICES:
        box.addItem(autolock_text(m), m)
    best = min(range(len(AUTOLOCK_CHOICES)), key=lambda i: abs(AUTOLOCK_CHOICES[i] - current))
    box.setCurrentIndex(best)
    box.setCursor(Qt.CursorShape.PointingHandCursor)
    return box


# ── building blocks ──────────────────────────────────────────────────────────
class PasswordEdit(QLineEdit):
    def __init__(self, placeholder: str = "", key: bool = False):
        super().__init__()
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self.setPlaceholderText(placeholder)
        self.setMaxLength(1024)
        if key:
            self.setObjectName("keyfield")
        self._toggle = QAction(glyph("eye", 16, "#9a9aa0"), t("show_pw"), self)
        self._toggle.triggered.connect(self._flip)
        self.addAction(self._toggle, QLineEdit.ActionPosition.TrailingPosition)
        # No copy/cut out of a hidden password field.
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

    def _flip(self) -> None:
        hidden = self.echoMode() == QLineEdit.EchoMode.Password
        self.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self._toggle.setIcon(glyph("eye_off" if hidden else "eye", 16, "#9a9aa0"))
        self._toggle.setText(t("hide_pw" if hidden else "show_pw"))

    def wipe(self) -> None:
        self.setText("")


def strength(pw: str) -> int:
    """0 (too short) … 4 (strong), from length and character variety."""
    if len(pw) < MIN_PASSWORD:
        return 0
    pool = 0
    if any(c.islower() for c in pw):
        pool += 26
    if any(c.isupper() for c in pw):
        pool += 26
    if any(c.isdigit() for c in pw):
        pool += 10
    if any(not c.isalnum() and c.isascii() for c in pw):
        pool += 33
    if any(not c.isascii() for c in pw):
        pool += 60
    distinct = len(set(pw))
    bits = min(len(pw), distinct * 2) * math.log2(max(pool, 2))
    if bits < 40:
        return 1
    if bits < 60:
        return 2
    if bits < 85:
        return 3
    return 4


class StrengthMeter(QWidget):
    def __init__(self):
        super().__init__()
        self._score = -1
        self.setFixedHeight(22)
        self._label = ""

    def set_password(self, pw: str) -> None:
        self._score = -1 if not pw else strength(pw)
        self._label = "" if not pw else (t("strength_0", n=MIN_PASSWORD) if self._score == 0
                                         else t(f"strength_{self._score}"))
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        seg_w, gap = 34, 5
        for i in range(4):
            r = QRectF(i * (seg_w + gap), 8, seg_w, 5)
            on = self._score > i
            c = QColor("#f2f2f4") if on else QColor(255, 255, 255, 26)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(r, 2.5, 2.5)
        p.setPen(QColor("#9a9aa0") if self._score != 0 else QColor("#f2f2f4"))
        f = p.font()
        f.setPixelSize(11)
        f.setBold(self._score == 0)
        p.setFont(f)
        p.drawText(QRectF(4 * (seg_w + gap) + 6, 0, self.width(), 22),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)
        p.end()


class Dialog(QDialog):
    """Frameless black dialog: header with title and ✕, body, button row."""

    def __init__(self, parent: QWidget | None, title: str, width: int = 520):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setFixedWidth(width)
        self._busy = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)

        head = TitleBar(self, name="dlg_header")
        head.setFixedHeight(56)
        h = QHBoxLayout(head)
        h.setContentsMargins(24, 0, 0, 0)
        self._title = label(title, "dlg_title")
        h.addWidget(self._title)
        h.addStretch(1)
        self._close = WindowButton("win_close", t("tip_close"))
        self._close.clicked.connect(self.reject)
        h.addWidget(self._close)
        outer.addWidget(head)

        body = QWidget()
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(24, 4, 24, 6)
        self.body.setSpacing(10)
        outer.addWidget(body)

        status = QWidget()
        sv = QVBoxLayout(status)
        sv.setContentsMargins(24, 0, 24, 0)
        sv.setSpacing(0)
        self._error = label("", "error", wrap=True)
        self._error.hide()
        self._status = label("", "hint", wrap=True)
        self._status.hide()
        sv.addWidget(self._error)
        sv.addWidget(self._status)
        outer.addWidget(status)

        foot = QWidget()
        self.buttons = QHBoxLayout(foot)
        self.buttons.setContentsMargins(24, 14, 24, 22)
        self.buttons.setSpacing(10)
        self.buttons.addStretch(1)
        outer.addWidget(foot)

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0a0a0b"))
        p.setPen(QPen(QColor(255, 255, 255, 36), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()

    # helpers
    def add_field(self, title: str, widget: QWidget, hint: str | None = None) -> None:
        self.body.addSpacing(2)
        self.body.addWidget(label(title, "field"))
        self.body.addWidget(widget)
        if hint:
            self.body.addWidget(label(hint, "hint", wrap=True))

    def add_text(self, text: str, name: str = "tagline") -> QLabel:
        lb = label(text, name, wrap=True)
        self.body.addWidget(lb)
        return lb

    def add_button(self, text: str, name: str = "secondary_lg", icon: str | None = None) -> QPushButton:
        b = button(text, name, icon)
        self.buttons.addWidget(b)
        return b

    def set_error(self, text: str | None) -> None:
        self._error.setText(text or "")
        self._error.setVisible(bool(text))
        self.adjustSize()

    def set_busy(self, text: str | None) -> None:
        self._busy = bool(text)
        self._status.setText(text or "")
        self._status.setVisible(bool(text))
        for w in self.findChildren(QWidget):
            if isinstance(w, (QPushButton, QLineEdit, QCheckBox, QComboBox, QRadioButton)):
                w.setEnabled(not self._busy)
        if not self._busy:
            self._after_unbusy()
        self.adjustSize()

    def _after_unbusy(self) -> None:
        """Re-apply enabled/disabled rules after set_busy(None)."""

    def run(self, busy_text: str, fn: Callable[..., Any], *args,
            on_done: Callable[[Any], None], on_fail: Callable[[BaseException], None] | None = None,
            **kwargs) -> None:
        self.set_error(None)
        self.set_busy(busy_text)

        def done(r: Any) -> None:
            self.set_busy(None)
            on_done(r)

        def fail(e: BaseException) -> None:
            self.set_busy(None)
            (on_fail or (lambda x: self.set_error(err(x))))(e)
        worker.run(fn, *args, on_done=done, on_fail=fail, **kwargs)

    def reject(self) -> None:
        if not self._busy:
            super().reject()

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        self.adjustSize()


def _is_wrong_password(e: BaseException) -> bool:
    return getattr(e, "reason", "") == "wrong_password"


# ── new capsule ──────────────────────────────────────────────────────────────
class NewCapsuleDialog(Dialog):
    def __init__(self, parent: QWidget | None):
        super().__init__(parent, t("new_title"), 540)
        self.result_value: tuple[Capsule, str, Path | None] | None = None
        self._folder: Path | None = None

        self.name = QLineEdit()
        self.name.setPlaceholderText(t("ph_name"))
        self.name.setMaxLength(store.NAME_MAX)
        self.add_field(t("f_name"), self.name)

        self.pw = PasswordEdit()
        self.add_field(t("f_password"), self.pw)
        self.meter = StrengthMeter()
        self.body.addWidget(self.meter)
        self.pw2 = PasswordEdit()
        self.add_field(t("f_confirm"), self.pw2)
        self.body.addWidget(label(t("pw_hint"), "hint", wrap=True))

        self.body.addSpacing(2)
        self.body.addWidget(label(t("f_location"), "field"))
        self.r_default = QRadioButton(t("loc_default_opt"))
        self.r_custom = QRadioButton(t("loc_custom_opt"))
        self.r_default.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.r_default)
        grp.addButton(self.r_custom)
        self.body.addWidget(self.r_default)
        self.body.addWidget(self.r_custom)
        row = QHBoxLayout()
        row.setContentsMargins(26, 0, 0, 0)
        self.choose = button(t("loc_choose"), "secondary", "usb")
        self.choose.clicked.connect(self._pick)
        self.folder_lbl = label(t("loc_none"), "path")
        row.addWidget(self.choose)
        row.addWidget(self.folder_lbl, 1)
        self.body.addLayout(row)
        self.r_custom.toggled.connect(self._after_unbusy)
        self.body.addSpacing(2)
        self.body.addWidget(label(t("name_visible"), "hint", wrap=True))

        cancel = self.add_button(t("btn_cancel"), "secondary_lg")
        cancel.clicked.connect(self.reject)
        self.ok = self.add_button(t("btn_create"), "get_lg", "plus")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._create)
        for w in (self.name, self.pw, self.pw2):
            w.textChanged.connect(self._after_unbusy)
        self.pw.textChanged.connect(self.meter.set_password)
        self._after_unbusy()

    def _pick(self) -> None:
        d = QFileDialog.getExistingDirectory(self, t("loc_choose"), str(Path.home()))
        if d:
            self._folder = Path(d)
            self.folder_lbl.setText(d)
            self.r_custom.setChecked(True)
        self._after_unbusy()

    def _after_unbusy(self) -> None:
        self.choose.setEnabled(self.r_custom.isChecked() and not self._busy)
        ok = (bool(self.name.text().strip()) and len(self.pw.text()) >= MIN_PASSWORD
              and bool(self.pw2.text()) and (not self.r_custom.isChecked() or self._folder is not None))
        self.ok.setEnabled(ok and not self._busy)

    def _create(self) -> None:
        if not self.ok.isEnabled():
            return
        try:
            name = store.clean_name(self.name.text())
        except store.CapsuleError as e:
            self.set_error(err(e))
            return
        if self.pw.text() != self.pw2.text():
            self.set_error(t("pw_mismatch"))
            return
        parent = self._folder if self.r_custom.isChecked() else None
        pw = self.pw.text()

        idle = settings.load()["idle_minutes"]

        def job() -> tuple[Capsule, str, Path | None]:
            capsule, key = store.create(name, pw, parent)
            # Open it straight away, so the next step is putting files in. A
            # failure here leaves a perfectly good locked capsule.
            try:
                mp = store.unlock(capsule, password=pw, idle_minutes=idle)
            except Exception:  # noqa: BLE001
                mp = None
            return capsule, key, mp

        def done(r) -> None:
            self.pw.wipe()
            self.pw2.wipe()
            self.result_value = r
            self.accept()
        self.run(t("creating"), job, on_done=done)


# ── recovery key ─────────────────────────────────────────────────────────────
class RecoveryKeyDialog(Dialog):
    def __init__(self, parent: QWidget | None, capsule: Capsule, key_hex: str, new: bool):
        super().__init__(parent, t("rk_title"), 600)
        self._capsule = capsule
        self._key = gocrypt.format_master_key(key_hex)
        self._new = new
        groups = self._key.split("-")

        self.add_text(t("rk_body_new" if new else "rk_body_show", name=capsule.name))
        shown = label("-".join(groups[:4]) + "-\n" + "-".join(groups[4:]), "recovery")
        shown.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        shown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addWidget(shown)

        row = QHBoxLayout()
        row.setSpacing(8)
        copy = CopyButton(t("btn_copy"), self._key)
        copy.clicked.connect(self._arm_clipboard_clear)
        row.addWidget(copy)
        save = button(t("btn_save_file"), "secondary", "save")
        save.clicked.connect(self._save)
        row.addWidget(save)
        row.addStretch(1)
        self.body.addLayout(row)
        self._saved = label("", "hint", wrap=True)
        self._saved.hide()
        self.body.addWidget(self._saved)

        if new:
            self.body.addSpacing(6)
            self.stored = QCheckBox(t("rk_stored"))
            self.stored.setCursor(Qt.CursorShape.PointingHandCursor)
            self.body.addWidget(self.stored)
            self.tail = QLineEdit()
            self.tail.setObjectName("keyfield")
            self.tail.setMaxLength(12)
            self.tail.setPlaceholderText("xxxxxxxx")
            self.body.addWidget(label(t("rk_confirm"), "tagline", wrap=True))
            self.body.addWidget(self.tail)
            later = self.add_button(t("rk_later_btn"), "ghost")
            later.clicked.connect(self._later)
            self.done_btn = self.add_button(t("btn_done"), "get_lg", "check")
            self.done_btn.clicked.connect(self._finish)
            self.stored.toggled.connect(self._after_unbusy)
            self.tail.textChanged.connect(self._after_unbusy)
            self._after_unbusy()
        else:
            self.done_btn = self.add_button(t("btn_done"), "get_lg", "check")
            self.done_btn.clicked.connect(self.accept)

    def _after_unbusy(self) -> None:
        if self._new:
            typed = self.tail.text().strip().lower().replace("-", "")
            self.done_btn.setEnabled(self.stored.isChecked() and len(typed) == 8)

    def _finish(self) -> None:
        typed = self.tail.text().strip().lower().replace("-", "")
        if typed != self._key.replace("-", "")[-8:]:
            self.set_error(t("rk_wrong"))
            return
        self.accept()

    def _later(self) -> None:
        c = ConfirmDialog(self, t("rk_later_title"), t("rk_later_body"), t("rk_later_btn"))
        if c.exec():
            self.reject()

    def reject(self) -> None:
        # Closing a fresh key with ✕ / Esc asks first, like "Save it later".
        if self._new and self.sender() is self._close:
            self._later()
            return
        super().reject()

    def _arm_clipboard_clear(self) -> None:
        # Do not leave the key on the clipboard for long.
        key = self._key

        def clear() -> None:
            cb = QApplication.clipboard()
            if cb is not None and cb.text() == key:
                cb.clear()
        QTimer.singleShot(60_000, clear)

    def _save(self) -> None:
        safe = store._folder_name(self._capsule.name)
        suggested = str(Path.home() / f"{safe} - recovery key.txt")
        path, _ = QFileDialog.getSaveFileName(self, t("btn_save_file"), suggested,
                                              "Text (*.txt);;All files (*)")
        if not path:
            return
        text = t("rk_file_note", name=self._capsule.name,
                 date=datetime.now().strftime("%Y-%m-%d"), recovery_key=self._key)
        try:
            atomic.write_bytes(Path(path), text.encode(), mode=0o600)
        except OSError as e:
            self.set_error(err(e))
            return
        self._saved.setText(t("rk_saved_to", path=path))
        self._saved.show()
        self.adjustSize()


# ── unlock ───────────────────────────────────────────────────────────────────
class UnlockDialog(Dialog):
    def __init__(self, parent: QWidget | None, capsule: Capsule, idle_default: int,
                 start_with_key: bool = False):
        super().__init__(parent, t("unlock_title", name=capsule.name), 500)
        self._c = capsule
        self.mountpoint: Path | None = None
        self.used_key: str | None = None

        self.pw_box = QWidget()
        v = QVBoxLayout(self.pw_box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        v.addWidget(label(t("f_password"), "field"))
        self.pw = PasswordEdit()
        v.addWidget(self.pw)
        self.body.addWidget(self.pw_box)

        self.key_box = QWidget()
        v = QVBoxLayout(self.key_box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        v.addWidget(label(t("f_recovery"), "field"))
        self.key = PasswordEdit(t("ph_recovery"), key=True)
        self.key.setMaxLength(100)
        v.addWidget(self.key)
        self.body.addWidget(self.key_box)
        self.key_box.hide()

        self.switch = button(t("unlock_forgot"), "ghost", "key")
        self.switch.clicked.connect(self._toggle)
        sw = QHBoxLayout()
        sw.setContentsMargins(-14, 0, 0, 0)
        sw.addWidget(self.switch)
        sw.addStretch(1)
        self.body.addLayout(sw)

        self.ro = QCheckBox(t("unlock_ro"))
        self.ro.setCursor(Qt.CursorShape.PointingHandCursor)
        self.body.addWidget(self.ro)
        self.idle = autolock_combo(idle_default)
        self.add_field(t("f_autolock"), self.idle)

        cancel = self.add_button(t("btn_cancel"), "secondary_lg")
        cancel.clicked.connect(self.reject)
        self.ok = self.add_button(t("btn_unlock"), "get_lg", "unlock")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._unlock)
        self.pw.textChanged.connect(self._after_unbusy)
        self.key.textChanged.connect(self._after_unbusy)
        if start_with_key:
            self._toggle()
        self._after_unbusy()
        QTimer.singleShot(0, lambda: (self.key if self.key_box.isVisible() else self.pw).setFocus())

    def _using_key(self) -> bool:
        return self.key_box.isVisible()

    def _toggle(self) -> None:
        use_key = not self._using_key()
        self.key_box.setVisible(use_key)
        self.pw_box.setVisible(not use_key)
        self.switch.setText(t("unlock_use_pw" if use_key else "unlock_forgot"))
        self.set_error(None)
        (self.key if use_key else self.pw).setFocus()
        self._after_unbusy()

    def _after_unbusy(self) -> None:
        field = self.key if self._using_key() else self.pw
        self.ok.setEnabled(bool(field.text()) and not self._busy)

    def _unlock(self) -> None:
        if not self.ok.isEnabled():
            return
        kw: dict = {"read_only": self.ro.isChecked(), "idle_minutes": int(self.idle.currentData())}
        if self._using_key():
            try:
                self.used_key = gocrypt.normalize_master_key(self.key.text())
            except gocrypt.GocryptError as e:
                self.set_error(err(e))
                return
            kw["master_key"] = self.used_key
        else:
            kw["password"] = self.pw.text()

        def done(mp: Path) -> None:
            self.pw.wipe()
            self.mountpoint = mp
            self.accept()

        def fail(e: BaseException) -> None:
            self.set_error(err(e))
            if _is_wrong_password(e):
                self.pw.selectAll()
                self.pw.setFocus()
        self.run(t("unlocking"), store.unlock, self._c, on_done=done, on_fail=fail, **kw)


# ── password prompt ──────────────────────────────────────────────────────────
class PasswordAskDialog(Dialog):
    """Asks for the password and runs fn(password) in the background."""

    def __init__(self, parent: QWidget | None, capsule: Capsule, prompt: str, busy_text: str,
                 fn: Callable[[str], Any], ok_text: str):
        super().__init__(parent, t("ask_pw_title", name=capsule.name), 480)
        self.result_value: Any = None
        self._fn = fn
        self._busy_text = busy_text
        self.add_text(prompt)
        self.pw = PasswordEdit()
        self.add_field(t("f_password"), self.pw)
        cancel = self.add_button(t("btn_cancel"), "secondary_lg")
        cancel.clicked.connect(self.reject)
        self.ok = self.add_button(ok_text, "get_lg")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._go)
        self.pw.textChanged.connect(self._after_unbusy)
        self._after_unbusy()

    def _after_unbusy(self) -> None:
        self.ok.setEnabled(bool(self.pw.text()) and not self._busy)

    def _go(self) -> None:
        if not self.ok.isEnabled():
            return

        def done(r: Any) -> None:
            self.pw.wipe()
            self.result_value = r
            self.accept()

        def fail(e: BaseException) -> None:
            self.set_error(err(e))
            self.pw.selectAll()
            self.pw.setFocus()
        self.run(self._busy_text, self._fn, self.pw.text(), on_done=done, on_fail=fail)


# ── change password ──────────────────────────────────────────────────────────
class ChangePasswordDialog(Dialog):
    def __init__(self, parent: QWidget | None, capsule: Capsule, master_key: str | None = None):
        super().__init__(parent, t("cp_title"), 520)
        self._c = capsule
        self._given_key = master_key
        self.add_text(t("cp_body"))

        self.cur_box = QWidget()
        v = QVBoxLayout(self.cur_box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self.cur_title = label(t("f_current"), "field")
        v.addWidget(self.cur_title)
        self.cur = PasswordEdit()
        v.addWidget(self.cur)
        self.use_key = False
        self.switch = button(t("cp_use_rk"), "ghost", "key")
        self.switch.clicked.connect(self._toggle)
        sw = QHBoxLayout()
        sw.setContentsMargins(-14, 0, 0, 0)
        sw.addWidget(self.switch)
        sw.addStretch(1)
        v.addLayout(sw)
        self.body.addWidget(self.cur_box)
        if master_key is not None:
            self.cur_box.hide()

        self.new = PasswordEdit()
        self.add_field(t("f_new"), self.new)
        self.meter = StrengthMeter()
        self.body.addWidget(self.meter)
        self.new2 = PasswordEdit()
        self.add_field(t("f_confirm"), self.new2)

        cancel = self.add_button(t("btn_cancel"), "secondary_lg")
        cancel.clicked.connect(self.reject)
        self.ok = self.add_button(t("btn_save"), "get_lg", "check")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._go)
        for w in (self.cur, self.new, self.new2):
            w.textChanged.connect(self._after_unbusy)
        self.new.textChanged.connect(self.meter.set_password)
        self._after_unbusy()

    def _toggle(self) -> None:
        self.use_key = not self.use_key
        self.cur_title.setText(t("f_recovery" if self.use_key else "f_current"))
        self.cur.setPlaceholderText(t("ph_recovery") if self.use_key else "")
        self.cur.setObjectName("keyfield" if self.use_key else "")
        self.cur.style().unpolish(self.cur)
        self.cur.style().polish(self.cur)
        self.cur.setMaxLength(100 if self.use_key else 1024)
        self.cur.clear()
        self.switch.setText(t("unlock_use_pw") if self.use_key else t("cp_use_rk"))
        self.cur.setFocus()

    def _after_unbusy(self) -> None:
        have_cur = self._given_key is not None or bool(self.cur.text())
        self.ok.setEnabled(have_cur and len(self.new.text()) >= MIN_PASSWORD
                           and bool(self.new2.text()) and not self._busy)

    def _go(self) -> None:
        if not self.ok.isEnabled():
            return
        if self.new.text() != self.new2.text():
            self.set_error(t("pw_mismatch"))
            return
        kw: dict = {}
        if self._given_key is not None:
            kw["master_key"] = self._given_key
        elif self.use_key:
            try:
                kw["master_key"] = gocrypt.normalize_master_key(self.cur.text())
            except gocrypt.GocryptError as e:
                self.set_error(err(e))
                return
        else:
            kw["old_password"] = self.cur.text()

        def done(_r) -> None:
            for w in (self.cur, self.new, self.new2):
                w.wipe()
            self.accept()
        self.run(t("cp_working"), store.change_password, self._c, self.new.text(),
                 on_done=done, **kw)


# ── small dialogs ────────────────────────────────────────────────────────────
class TextDialog(Dialog):
    def __init__(self, parent: QWidget | None, title: str, field_title: str, initial: str,
                 validate: Callable[[str], str]):
        super().__init__(parent, title, 460)
        self.value: str | None = None
        self._validate = validate
        self.edit = QLineEdit(initial)
        self.edit.setMaxLength(store.NAME_MAX)
        self.edit.selectAll()
        self.add_field(field_title, self.edit)
        cancel = self.add_button(t("btn_cancel"), "secondary_lg")
        cancel.clicked.connect(self.reject)
        self.ok = self.add_button(t("btn_save"), "get_lg", "check")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._go)

    def _go(self) -> None:
        try:
            self.value = self._validate(self.edit.text())
        except Exception as e:  # noqa: BLE001 — validation message
            self.set_error(err(e))
            return
        self.accept()


class ConfirmDialog(Dialog):
    def __init__(self, parent: QWidget | None, title: str, body: str, confirm_text: str,
                 danger: bool = False, typed: str | None = None, icon: str | None = None):
        super().__init__(parent, title, 500)
        if icon:
            row = QHBoxLayout()
            ic = QLabel()
            ic.setPixmap(glyph_pixmap(icon, 26))
            row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
            row.addSpacing(6)
            row.addWidget(label(body, "tagline", wrap=True), 1)
            self.body.addLayout(row)
        else:
            self.add_text(body)
        self._typed = typed
        if typed is not None:
            self.typed = QLineEdit()
            self.typed.setPlaceholderText(typed)
            self.add_field(t("purge_type"), self.typed)
        cancel = self.add_button(t("btn_cancel"), "secondary_lg")
        cancel.clicked.connect(self.reject)
        self.ok = self.add_button(confirm_text, "danger_lg" if danger else "get_lg")
        self.ok.clicked.connect(self.accept)
        if typed is not None:
            self.ok.setEnabled(False)
            self.typed.textChanged.connect(lambda s: self.ok.setEnabled(s.strip() == typed))
        else:
            self.ok.setDefault(not danger)


class ChoiceDialog(Dialog):
    def __init__(self, parent: QWidget | None, title: str, body: str,
                 choices: list[tuple[str, str, str]], icon: str | None = None):
        super().__init__(parent, title, 540)
        self.choice: str | None = None
        if icon:
            row = QHBoxLayout()
            ic = QLabel()
            ic.setPixmap(glyph_pixmap(icon, 26))
            row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
            row.addSpacing(6)
            row.addWidget(label(body, "tagline", wrap=True), 1)
            self.body.addLayout(row)
        else:
            self.add_text(body)
        for key, text, name in choices:
            b = self.add_button(text, name)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))

    def _pick(self, key: str) -> None:
        self.choice = key
        self.accept()


class MessageDialog(Dialog):
    def __init__(self, parent: QWidget | None, title: str, body: str, icon: str = "shield_ok",
                 report: str | None = None):
        super().__init__(parent, title, 560)
        row = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(glyph_pixmap(icon, 30))
        row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        row.addSpacing(8)
        row.addWidget(label(body, "tagline", wrap=True), 1)
        self.body.addLayout(row)
        if report:
            rep = label(report.strip(), "report", wrap=False)
            rep.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            sc = QScrollArea()
            sc.setWidget(rep)
            sc.setWidgetResizable(True)
            sc.setFrameShape(QFrame.Shape.NoFrame)
            sc.setFixedHeight(min(rep.sizeHint().height() + 6, 220))
            self.body.addWidget(sc)
        ok = self.add_button(t("btn_close"), "get_lg")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)


class ProgressDialog(Dialog):
    """Determinate progress with Cancel. `cancel_event` is read by the worker."""

    def __init__(self, parent: QWidget | None, title: str):
        super().__init__(parent, title, 520)
        self.cancel_event = threading.Event()
        self.current = label(" ", "path")
        self.body.addWidget(self.current)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.body.addWidget(self.bar)
        self.amount = label(" ", "hint")
        self.body.addWidget(self.amount)
        self.cancel = self.add_button(t("btn_cancel"), "secondary_lg")
        self.cancel.clicked.connect(self._cancel)
        self._close.hide()

    def set_progress(self, done: int, total: int, name: str = "") -> None:
        from mazecapsule.gui.i18n import human_size
        self.bar.setValue(int(1000 * done / total) if total else 0)
        if name:
            self.current.setText(self.current.fontMetrics().elidedText(
                name, Qt.TextElideMode.ElideMiddle, 460))
        self.amount.setText(f"{human_size(done)} / {human_size(total)}")

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.cancel.setEnabled(False)

    def reject(self) -> None:
        self._cancel()  # Esc means cancel; the window closes when the worker stops

    def finish(self) -> None:
        QDialog.accept(self)


class SettingsDialog(Dialog):
    language_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None):
        super().__init__(parent, t("st_title"), 500)
        s = settings.load()
        self.body.addWidget(label(t("st_language"), "field"))
        row = QHBoxLayout()
        row.setSpacing(6)
        self._seg: dict[str, QPushButton] = {}
        for code, text in (("en", "English"), ("tr", "Türkçe")):
            b = QPushButton(text, objectName="seg_on" if language() == code else "seg")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=code: self._lang(c))
            row.addWidget(b)
            self._seg[code] = b
        row.addStretch(1)
        self.body.addLayout(row)

        self.idle = autolock_combo(s["idle_minutes"])
        self.idle.currentIndexChanged.connect(
            lambda _i: settings.save(idle_minutes=int(self.idle.currentData())))
        self.add_field(t("st_autolock"), self.idle, t("st_autolock_note"))

        self.body.addSpacing(2)
        self.body.addWidget(label(t("st_sandbox"), "field"))
        self.net = QCheckBox(t("st_sandbox_net"))
        self.net.setChecked(s["sandbox_network"])
        self.net.setCursor(Qt.CursorShape.PointingHandCursor)
        self.net.toggled.connect(lambda v: settings.save(sandbox_network=bool(v)))
        self.body.addWidget(self.net)

        self.body.addSpacing(8)
        self.body.addWidget(label(t("st_about", ver=__version__, gv=gocrypt.version() or "—"), "hint"))
        ok = self.add_button(t("btn_done"), "get_lg", "check")
        ok.clicked.connect(self.accept)

    def _lang(self, code: str) -> None:
        settings.save(language=code)
        self.language_changed.emit(code)
        self.accept()

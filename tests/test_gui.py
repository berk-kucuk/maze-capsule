"""GUI smoke tests, offscreen: every page and dialog builds in both languages,
and every English string has a Turkish one."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mazecapsule.gui.i18n import STRINGS  # noqa: E402


class StringsTests(unittest.TestCase):
    def test_turkish_complete(self) -> None:
        missing = sorted(set(STRINGS["en"]) - set(STRINGS["tr"]))
        self.assertEqual(missing, [])

    def test_every_string_formats_through_t(self) -> None:
        # A placeholder named like t()'s own parameter once crashed the app.
        from mazecapsule.gui import i18n
        for lang in ("en", "tr"):
            i18n.set_language(lang)
            for key, text in STRINGS[lang].items():
                kw = {p: "x" for p in re.findall(r"{(\w+)}", text)}
                out = i18n.t(key, **kw)
                self.assertNotIn("{", out.replace("{{", ""), (lang, key))
        i18n.set_language("en")

    def test_placeholders_match(self) -> None:
        for key, en in STRINGS["en"].items():
            tr = STRINGS["tr"].get(key, "")
            self.assertEqual(set(re.findall(r"{(\w+)}", en)), set(re.findall(r"{(\w+)}", tr)), key)

    def test_every_used_key_exists(self) -> None:
        root = Path(__file__).resolve().parents[1] / "mazecapsule"
        used = set()
        for f in root.rglob("*.py"):
            used |= set(re.findall(r'\bt\("([a-z0-9_]+)"', f.read_text()))
        self.assertEqual(sorted(used - set(STRINGS["en"])), [])


try:
    from PyQt6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:  # pragma: no cover
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PyQt6 missing")
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="maze-capsule-gui-"))
        self._env = {k: os.environ.get(k) for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_RUNTIME_DIR")}
        os.environ["XDG_DATA_HOME"] = str(self.tmp / "data")
        os.environ["XDG_CONFIG_HOME"] = str(self.tmp / "config")
        rt = self.tmp / "run"
        rt.mkdir(mode=0o700)
        os.environ["XDG_RUNTIME_DIR"] = str(rt)

    def tearDown(self) -> None:
        from mazecapsule.core import mounts
        for m in mounts.gocryptfs_mounts():
            if m.target.startswith(str(self.tmp)):
                subprocess.run(["fusermount3", "-u", "-z", m.target], check=False)
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_window_and_dialogs_build(self) -> None:
        from mazecapsule.core import gocrypt, store
        from mazecapsule.gui import dialogs
        from mazecapsule.gui.i18n import set_language
        from mazecapsule.gui.window import MainWindow

        caps = []
        if gocrypt.available() and os.access("/dev/fuse", os.R_OK | os.W_OK):
            n = gocrypt.SCRYPT_N
            gocrypt.SCRYPT_N = 10
            try:
                a, _ = store.create("A", "password123")
                b, _ = store.create("B", "password123")
                store.unlock(b, password="password123")
                caps = [a, b]
                store.trash(a)
            finally:
                gocrypt.SCRYPT_N = n
        for lang in ("en", "tr"):
            set_language(lang)
            w = MainWindow()
            w._show_trash = True
            w.refresh(force=True)
            w.grab()
            if caps:
                b = store.get(caps[1].id)
                for d in (dialogs.UnlockDialog(w, b, 30), dialogs.ChangePasswordDialog(w, b),
                          dialogs.RecoveryKeyDialog(w, b, "ab" * 32, True),
                          dialogs.RecoveryKeyDialog(w, b, "ab" * 32, False),
                          dialogs.NewCapsuleDialog(w), dialogs.SettingsDialog(w),
                          dialogs.ConfirmDialog(w, "x", "y", "z", danger=True, typed="B")):
                    d.grab()
                    d.deleteLater()
            w._poll.stop()
            w.deleteLater()
            from PyQt6.QtCore import QCoreApplication, QEvent, QThreadPool
            QThreadPool.globalInstance().waitForDone(10_000)
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
            import gc
            gc.collect()
        set_language("en")
        if caps:
            store.lock_all(lazy=True)

    def test_recovery_key_saved_to_file(self) -> None:
        from unittest import mock
        from mazecapsule.core.store import Capsule
        from mazecapsule.gui import dialogs
        from mazecapsule.gui.i18n import set_language
        c = Capsule(id="x", name="Docs", root=self.tmp, cipherdir=self.tmp / "vault", created=0)
        for lang in ("en", "tr"):
            set_language(lang)
            out = self.tmp / f"key-{lang}.txt"
            d = dialogs.RecoveryKeyDialog(None, c, "ab" * 32, new=True)
            with mock.patch.object(dialogs.QFileDialog, "getSaveFileName", return_value=(str(out), "")):
                d._save()
            text = out.read_text()
            self.assertIn("abababab-abababab", text)
            self.assertIn("Docs", text)
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        set_language("en")

    def test_strength(self) -> None:
        from mazecapsule.gui.dialogs import strength
        self.assertEqual(strength("short"), 0)
        self.assertLessEqual(strength("aaaaaaaaaaaa"), 1)
        self.assertGreaterEqual(strength("correct horse battery staple"), 3)


if __name__ == "__main__":
    unittest.main()

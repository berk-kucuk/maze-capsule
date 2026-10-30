"""Core tests against the real gocryptfs, in throwaway XDG folders.

Every test runs with its own XDG_DATA_HOME / XDG_CONFIG_HOME / XDG_RUNTIME_DIR
under a temp dir, mounts real capsules through FUSE and locks them again in
tearDown. Nothing outside the temp dir is touched. Tests that need FUSE are
skipped where /dev/fuse cannot be used (some build chroots).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mazecapsule.core import atomic, gocrypt, mounts, paths, sandbox, settings, store, transfer  # noqa: E402
from mazecapsule.core.gocrypt import GocryptError  # noqa: E402
from mazecapsule.core.store import CapsuleError  # noqa: E402

PW = "correct horse battery"
PW2 = "a whole new password"


def _fuse_ok() -> bool:
    if not gocrypt.available() or not os.access("/dev/fuse", os.R_OK | os.W_OK):
        return False
    with tempfile.TemporaryDirectory() as d:
        c, m = Path(d, "c"), Path(d, "m")
        c.mkdir(), m.mkdir()
        try:
            subprocess.run(["gocryptfs", "-init", "-q", "-scryptn", "10", str(c)],
                           input=b"x\n", check=True, capture_output=True, timeout=60)
            r = subprocess.run(["gocryptfs", "-q", str(c), str(m)],
                               input=b"x\n", capture_output=True, timeout=60)
            if r.returncode != 0:
                return False
            subprocess.run(["fusermount3", "-u", str(m)], check=False, timeout=30)
            return True
        except (OSError, subprocess.SubprocessError):
            return False


FUSE = _fuse_ok()
needs_fuse = unittest.skipUnless(FUSE, "gocryptfs/FUSE not usable here")


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="maze-capsule-test-"))
        self._env = {k: os.environ.get(k) for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_RUNTIME_DIR")}
        os.environ["XDG_DATA_HOME"] = str(self.tmp / "data")
        os.environ["XDG_CONFIG_HOME"] = str(self.tmp / "config")
        rt = self.tmp / "run"
        rt.mkdir(mode=0o700)
        os.environ["XDG_RUNTIME_DIR"] = str(rt)
        # Fast scrypt for tests only.
        self._n = gocrypt.SCRYPT_N
        gocrypt.SCRYPT_N = 10

    def tearDown(self) -> None:
        for m in mounts.gocryptfs_mounts():
            if m.target.startswith(str(self.tmp)):
                subprocess.run(["fusermount3", "-u", "-z", m.target], check=False)
        gocrypt.SCRYPT_N = self._n
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)


class AtomicTests(Base):
    def test_write_and_backup_fallback(self) -> None:
        p = self.tmp / "x.json"
        atomic.write_json(p, {"v": 1})
        atomic.write_json(p, {"v": 2})
        self.assertEqual(atomic.read_json(p), {"v": 2})
        self.assertEqual(json.loads((self.tmp / "x.json.bak").read_text()), {"v": 1})
        p.write_text("{garbage")
        self.assertEqual(atomic.read_json(p), {"v": 1})

    def test_corrupt_file_never_replaces_good_backup(self) -> None:
        p = self.tmp / "x.json"
        atomic.write_json(p, {"v": 1})
        atomic.write_json(p, {"v": 2})
        p.write_text("{garbage")
        atomic.write_json(p, {"v": 3})
        self.assertEqual(json.loads((self.tmp / "x.json.bak").read_text()), {"v": 1})

    def test_no_temp_files_left(self) -> None:
        atomic.write_bytes(self.tmp / "a", b"1")
        self.assertEqual(sorted(x.name for x in self.tmp.iterdir() if x.is_file()), ["a"])


class MountinfoTests(unittest.TestCase):
    def test_parse_and_unescape(self) -> None:
        line = ("382 216 0:135 / /run/user/1000/maze-capsule/My\\040Files rw,nosuid shared:6 - "
                "fuse.gocryptfs /home/u/.local/share/maze-capsule/capsules/ab/vault rw,user_id=1000\n"
                "22 1 0:21 / /proc rw - proc proc rw\n")
        ms = mounts.parse(line)
        self.assertEqual(len(ms), 1)
        self.assertEqual(ms[0].target, "/run/user/1000/maze-capsule/My Files")
        self.assertTrue(ms[0].source.endswith("/vault"))


class KeyFormatTests(unittest.TestCase):
    def test_master_key_roundtrip(self) -> None:
        k = "bb9ec879a7b14672fc1c01bdfae8539064a5fe5c9298010f6ab5b9044f291609"
        f = gocrypt.format_master_key(k)
        self.assertEqual(f.count("-"), 7)
        self.assertEqual(gocrypt.normalize_master_key(f.upper().replace("-", " ")), k)
        with self.assertRaises(GocryptError):
            gocrypt.normalize_master_key(k[:-1])

    def test_secret_rules(self) -> None:
        for bad in ("", "a\nb", "x" * 2000):
            with self.assertRaises(GocryptError):
                gocrypt.check_secret(bad)


class NameTests(unittest.TestCase):
    def test_clean_name(self) -> None:
        self.assertEqual(store.clean_name("  Work   files "), "Work files")
        for bad in ("", "   ", "a/b", "x" * 65, ".."):
            with self.assertRaises(CapsuleError):
                store.clean_name(bad)


@needs_fuse
class CapsuleTests(Base):
    def _make(self, name: str = "Private", parent: Path | None = None):
        return store.create(name, PW, parent)

    def test_create_unlock_write_lock_reopen(self) -> None:
        c, key = self._make()
        self.assertEqual(len(gocrypt.normalize_master_key(key)), 64)
        self.assertTrue((c.root / "README.txt").is_file())
        self.assertTrue(c.key_backup.is_file())
        self.assertEqual(c.key_backup.read_bytes(), c.conf.read_bytes())
        mp = store.unlock(c, password=PW)
        self.assertTrue(c.unlocked)
        (mp / "secret.txt").write_text("hello")
        (mp / "folder").mkdir()
        store.lock(c)
        self.assertFalse(c.unlocked)
        self.assertFalse(mp.exists())  # empty mount point removed
        # Nothing readable in the cipher dir.
        for p in c.cipherdir.rglob("*"):
            if p.is_file():
                self.assertNotIn(b"hello", p.read_bytes())
            self.assertNotIn("secret", p.name)
        mp = store.unlock(c, password=PW)
        self.assertEqual((mp / "secret.txt").read_text(), "hello")
        store.lock(c)

    def test_no_staging_left_and_listed(self) -> None:
        c, _ = self._make("A")
        self._make("B")
        names = [x.name for x in store.list_capsules()]
        self.assertEqual(names, ["A", "B"])
        self.assertFalse([p for p in paths.capsules_dir().iterdir() if p.name.startswith(".")])
        self.assertEqual(store.get(c.id).name, "A")

    def test_wrong_password(self) -> None:
        c, _ = self._make()
        with self.assertRaises(GocryptError) as cm:
            store.unlock(c, password="nope nope")
        self.assertEqual(cm.exception.reason, "wrong_password")
        self.assertFalse(c.unlocked)
        self.assertEqual(list(paths.runtime_dir().glob("Private*")), [])

    def test_failed_create_removes_only_its_staging(self) -> None:
        orig = gocrypt.init

        def boom(*a, **k):
            orig(*a, **k)
            raise GocryptError("failed", "simulated")
        gocrypt.init = boom
        try:
            with self.assertRaises(GocryptError):
                self._make()
        finally:
            gocrypt.init = orig
        self.assertEqual(list(paths.capsules_dir().iterdir()), [])

    def test_staging_with_foreign_files_is_kept(self) -> None:
        st = self.tmp / "stage"
        st.mkdir()
        (st / "vault").mkdir()
        (st / "vault" / "user-file").write_text("x")
        store._remove_fresh_staging(st)
        self.assertTrue((st / "vault" / "user-file").exists())

    def test_recovery_key_opens_after_conf_lost(self) -> None:
        c, key = self._make()
        mp = store.unlock(c, password=PW)
        (mp / "a").write_text("data")
        store.lock(c)
        c.conf.chmod(0o600)
        c.conf.unlink()
        c.key_backup.chmod(0o600)
        c.key_backup.unlink()
        mp = store.unlock(c, master_key=key)
        self.assertEqual((mp / "a").read_text(), "data")
        store.lock(c)

    def test_key_backup_rescues_damaged_conf(self) -> None:
        c, _ = self._make()
        mp = store.unlock(c, password=PW)
        (mp / "a").write_text("data")
        store.lock(c)
        c.conf.chmod(0o600)
        c.conf.write_text("{ broken")
        mp = store.unlock(c, password=PW)
        self.assertEqual((mp / "a").read_text(), "data")
        store.lock(c)
        self.assertTrue(store._conf_ok(c.conf))  # put back from the backup

    def test_change_password_verified(self) -> None:
        c, key = self._make()
        store.change_password(c, PW2, old_password=PW)
        with self.assertRaises(GocryptError):
            store.unlock(c, password=PW)
        mp = store.unlock(c, password=PW2)
        store.lock(c)
        self.assertEqual(store.recovery_key(c, PW2), gocrypt.format_master_key(key))
        self.assertEqual(c.key_backup.read_bytes(), c.conf.read_bytes())
        self.assertFalse((c.cipherdir / "gocryptfs.conf.bak").exists())
        del mp

    def test_change_password_wrong_old_changes_nothing(self) -> None:
        c, _ = self._make()
        before = c.conf.read_bytes()
        with self.assertRaises(GocryptError):
            store.change_password(c, PW2, old_password="wrong one")
        self.assertEqual(c.conf.read_bytes(), before)

    def test_reset_password_with_recovery_key(self) -> None:
        c, key = self._make()
        store.change_password(c, PW2, master_key=gocrypt.format_master_key(key))
        store.unlock(c, password=PW2)
        store.lock(c)
        self.assertFalse((c.cipherdir / "gocryptfs.conf.bak").exists())
        ok, _report = store.check_integrity(c, PW2)
        self.assertTrue(ok)

    def test_failed_verification_rolls_back(self) -> None:
        c, _ = self._make()
        before = c.conf.read_bytes()
        orig = gocrypt.dump_master_key
        calls = {"n": 0}

        def fake(conf, pw):
            calls["n"] += 1
            return orig(conf, pw) if calls["n"] == 1 else "0" * 64
        gocrypt.dump_master_key = fake
        try:
            with self.assertRaises(CapsuleError):
                store.change_password(c, PW2, old_password=PW)
        finally:
            gocrypt.dump_master_key = orig
        self.assertEqual(c.conf.read_bytes(), before)
        store.unlock(c, password=PW)
        store.lock(c)

    def test_integrity_check_finds_damage(self) -> None:
        c, _ = self._make()
        mp = store.unlock(c, password=PW)
        (mp / "f").write_bytes(os.urandom(10000))
        store.lock(c)
        ok, _ = store.check_integrity(c, PW)
        self.assertTrue(ok)
        victim = next(p for p in c.cipherdir.iterdir() if p.name not in ("gocryptfs.conf", "gocryptfs.diriv"))
        data = bytearray(victim.read_bytes())
        data[100] ^= 0xFF
        victim.write_bytes(bytes(data))
        ok, _ = store.check_integrity(c, PW)
        self.assertFalse(ok)

    def test_trash_requires_locked_and_restores(self) -> None:
        c, _ = self._make()
        mp = store.unlock(c, password=PW)
        (mp / "keep").write_text("1")
        with self.assertRaises(CapsuleError):
            store.trash(c)
        store.lock(c)
        t = store.trash(c)
        self.assertEqual(store.list_capsules(), [])
        self.assertEqual([x.name for x in store.list_trash()], ["Private"])
        r = store.restore(t)
        mp = store.unlock(r, password=PW)
        self.assertEqual((mp / "keep").read_text(), "1")
        store.lock(r)

    def test_purge_only_inside_trash(self) -> None:
        c, _ = self._make()
        fake = store.Trashed(id=c.id, name=c.name, path=c.root, trashed_at=0)
        with self.assertRaises(CapsuleError):
            store.purge(fake)
        self.assertTrue(c.root.exists())
        outside = store.Trashed(id="x", name="x", path=self.tmp, trashed_at=0)
        with self.assertRaises(CapsuleError):
            store.purge(outside)
        t = store.trash(c)
        store.purge(t)
        self.assertEqual(store.list_trash(), [])

    def test_purge_refuses_capsule_opened_from_trash(self) -> None:
        c, _ = self._make()
        t = store.trash(c)
        mnt = self.tmp / "by-hand"
        mnt.mkdir()
        gocrypt.mount(t.path / "vault", mnt, password=PW)
        try:
            with self.assertRaises(CapsuleError):
                store.purge(t)
            self.assertTrue((t.path / "vault" / "gocryptfs.conf").exists())
        finally:
            gocrypt.unmount(mnt)

    def test_purge_refuses_symlink_in_trash(self) -> None:
        c, _ = self._make()
        tdir = paths.ensure_private_dir(paths.trash_dir())
        link = tdir / "evil-1"
        link.symlink_to(c.root)
        with self.assertRaises(CapsuleError):
            store.purge(store.Trashed(id="e", name="e", path=link, trashed_at=0))
        self.assertTrue(c.root.exists())

    def test_linked_capsule_forgotten_not_deleted(self) -> None:
        usb = self.tmp / "usb"
        usb.mkdir()
        c, _ = self._make("Travel", parent=usb)
        self.assertTrue(c.linked)
        self.assertTrue((usb / "Travel" / "vault").is_dir())
        self.assertIn("Travel", [x.name for x in store.list_capsules()])
        # Unplugged: still listed, marked unavailable.
        moved = self.tmp / "away"
        (usb / "Travel").rename(moved)
        lst = store.list_capsules()
        self.assertFalse(lst[0].available)
        moved.rename(usb / "Travel")
        store.trash(store.get(c.id))
        self.assertEqual(store.list_capsules(), [])
        self.assertTrue((usb / "Travel" / "vault" / "gocryptfs.conf").exists())
        # And it can be linked again.
        again = store.link_folder(usb / "Travel")
        self.assertEqual(again.id, c.id)
        with self.assertRaises(CapsuleError):
            store.link_folder(usb / "Travel")

    def test_link_bare_gocryptfs_folder(self) -> None:
        bare = self.tmp / "old-vault"
        bare.mkdir()
        gocrypt.init(bare, PW)
        c = store.link_folder(bare)
        self.assertTrue(c.bare)
        mp = store.unlock(store.get(c.id), password=PW)
        (mp / "x").write_text("y")
        store.lock(store.get(c.id))
        store.rename(store.get(c.id), "Old vault")
        self.assertEqual(store.get(c.id).name, "Old vault")

    def test_export_import_roundtrip(self) -> None:
        c, _ = self._make("Docs")
        mp = store.unlock(c, password=PW)
        (mp / "report.txt").write_text("q3")
        with self.assertRaises(CapsuleError):
            store.export_backup(c, self.tmp / "b")
        store.lock(c)
        out = store.export_backup(c, self.tmp / "b")
        self.assertTrue(out.name.endswith(".capsule.tar"))
        with self.assertRaises(CapsuleError):
            store.export_backup(c, out)  # never overwrite
        imported = store.import_backup(out)
        self.assertNotEqual(imported.id, c.id)  # id clash → new id
        mp = store.unlock(imported, password=PW)
        self.assertEqual((mp / "report.txt").read_text(), "q3")
        store.lock(imported)
        self.assertFalse([p for p in paths.capsules_dir().iterdir() if p.name.startswith(".")])

    def test_import_rejects_evil_archive(self) -> None:
        evil = self.tmp / "evil.capsule.tar"
        with tarfile.open(evil, "w") as tar:
            data = self.tmp / "payload"
            data.write_text("x")
            tar.add(data, arcname="top/capsule.json")
            tar.add(data, arcname="top/vault/gocryptfs.conf")
            tar.add(data, arcname="../escape")
        with self.assertRaises(CapsuleError):
            store.import_backup(evil)
        self.assertFalse((self.tmp / "data" / "maze-capsule" / "escape").exists())

    def test_crash_survival_listing_without_metadata(self) -> None:
        c, _ = self._make("Lost meta")
        (c.root / "capsule.json").unlink()
        self.assertEqual(store.list_capsules()[0].name, "Lost meta")  # from .bak?
        (c.root / "capsule.json.bak").unlink(missing_ok=True)
        lst = store.list_capsules()
        self.assertEqual(len(lst), 1)  # still listed, by folder name

    def test_mount_survives_new_process_view(self) -> None:
        c, _ = self._make()
        mp = store.unlock(c, password=PW)
        again = store.get(c.id)
        self.assertEqual(again.mountpoint, mp)
        self.assertEqual(store.unlock(again, password="ignored because mounted"), mp)
        self.assertEqual(store.lock_all(), [])

    def test_busy_lock_refuses_then_lazy(self) -> None:
        c, _ = self._make()
        mp = store.unlock(c, password=PW)
        f = open(mp / "open.txt", "w")
        try:
            proc = subprocess.Popen(["sleep", "30"], cwd=mp)
            try:
                with self.assertRaises(CapsuleError) as cm:
                    store.lock(c)
                self.assertEqual(cm.exception.reason, "busy")
                self.assertTrue(c.unlocked)
            finally:
                proc.kill()
                proc.wait()
        finally:
            f.close()
        store.lock(c)

    def test_read_only_unlock(self) -> None:
        c, _ = self._make()
        mp = store.unlock(c, password=PW, read_only=True)
        self.assertTrue(store.get(c.id).read_only)
        with self.assertRaises(OSError):
            (mp / "x").write_text("no")
        store.lock(c)


@needs_fuse
class TransferTests(Base):
    def test_copy_never_overwrites_and_keeps_originals(self) -> None:
        c, _ = store.create("T", PW)
        mp = store.unlock(c, password=PW)
        src = self.tmp / "src"
        (src / "sub").mkdir(parents=True)
        (src / "a.txt").write_text("one")
        (src / "sub" / "b.bin").write_bytes(os.urandom(3 * 1024 * 1024 + 7))
        (src / "link").symlink_to("a.txt")
        (mp / "a.txt").write_text("existing")
        r1 = transfer.copy_into([src / "a.txt", src / "sub", src / "link"], mp)
        self.assertEqual(r1.errors, [])
        self.assertEqual((mp / "a.txt").read_text(), "existing")
        self.assertEqual((mp / "a (2).txt").read_text(), "one")
        self.assertEqual((mp / "sub" / "b.bin").read_bytes(), (src / "sub" / "b.bin").read_bytes())
        self.assertTrue((mp / "link").is_symlink())
        transfer.copy_into([src / "sub"], mp)
        self.assertTrue((mp / "sub (2)" / "b.bin").exists())
        self.assertTrue((src / "a.txt").exists())  # originals untouched
        self.assertFalse(list(mp.rglob(".*part-*")))
        store.lock(c)

    def test_cancel_leaves_no_partial(self) -> None:
        c, _ = store.create("T", PW)
        mp = store.unlock(c, password=PW)
        big = self.tmp / "big"
        big.write_bytes(os.urandom(4 * 1024 * 1024))
        seen = {"n": 0}

        def cancelled() -> bool:
            seen["n"] += 1
            return seen["n"] > 2
        with self.assertRaises(transfer.Cancelled):
            transfer.copy_into([big], mp, cancelled=cancelled)
        self.assertEqual(list(mp.iterdir()), [])
        self.assertTrue(big.exists())
        store.lock(c)

    def test_refuses_copy_into_itself(self) -> None:
        d = self.tmp / "d"
        d.mkdir()
        r = transfer.copy_into([d], d)
        self.assertTrue(r.errors)


class SandboxTests(unittest.TestCase):
    def test_argv_shape(self) -> None:
        argv = sandbox.bwrap_argv(Path("/run/user/1/maze-capsule/X"), "X")
        self.assertIn("--unshare-all", argv)
        self.assertNotIn("--share-net", argv)
        i = argv.index("--bind")
        self.assertEqual(argv[i + 1:i + 3], ["/run/user/1/maze-capsule/X", sandbox.HOME])
        self.assertIn("--share-net", sandbox.bwrap_argv(Path("/x"), "X", network=True))

    @unittest.skipUnless(sandbox.available(), "bwrap missing")
    def test_sandbox_sees_only_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            Path(d, "inside.txt").write_text("x")
            argv = sandbox.bwrap_argv(Path(d), "T")[:-4] + ["/usr/bin/bash", "-c",
                                                            f"ls {sandbox.HOME}; ls /home; test -e {Path.home()} && echo HOME_VISIBLE"]
            r = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            if r.returncode != 0 and "setting up uid map" in r.stderr:
                self.skipTest("user namespaces unavailable")
            self.assertIn("inside.txt", r.stdout)
            self.assertNotIn("HOME_VISIBLE", r.stdout)


class SettingsTests(Base):
    def test_defaults_and_validation(self) -> None:
        self.assertEqual(settings.load()["language"], "en")
        settings.save(language="tr")
        self.assertEqual(settings.load()["language"], "tr")
        settings.save(language="xx", idle_minutes="5")
        s = settings.load()
        self.assertEqual(s["language"], "en")
        self.assertEqual(s["idle_minutes"], 0)


if __name__ == "__main__":
    unittest.main()

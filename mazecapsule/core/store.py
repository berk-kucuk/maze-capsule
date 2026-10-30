"""Capsules: create, list, unlock, lock, rename, re-key, trash, back up.

A capsule is one self-contained folder:

    <capsule>/capsule.json            name, id, creation date (atomic, with .bak)
    <capsule>/vault/                  the gocryptfs cipher directory — the data
    <capsule>/key-backup/gocryptfs.conf  a second copy of the password-wrapped key
    <capsule>/README.txt              how to open it without Maze Capsule

Copy that folder anywhere — another disk, another Maze or any Linux with
gocryptfs — and it opens there. Nothing about a capsule lives anywhere else,
except an entry in linked.json for capsules the user keeps outside the default
folder, and that entry is only a pointer.

Data-safety rules this module never breaks:
  1. User data is never deleted by anything but `purge()`, which only works on
     a capsule already in Maze Capsule's trash, not mounted, after the GUI has
     made the user type its name.
  2. Deleting a capsule moves it to the trash (one rename on the same disk).
     Removing a linked capsule only forgets the pointer; its folder stays.
  3. A capsule is created in a hidden staging folder and renamed into place
     only when complete. A failed create removes only that staging folder, and
     only after checking it holds nothing but the files the create just made.
  4. Password changes are verified: the new password must unwrap the same
     master key, or the previous gocryptfs.conf is put back.
  5. A capsule is never moved, trashed or exported while it is unlocked.
  6. Every metadata write is atomic (see atomic.py).
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import secrets
import shutil
import tarfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator

from mazecapsule.core import atomic, gocrypt, mounts, paths
from mazecapsule.core.gocrypt import GocryptError

FORMAT = 1
META = "capsule.json"
VAULT = "vault"
KEY_BACKUP_DIR = "key-backup"
CONF = "gocryptfs.conf"
README = "README.txt"
LINKED = "linked.json"
NAME_MAX = 64

README_TEXT = """\
This folder is a Maze Capsule: an encrypted gocryptfs folder.
Everything inside vault/ is encrypted, including the file names.

Open it without Maze Capsule, on any Linux with gocryptfs installed:
    mkdir ~/capsule
    gocryptfs vault ~/capsule

Lock it again:
    fusermount3 -u ~/capsule

Forgot the password? Use the recovery key you wrote down:
    gocryptfs -masterkey=stdin vault ~/capsule

If vault/gocryptfs.conf was damaged, the copy in key-backup/ works too:
    gocryptfs -config key-backup/gocryptfs.conf vault ~/capsule

Never edit, rename or delete files inside vault/ by hand: each one is part of
your encrypted data. To move or back up a capsule, copy this whole folder.
"""


class CapsuleError(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass
class Capsule:
    id: str
    name: str
    root: Path
    cipherdir: Path
    created: float
    recovery_confirmed: bool = False
    linked: bool = False       # kept outside capsules_dir()
    available: bool = True     # its folder is there (a USB disk may be unplugged)
    bare: bool = False         # a plain gocryptfs folder with no capsule.json

    @property
    def conf(self) -> Path:
        return self.cipherdir / CONF

    @property
    def key_backup(self) -> Path | None:
        return None if self.bare else self.root / KEY_BACKUP_DIR / CONF

    def mount(self) -> mounts.Mount | None:
        return mounts.mount_of(self.cipherdir) if self.available else None

    @property
    def mountpoint(self) -> Path | None:
        m = self.mount()
        return Path(m.target) if m else None

    @property
    def unlocked(self) -> bool:
        return self.mount() is not None

    @property
    def read_only(self) -> bool:
        m = self.mount()
        return bool(m and ("ro" in m.options.split(",")))


@dataclass
class Trashed:
    id: str
    name: str
    path: Path
    trashed_at: float


# ── helpers ──────────────────────────────────────────────────────────────────
def clean_name(name: str) -> str:
    name = " ".join((name or "").split())
    if not name:
        raise CapsuleError("name_empty")
    if len(name) > NAME_MAX:
        raise CapsuleError("name_long")
    if any(ord(c) < 32 or c in "/\\" for c in name) or name in (".", ".."):
        raise CapsuleError("name_chars")
    return name


def _folder_name(name: str) -> str:
    """A capsule name as a safe single path component."""
    safe = re.sub(r"[^\w .,()\-+@]", "_", name, flags=re.UNICODE).strip(" .")
    return safe or "Capsule"


def _unique(parent: Path, base: str) -> Path:
    cand = parent / base
    n = 2
    while cand.exists() or cand.is_symlink():
        cand = parent / f"{base} ({n})"
        n += 1
    return cand


def _new_id() -> str:
    return secrets.token_hex(8)


def _meta(path: Path) -> dict | None:
    data = atomic.read_json(path / META)
    if isinstance(data, dict) and isinstance(data.get("id"), str) and isinstance(data.get("name"), str):
        return data
    return None


def _is_dir(p: Path) -> bool:
    try:
        return p.is_dir()
    except OSError:
        return False


@contextlib.contextmanager
def _op_lock(capsule_id: str) -> Iterator[None]:
    """One operation per capsule at a time, across every Maze Capsule process."""
    lock_dir = paths.ensure_private_dir(paths.runtime_dir() / ".locks")
    fd = os.open(lock_dir / f"{capsule_id}.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CapsuleError("in_progress") from None
        yield
    finally:
        os.close(fd)


def _require_locked(c: Capsule) -> None:
    if c.unlocked:
        raise CapsuleError("unlocked")


def _require_available(c: Capsule) -> None:
    if not c.available or not _is_dir(c.cipherdir):
        raise CapsuleError("unavailable", str(c.root))


# ── linked capsules ──────────────────────────────────────────────────────────
def _linked_path() -> Path:
    return paths.config_dir() / LINKED


def _load_linked() -> list[dict]:
    data = atomic.read_json(_linked_path())
    if not isinstance(data, list):
        return []
    return [e for e in data if isinstance(e, dict) and isinstance(e.get("path"), str)
            and isinstance(e.get("id"), str)]


def _save_linked(entries: list[dict]) -> None:
    paths.ensure_private_dir(paths.config_dir())
    atomic.write_json(_linked_path(), entries)


def _from_folder(folder: Path, linked: bool, entry: dict | None = None) -> Capsule:
    meta = _meta(folder)
    if meta is not None:
        return Capsule(id=meta["id"], name=meta["name"], root=folder,
                       cipherdir=folder / VAULT, created=float(meta.get("created", 0)),
                       recovery_confirmed=bool(meta.get("recovery_confirmed")), linked=linked)
    if (folder / VAULT / CONF).is_file():
        # capsule.json and its .bak are both unreadable: still a capsule.
        return Capsule(id=(entry or {}).get("id") or folder.name,
                       name=(entry or {}).get("name") or folder.name, root=folder,
                       cipherdir=folder / VAULT, created=_mtime(folder / VAULT),
                       recovery_confirmed=True, linked=linked)
    # A bare gocryptfs folder the user linked.
    return Capsule(id=(entry or {}).get("id") or _new_id(),
                   name=(entry or {}).get("name") or folder.name, root=folder, cipherdir=folder,
                   created=float((entry or {}).get("created", 0)) or _mtime(folder),
                   recovery_confirmed=True, linked=linked, bare=True)


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


# ── listing ──────────────────────────────────────────────────────────────────
def list_capsules() -> list[Capsule]:
    out: list[Capsule] = []
    base = paths.capsules_dir()
    try:
        entries = sorted(base.iterdir())
    except OSError:
        entries = []
    for folder in entries:
        if folder.name.startswith(".") or not _is_dir(folder) or folder.is_symlink():
            continue
        if _meta(folder) is None and not (folder / VAULT / CONF).is_file():
            continue
        out.append(_from_folder(folder, linked=False))

    for e in _load_linked():
        folder = Path(e["path"])
        markers = (folder / META, folder / (META + ".bak"), folder / VAULT / CONF, folder / CONF)
        if _is_dir(folder) and any(m.exists() for m in markers):
            c = _from_folder(folder, linked=True, entry=e)
            if c.bare:
                c.id = e["id"]
        else:
            # Unplugged disk or moved folder. Keep showing it; never drop it.
            bare = bool(e.get("bare"))
            c = Capsule(id=e["id"], name=e.get("name") or folder.name, root=folder,
                        cipherdir=folder if bare else folder / VAULT,
                        created=float(e.get("created", 0)), recovery_confirmed=True,
                        linked=True, available=False, bare=bare)
        out.append(c)
    out.sort(key=lambda c: (c.created, c.name.lower()))
    return out


def get(capsule_id: str) -> Capsule:
    for c in list_capsules():
        if c.id == capsule_id:
            return c
    raise CapsuleError("not_found", capsule_id)


# ── create ───────────────────────────────────────────────────────────────────
_STAGING_OWN = {META, META + ".bak", VAULT, KEY_BACKUP_DIR, README}


def _remove_fresh_staging(staging: Path) -> None:
    """Remove a staging folder from a create that failed — if, and only if, it
    holds nothing but what create() itself writes. Otherwise leave it."""
    try:
        names = {p.name for p in staging.iterdir()}
        if not names <= _STAGING_OWN:
            return
        vault = staging / VAULT
        if vault.exists():
            inside = {p.name for p in vault.iterdir()}
            if not inside <= {CONF, "gocryptfs.diriv"}:
                return
        shutil.rmtree(staging)
    except OSError:
        pass


def create(name: str, password: str, parent: Path | None = None) -> tuple[Capsule, str]:
    """Make a new, empty capsule. Returns it and its recovery key (hex).

    parent: a folder of the user's choosing (USB disk, synced folder...). The
    capsule then lives in <parent>/<name>/ and is linked; by default it lives
    in ~/.local/share/maze-capsule/capsules/<id>/.
    """
    name = clean_name(name)
    gocrypt.check_secret(password)
    if not gocrypt.available():
        raise CapsuleError("no_gocryptfs")
    cid = _new_id()
    if parent is None:
        home = paths.ensure_private_dir(paths.capsules_dir())
        final = home / cid
    else:
        parent = Path(parent).expanduser()
        if not _is_dir(parent):
            raise CapsuleError("no_folder", str(parent))
        if not os.access(parent, os.W_OK):
            raise CapsuleError("not_writable", str(parent))
        final = _unique(parent, _folder_name(name))
        home = parent

    staging = home / f".creating-{cid}"
    staging.mkdir(mode=0o700)
    try:
        vault = staging / VAULT
        vault.mkdir(mode=0o700)
        key = gocrypt.init(vault, password)
        kb = staging / KEY_BACKUP_DIR
        kb.mkdir(mode=0o700)
        atomic.write_bytes(kb / CONF, (vault / CONF).read_bytes(), mode=0o400)
        atomic.write_bytes(staging / README, README_TEXT.encode(), mode=0o644)
        meta = {"format": FORMAT, "id": cid, "name": name, "created": time.time(),
                "recovery_confirmed": False}
        atomic.write_json(staging / META, meta)
        # A .bak from the start, so even a capsule.json destroyed before its
        # first update still has its name and id.
        atomic.write_json(staging / META, meta)
        if final.exists():
            raise CapsuleError("exists", str(final))
        os.rename(staging, final)
        atomic.fsync_dir(home)
    except BaseException:
        _remove_fresh_staging(staging)
        raise

    if parent is not None:
        entries = _load_linked()
        entries.append({"id": cid, "path": str(final), "name": name, "created": time.time()})
        _save_linked(entries)
    return _from_folder(final, linked=parent is not None), key


def _write_meta(c: Capsule, **changes) -> None:
    if c.bare:
        entries = _load_linked()
        for e in entries:
            if e["id"] == c.id:
                e.update({k: v for k, v in changes.items() if k == "name"})
        _save_linked(entries)
        return
    meta = _meta(c.root) or {"format": FORMAT, "id": c.id, "name": c.name, "created": c.created}
    meta.update(changes)
    atomic.write_json(c.root / META, meta)
    if c.linked:
        entries = _load_linked()
        for e in entries:
            if e["id"] == c.id and "name" in changes:
                e["name"] = changes["name"]
        _save_linked(entries)


def rename(c: Capsule, new_name: str) -> None:
    _require_available(c)
    with _op_lock(c.id):
        _write_meta(c, name=clean_name(new_name))


def confirm_recovery(c: Capsule) -> None:
    with _op_lock(c.id):
        _write_meta(c, recovery_confirmed=True)


# ── unlock / lock ────────────────────────────────────────────────────────────
def _mountpoint_for(c: Capsule) -> Path:
    base = paths.ensure_private_dir(paths.runtime_dir())
    want = _folder_name(c.name)
    cand, n = base / want, 2
    while True:
        if not cand.exists():
            cand.mkdir(mode=0o700)
            return cand
        # Reuse a leftover empty folder from an earlier unlock, nothing else.
        if _is_dir(cand) and not mounts.is_mountpoint(cand) and not any(cand.iterdir()):
            return cand
        cand, n = base / f"{want} ({n})", n + 1


def _rmdir_mountpoint(mp: Path) -> None:
    """Remove an empty mount point we made. rmdir cannot remove anything else."""
    try:
        if mp.resolve().parent == paths.runtime_dir().resolve() and not mounts.is_mountpoint(mp):
            mp.rmdir()
    except OSError:
        pass


def unlock(c: Capsule, *, password: str | None = None, master_key: str | None = None,
           read_only: bool = False, idle_minutes: int = 0) -> Path:
    _require_available(c)
    with _op_lock(c.id):
        m = c.mount()
        if m is not None:
            return Path(m.target)
        # The gocryptfs.conf in the vault is missing or damaged: the key backup
        # unwraps the same master key with the same password. (A recovery-key
        # unlock needs no conf at all.)
        kb = c.key_backup
        use_backup = (master_key is None and not _conf_ok(c.conf)
                      and kb is not None and _conf_ok(kb))
        mp = _mountpoint_for(c)
        try:
            gocrypt.mount(c.cipherdir, mp, password=password, master_key=master_key,
                          idle_minutes=idle_minutes, read_only=read_only,
                          config=kb if use_backup else None)
            if use_backup and not read_only:
                _restore_conf_from_backup(c)
        except BaseException:
            _rmdir_mountpoint(mp)
            raise
        if password is not None:
            _refresh_key_backup(c)
        return mp


def _restore_conf_from_backup(c: Capsule) -> None:
    """Put the backup conf back only where the vault has none or a broken one."""
    kb = c.key_backup
    if kb is None:
        return
    if _conf_ok(c.conf):
        return  # the vault's own conf parses; leave it alone
    with contextlib.suppress(OSError):
        if c.conf.exists():
            c.conf.chmod(0o600)
        atomic.write_bytes(c.conf, kb.read_bytes(), mode=0o400)


def _refresh_key_backup(c: Capsule) -> None:
    """Keep key-backup/ equal to the vault's conf (after a password unlock, the
    vault's conf is known good)."""
    kb = c.key_backup
    if kb is None:
        return
    try:
        current = c.conf.read_bytes()
        if kb.is_file() and kb.read_bytes() == current:
            return
        paths.ensure_private_dir(kb.parent)
        if kb.exists():
            kb.chmod(0o600)
        atomic.write_bytes(kb, current, mode=0o400)
    except OSError:
        pass


def lock(c: Capsule, lazy: bool = False) -> None:
    with _op_lock(c.id):
        m = c.mount()
        if m is None:
            return
        try:
            gocrypt.unmount(Path(m.target), lazy=lazy)
        except GocryptError as e:
            raise CapsuleError(e.reason, e.detail) from e
        _rmdir_mountpoint(Path(m.target))


def lock_all(lazy: bool = False) -> list[tuple[Capsule, CapsuleError]]:
    failed = []
    for c in list_capsules():
        if c.unlocked:
            try:
                lock(c, lazy=lazy)
            except CapsuleError as e:
                failed.append((c, e))
    return failed


# ── keys ─────────────────────────────────────────────────────────────────────
def _conf_ok(conf: Path) -> bool:
    try:
        data = json.loads(conf.read_bytes())
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and "EncryptedKey" in data


def _readable_conf(c: Capsule) -> Path:
    if _conf_ok(c.conf):
        return c.conf
    kb = c.key_backup
    if kb is not None and _conf_ok(kb):
        return kb
    raise CapsuleError("config")


def recovery_key(c: Capsule, password: str) -> str:
    """The recovery key, re-derived with the password (it is never stored)."""
    _require_available(c)
    return gocrypt.format_master_key(gocrypt.dump_master_key(_readable_conf(c), password))


def verify_password(c: Capsule, password: str) -> None:
    _require_available(c)
    gocrypt.dump_master_key(_readable_conf(c), password)


def change_password(c: Capsule, new_password: str, *, old_password: str | None = None,
                    master_key: str | None = None) -> None:
    _require_available(c)
    gocrypt.check_secret(new_password)
    with _op_lock(c.id):
        if master_key is not None:
            key = gocrypt.normalize_master_key(master_key)
        else:
            key = gocrypt.dump_master_key(_readable_conf(c), old_password or "")
        try:
            before = c.conf.read_bytes()
        except OSError:
            before = None
        stray = c.cipherdir / (CONF + ".bak")
        had_stray = stray.exists()
        try:
            if before is None:
                # No conf in the vault: re-key from the backup copy instead.
                kb = c.key_backup
                if kb is None or not kb.is_file():
                    raise CapsuleError("config")
                atomic.write_bytes(c.conf, kb.read_bytes(), mode=0o400)
            gocrypt.change_password(c.cipherdir, new_password, old_password=old_password,
                                    master_key=key if master_key is not None else None)
            if gocrypt.dump_master_key(c.conf, new_password) != key:
                raise CapsuleError("verify_failed")
        except BaseException:
            if before is not None:
                with contextlib.suppress(OSError):
                    if c.conf.exists():
                        c.conf.chmod(0o600)
                    atomic.write_bytes(c.conf, before, mode=0o400)
            raise
        # gocryptfs leaves the previous conf as gocryptfs.conf.bak inside the
        # vault. It wraps the key under the OLD password — keeping it would let
        # the old password keep working — and fsck reports it as a corrupt
        # entry. It is key material, not file data; the recovery key and the
        # new conf (verified above) open everything it did.
        if not had_stray and stray.is_file():
            with contextlib.suppress(OSError):
                stray.unlink()
        kb = c.key_backup
        if kb is not None:
            with contextlib.suppress(OSError):
                paths.ensure_private_dir(kb.parent)
                if kb.exists():
                    kb.chmod(0o600)
                atomic.write_bytes(kb, c.conf.read_bytes(), mode=0o400)


def check_integrity(c: Capsule, password: str) -> tuple[bool, str]:
    _require_available(c)
    try:
        return gocrypt.fsck(c.cipherdir, password)
    except GocryptError as e:
        if e.reason == "config":
            raise CapsuleError("config", e.detail) from e
        raise


# ── trash ────────────────────────────────────────────────────────────────────
def trash(c: Capsule) -> Trashed | None:
    """Delete = move to the trash. A linked capsule is only forgotten."""
    with _op_lock(c.id):
        if c.available:
            _require_locked(c)
        if c.linked:
            _save_linked([e for e in _load_linked() if e["id"] != c.id])
            return None
        tdir = paths.ensure_private_dir(paths.trash_dir())
        stamp = int(time.time())
        dest = _unique(tdir, f"{c.id}-{stamp}")
        os.rename(c.root, dest)
        atomic.fsync_dir(tdir)
        atomic.fsync_dir(c.root.parent)
        return Trashed(id=c.id, name=c.name, path=dest, trashed_at=stamp)


def list_trash() -> list[Trashed]:
    out = []
    try:
        entries = sorted(paths.trash_dir().iterdir())
    except OSError:
        return out
    for p in entries:
        if p.name.startswith(".") or not _is_dir(p):
            continue
        meta = _meta(p)
        m = re.fullmatch(r"(.+)-(\d+)(?: \(\d+\))?", p.name)
        stamp = float(m.group(2)) if m else _mtime(p)
        out.append(Trashed(id=(meta or {}).get("id") or p.name,
                           name=(meta or {}).get("name") or p.name, path=p, trashed_at=stamp))
    out.sort(key=lambda t: -t.trashed_at)
    return out


def restore(t: Trashed) -> Capsule:
    base = paths.ensure_private_dir(paths.capsules_dir())
    existing = {c.id for c in list_capsules()}
    dest = base / t.id
    if dest.exists() or t.id in existing:
        dest = _unique(base, f"{t.id}-restored")
    os.rename(t.path, dest)
    atomic.fsync_dir(base)
    c = _from_folder(dest, linked=False)
    if c.id in existing:
        c.id = dest.name
        with contextlib.suppress(OSError, CapsuleError):
            _write_meta(c, id=c.id)
    return c


def purge(t: Trashed) -> None:
    """The one place user data is really deleted. Only for trashed capsules."""
    tdir = paths.trash_dir().resolve()
    target = t.path.resolve()
    if target.parent != tdir or target == tdir:
        raise CapsuleError("not_in_trash", str(t.path))
    if t.path.is_symlink():
        raise CapsuleError("not_in_trash", str(t.path))
    if mounts.any_mount_under(target):
        raise CapsuleError("unlocked")
    # Opened by hand from the trash (gocryptfs <trash>/.../vault somewhere)?
    root = str(target).rstrip("/") + "/"
    for m in mounts.gocryptfs_mounts():
        if os.path.realpath(m.source).rstrip("/") + "/" == root or \
                os.path.realpath(m.source).startswith(root):
            raise CapsuleError("unlocked")
    if _meta(target) is None and not (target / VAULT).exists():
        raise CapsuleError("not_a_capsule", str(t.path))
    shutil.rmtree(target)
    atomic.fsync_dir(tdir)


# ── linking existing folders ─────────────────────────────────────────────────
def link_folder(folder: Path) -> Capsule:
    """Add a capsule folder (e.g. on a USB disk) or a plain gocryptfs folder."""
    folder = Path(folder).expanduser().resolve()
    if not _is_dir(folder):
        raise CapsuleError("no_folder", str(folder))
    base = paths.capsules_dir().resolve()
    if folder == base or base in folder.parents or paths.data_dir().resolve() in folder.parents:
        raise CapsuleError("already_listed")
    for e in _load_linked():
        if Path(e["path"]).resolve() == folder:
            raise CapsuleError("already_listed")
    meta = _meta(folder)
    if meta is not None or (folder / VAULT / CONF).is_file():
        c = _from_folder(folder, linked=True)
        if any(x.id == c.id for x in list_capsules()):
            raise CapsuleError("already_listed")
        entry = {"id": c.id, "path": str(folder), "name": c.name, "created": c.created}
    elif (folder / CONF).is_file():
        cid = _new_id()
        entry = {"id": cid, "path": str(folder), "name": folder.name,
                 "created": _mtime(folder), "bare": True}
    else:
        raise CapsuleError("not_a_capsule", str(folder))
    entries = _load_linked()
    entries.append(entry)
    _save_linked(entries)
    return _from_folder(folder, linked=True, entry=entry) if not entry.get("bare") else \
        Capsule(id=entry["id"], name=entry["name"], root=folder, cipherdir=folder,
                created=entry["created"], recovery_confirmed=True, linked=True, bare=True)


# ── backups ──────────────────────────────────────────────────────────────────
BACKUP_SUFFIX = ".capsule.tar"


def size_of(c: Capsule) -> int:
    total = 0
    for dirpath, _dirs, files in os.walk(c.cipherdir):
        for f in files:
            with contextlib.suppress(OSError):
                total += os.lstat(os.path.join(dirpath, f)).st_size
    return total


def free_space(c: Capsule) -> int | None:
    try:
        return shutil.disk_usage(c.root).free
    except OSError:
        return None


def export_backup(c: Capsule, dest: Path,
                  progress: Callable[[int, int], None] | None = None) -> Path:
    """Write the whole capsule — still encrypted — into one .capsule.tar.

    The archive is written next to `dest` under a temporary name and renamed
    only once complete and re-read; an existing file is never overwritten.
    """
    _require_available(c)
    if c.bare:
        raise CapsuleError("bare_export")
    dest = Path(dest)
    if not dest.name.endswith(BACKUP_SUFFIX):
        dest = dest.with_name(dest.name + BACKUP_SUFFIX)
    if dest.exists():
        raise CapsuleError("exists", str(dest))
    with _op_lock(c.id):
        _require_locked(c)
        files = []
        for dirpath, dirs, names in os.walk(c.root):
            dirs.sort()
            for n in sorted(names):
                files.append(Path(dirpath) / n)
        total = sum(f.lstat().st_size for f in files)
        tmp = dest.with_name(f".{dest.name}.part-{secrets.token_hex(4)}")
        done = 0
        arc = c.id
        try:
            with open(tmp, "xb") as raw:
                with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
                    tar.add(c.root, arcname=arc, recursive=False)
                    for dirpath, dirs, _names in os.walk(c.root):
                        dirs.sort()
                        for d in dirs:
                            full = Path(dirpath) / d
                            tar.add(full, arcname=f"{arc}/{full.relative_to(c.root)}", recursive=False)
                    for f in files:
                        tar.add(f, arcname=f"{arc}/{f.relative_to(c.root)}", recursive=False)
                        done += f.lstat().st_size
                        if progress:
                            progress(done, total)
                raw.flush()
                os.fsync(raw.fileno())
            # Read it back before calling it a backup.
            with tarfile.open(tmp, mode="r") as tar:
                names = {m.name for m in tar.getmembers()}
            want = {f"{arc}/{f.relative_to(c.root)}" for f in files}
            if not want <= names:
                raise CapsuleError("backup_verify")
            # link() refuses an existing name, so a file that appeared at
            # `dest` meanwhile is never replaced.
            try:
                os.link(tmp, dest)
            except FileExistsError:
                raise CapsuleError("exists", str(dest)) from None
            except OSError:
                if dest.exists():
                    raise CapsuleError("exists", str(dest)) from None
                os.rename(tmp, dest)
            else:
                tmp.unlink()
            atomic.fsync_dir(dest.parent)
        except BaseException:
            with contextlib.suppress(OSError):
                tmp.unlink()
            raise
    return dest


def import_backup(archive: Path) -> Capsule:
    """Add a capsule from a .capsule.tar made by export_backup()."""
    archive = Path(archive)
    base = paths.ensure_private_dir(paths.capsules_dir())
    try:
        tar = tarfile.open(archive, mode="r")
    except (OSError, tarfile.TarError) as e:
        raise CapsuleError("bad_backup", str(e)) from e
    with tar:
        members = tar.getmembers()
        tops = {m.name.split("/", 1)[0] for m in members}
        if len(tops) != 1:
            raise CapsuleError("bad_backup", "more than one top folder")
        top = tops.pop()
        names = {m.name for m in members}
        if f"{top}/{META}" not in names or f"{top}/{VAULT}/{CONF}" not in names:
            raise CapsuleError("bad_backup", "not a capsule backup")
        staging = base / f".importing-{secrets.token_hex(6)}"
        staging.mkdir(mode=0o700)
        try:
            # The "data" filter refuses absolute paths, "..", device files and
            # links that point outside the folder.
            tar.extractall(staging, filter="data")
            folder = staging / top
            meta = _meta(folder)
            if meta is None:
                raise CapsuleError("bad_backup", "capsule.json unreadable")
            existing = {c.id for c in list_capsules()}
            cid = meta["id"]
            if cid in existing or (base / cid).exists() or not re.fullmatch(r"[0-9a-f]{16}", cid):
                cid = _new_id()
                meta["id"] = cid
                atomic.write_json(folder / META, meta)
            final = base / cid
            if final.exists():
                raise CapsuleError("exists", str(final))
            os.rename(folder, final)
            atomic.fsync_dir(base)
        finally:
            # Only our own extraction folder; by now it is empty on success.
            with contextlib.suppress(OSError):
                shutil.rmtree(staging)
    return _from_folder(final, linked=False)


def created_text(c: Capsule) -> str:
    return datetime.fromtimestamp(c.created).strftime("%Y-%m-%d") if c.created else "—"

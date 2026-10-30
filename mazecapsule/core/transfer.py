"""Copying files into an unlocked capsule.

Copy, never move: the originals stay where they were, and the user removes
them once they have seen their files inside the capsule. Nothing that already
exists in the capsule is ever overwritten — a clash gets a " (2)" name.

Each file is written to a hidden ".part" name, fsync'ed and only then renamed
to its real name, so an interrupted copy never leaves a half file that looks
complete. Cancelling removes only the .part file being written.
"""
from __future__ import annotations

import contextlib
import os
import secrets
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

CHUNK = 1024 * 1024


class Cancelled(Exception):
    pass


@dataclass
class CopyReport:
    files: int = 0
    folders: int = 0
    bytes: int = 0
    skipped: list[str] = field(default_factory=list)   # sockets, devices...
    errors: list[tuple[str, str]] = field(default_factory=list)


def _free_name(parent: Path, name: str) -> Path:
    cand = parent / name
    if not (cand.exists() or cand.is_symlink()):
        return cand
    stem, dot, ext = name.partition(".") if not name.startswith(".") else (name, "", "")
    n = 2
    while True:
        cand = parent / (f"{stem} ({n}){dot}{ext}")
        if not (cand.exists() or cand.is_symlink()):
            return cand
        n += 1


def measure(sources: list[Path]) -> tuple[int, int]:
    """(files, bytes) to copy, for the progress bar."""
    files = total = 0
    for src in sources:
        if src.is_symlink() or not src.is_dir():
            files += 1
            with contextlib.suppress(OSError):
                total += src.lstat().st_size
            continue
        for dirpath, _dirs, names in os.walk(src):
            for n in names:
                files += 1
                with contextlib.suppress(OSError):
                    total += os.lstat(os.path.join(dirpath, n)).st_size
    return files, total


def _publish(part: Path, dest: Path) -> None:
    """Give the finished .part file its real name without ever replacing a file.

    link() fails if the name exists, unlike rename(), so a file that appeared
    meanwhile (another program, a second copy) is never overwritten.
    """
    for _ in range(1000):
        final = _free_name(dest.parent, dest.name)
        try:
            os.link(part, final)
        except FileExistsError:
            continue
        except OSError:
            # No hard links on this filesystem: check-then-rename instead.
            if final.exists() or final.is_symlink():
                continue
            os.rename(part, final)
            return
        os.unlink(part)
        return
    raise OSError("no free file name")


def _copy_file(src: Path, dest: Path, report: CopyReport,
               tick: Callable[[int], None], cancelled: Callable[[], bool]) -> None:
    part = dest.with_name(f".{dest.name}.part-{secrets.token_hex(3)}")
    try:
        with open(src, "rb") as fi, open(part, "xb") as fo:
            while True:
                if cancelled():
                    raise Cancelled()
                buf = fi.read(CHUNK)
                if not buf:
                    break
                fo.write(buf)
                tick(len(buf))
            fo.flush()
            os.fsync(fo.fileno())
        st = src.stat()
        with contextlib.suppress(OSError):
            os.chmod(part, stat.S_IMODE(st.st_mode) | 0o600)
            os.utime(part, ns=(st.st_atime_ns, st.st_mtime_ns))
        _publish(part, dest)
        report.files += 1
    except BaseException:
        with contextlib.suppress(OSError):
            part.unlink()
        raise


def copy_into(sources: list[Path], dest_dir: Path,
              progress: Callable[[int, int, str], None] | None = None,
              cancelled: Callable[[], bool] = lambda: False) -> CopyReport:
    """Copy files and folders into dest_dir (normally a capsule's mount point)."""
    dest_dir = Path(dest_dir)
    report = CopyReport()
    _, total = measure(sources)
    done = 0

    def tick(n: int, name: str = "") -> None:
        nonlocal done
        done += n
        if progress:
            progress(done, total, name)

    def one(src: Path, parent: Path) -> None:
        if cancelled():
            raise Cancelled()
        try:
            st = src.lstat()
        except OSError as e:
            report.errors.append((str(src), e.strerror or str(e)))
            return
        try:
            if stat.S_ISLNK(st.st_mode):
                target = os.readlink(src)
                os.symlink(target, _free_name(parent, src.name))
                report.files += 1
            elif stat.S_ISDIR(st.st_mode):
                # Never copy a capsule into itself.
                if dest_dir.resolve() == src.resolve() or src.resolve() in dest_dir.resolve().parents:
                    report.errors.append((str(src), "inside the destination"))
                    return
                sub = _free_name(parent, src.name)
                sub.mkdir()
                report.folders += 1
                for child in sorted(src.iterdir()):
                    one(child, sub)
            elif stat.S_ISREG(st.st_mode):
                if progress:
                    progress(done, total, src.name)
                _copy_file(src, parent / src.name, report, tick, cancelled)
                report.bytes += st.st_size
            else:
                report.skipped.append(str(src))
        except Cancelled:
            raise
        except OSError as e:
            report.errors.append((str(src), e.strerror or str(e)))

    for s in sources:
        one(Path(s), dest_dir)
    return report

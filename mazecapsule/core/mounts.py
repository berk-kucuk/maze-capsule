"""Which capsules are unlocked right now, read from the kernel.

The truth about a mount is /proc/self/mountinfo, never state kept by the app:
gocryptfs runs as its own daemon, so a capsule stays unlocked (and its files
safe) when Maze Capsule crashes or is closed, and is found again on restart.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MOUNTINFO = Path("/proc/self/mountinfo")
FSTYPE = "fuse.gocryptfs"


@dataclass(frozen=True)
class Mount:
    source: str      # the cipher directory gocryptfs was given
    target: str      # the mount point
    options: str


def _unescape(field: str) -> str:
    # mountinfo escapes space, tab, newline and backslash as \ooo octal.
    out, i = [], 0
    while i < len(field):
        octal = field[i + 1:i + 4]
        if field[i] == "\\" and len(octal) == 3 and all(c in "01234567" for c in octal):
            out.append(chr(int(octal, 8)))
            i += 4
        else:
            out.append(field[i])
            i += 1
    return "".join(out)


def parse(text: str) -> list[Mount]:
    mounts = []
    for line in text.splitlines():
        left, sep, right = line.partition(" - ")
        if not sep:
            continue
        lf, rf = left.split(), right.split()
        if len(lf) < 5 or len(rf) < 2 or rf[0] != FSTYPE:
            continue
        mounts.append(Mount(source=_unescape(rf[1]), target=_unescape(lf[4]),
                            options=rf[2] if len(rf) > 2 else ""))
    return mounts


def gocryptfs_mounts() -> list[Mount]:
    try:
        return parse(MOUNTINFO.read_text())
    except OSError:
        return []


def _real(path: str | Path) -> str:
    try:
        return os.path.realpath(path)
    except OSError:
        return str(path)


def mount_of(cipherdir: Path) -> Mount | None:
    """The live mount of this cipher directory, if any."""
    want = _real(cipherdir)
    for m in gocryptfs_mounts():
        if _real(m.source) == want:
            return m
    return None


def is_mountpoint(path: Path) -> bool:
    want = _real(path)
    try:
        text = MOUNTINFO.read_text()
    except OSError:
        return os.path.ismount(path)
    for line in text.splitlines():
        lf = line.split(" - ", 1)[0].split()
        if len(lf) >= 5 and _real(_unescape(lf[4])) == want:
            return True
    return False


def any_mount_under(path: Path) -> bool:
    """True if anything is mounted at or below `path` (checked before deleting)."""
    root = _real(path).rstrip("/") + "/"
    try:
        text = MOUNTINFO.read_text()
    except OSError:
        return True  # cannot tell → answer the safe way
    for line in text.splitlines():
        lf = line.split(" - ", 1)[0].split()
        if len(lf) >= 5:
            target = _real(_unescape(lf[4])).rstrip("/") + "/"
            if target.startswith(root):
                return True
    return False

"""Crash-safe small-file writes.

Every metadata file Maze Capsule writes goes through here: the new content is
written to a temporary file in the same directory, fsync'ed, renamed over the
old one, and the directory is fsync'ed. A power cut at any point leaves either
the old file or the new one — never a truncated mix.

JSON files also keep a `.bak` of the previous version, and `read_json` falls
back to it, so even a file corrupted by something else (a disk error, a manual
edit) does not lose the record.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    fsync_dir(path.parent)


def _backup(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def write_json(path: Path, obj: Any) -> None:
    path = Path(path)
    data = (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode()
    # Keep the current version as .bak — but only if it is valid, so a
    # corrupt file never replaces a good backup.
    if path.exists():
        try:
            current = path.read_bytes()
            json.loads(current)
            write_bytes(_backup(path), current)
        except (OSError, ValueError):
            pass
    write_bytes(path, data)


def read_json(path: Path) -> Any | None:
    """The file's JSON, else its .bak's, else None."""
    path = Path(path)
    for candidate in (path, _backup(path)):
        try:
            return json.loads(candidate.read_bytes())
        except (OSError, ValueError):
            continue
    return None

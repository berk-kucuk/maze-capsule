"""Where Maze Capsule keeps things.

    ~/.local/share/maze-capsule/capsules/<id>/   one capsule (see store.py)
    ~/.local/share/maze-capsule/trash/<id>-<ts>/ capsules the user deleted
    ~/.config/maze-capsule/settings.json         preferences
    ~/.config/maze-capsule/linked.json           capsules kept outside capsules/
    $XDG_RUNTIME_DIR/maze-capsule/<name>/        where an unlocked capsule appears

Mount points live in the runtime directory: it is a per-user tmpfs, so a folder
there can never hold real files that a locked capsule would hide, and it is
gone after logout.
"""
from __future__ import annotations

import os
from pathlib import Path


def _xdg(var: str, fallback: str) -> Path:
    value = os.environ.get(var, "")
    # The spec says relative values must be ignored.
    return Path(value) if value and os.path.isabs(value) else Path.home() / fallback


def data_dir() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / "maze-capsule"


def capsules_dir() -> Path:
    return data_dir() / "capsules"


def trash_dir() -> Path:
    return data_dir() / "trash"


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "maze-capsule"


def runtime_dir() -> Path:
    rt = os.environ.get("XDG_RUNTIME_DIR", "")
    if rt and os.path.isabs(rt) and os.path.isdir(rt):
        return Path(rt) / "maze-capsule"
    # No runtime dir (a bare tty, some containers): a private folder in the
    # data dir. Mount points are only ever created empty, so this is safe too.
    return data_dir() / "mnt"


def ensure_private_dir(path: Path) -> Path:
    """Create `path` (and parents) as 0700 and return it."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        if path.stat().st_mode & 0o077:
            path.chmod(0o700)
    except OSError:
        pass
    return path

"""Qt-free command line: `maze-capsule --list`, `--lock-all`.

`--lock-all` is also what the maze-capsule-autolock user service runs when the
session ends, so no capsule is left mounted after logout.
"""
from __future__ import annotations

import sys

from mazecapsule import __version__

USAGE = """\
Usage: maze-capsule [--lang=en|tr]     open the app
       maze-capsule --list             list capsules and whether they are unlocked
       maze-capsule --lock-all [--lazy]
                                       lock every unlocked capsule; --lazy locks
                                       busy ones as soon as their files close
       maze-capsule --version
"""


def main(argv: list[str]) -> int | None:
    """Returns an exit code, or None when the GUI should start."""
    args = [a for a in argv if not a.startswith("--lang=")]
    if not args:
        return None
    if args[0] in ("-h", "--help"):
        print(USAGE, end="")
        return 0
    if args[0] == "--version":
        print(f"maze-capsule {__version__}")
        return 0

    from mazecapsule.core import store

    if args[0] == "--list":
        for c in store.list_capsules():
            state = ("not connected" if not c.available else
                     f"unlocked at {c.mountpoint}" if c.unlocked else "locked")
            print(f"{c.name}\t{state}\t{c.root}")
        return 0
    if args[0] == "--lock-all":
        failed = store.lock_all(lazy="--lazy" in args[1:])
        for c, e in failed:
            print(f"could not lock {c.name}: {e.reason}", file=sys.stderr)
        return 1 if failed else 0
    print(USAGE, end="", file=sys.stderr)
    return 2

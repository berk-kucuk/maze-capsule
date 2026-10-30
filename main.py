#!/usr/bin/env python3
"""Maze Capsule — encrypted, self-contained spaces for your files."""
import sys

if __name__ == "__main__":
    from mazecapsule.cli import main
    code = main(sys.argv[1:])
    if code is None:
        from mazecapsule.gui.app import run
        code = run()
    sys.exit(code)

"""A shell sealed inside one unlocked capsule.

bubblewrap starts the shell in fresh namespaces (user, pid, ipc, uts, cgroup
and, unless the user allows it, network). It sees the system read-only, a
private /tmp, and exactly one writable folder: the capsule, as its home. Your
real home, other capsules, the session bus and the display are not there.
Anything a program writes ends up encrypted in the capsule, or in a /tmp that
disappears when the shell exits.
"""
from __future__ import annotations

import shutil
from pathlib import Path

HOME = "/home/capsule"

_TERMINALS: list[tuple[str, list[str]]] = [
    ("maze-terminal", ["-e"]),
    ("konsole", ["--separate", "-p", "tabtitle={title}", "-e"]),
    ("kgx", ["--"]),
    ("gnome-terminal", ["--wait", "--"]),
    ("xfce4-terminal", ["--disable-server", "-x"]),
    ("alacritty", ["-e"]),
    ("kitty", ["--"]),
    ("foot", []),
    ("wezterm", ["start", "--"]),
    ("xterm", ["-e"]),
]


def available() -> bool:
    return shutil.which("bwrap") is not None


def find_terminal() -> tuple[str, list[str]] | None:
    for binary, prefix in _TERMINALS:
        path = shutil.which(binary)
        if path:
            return path, prefix
    return None


def bwrap_argv(mountpoint: Path, name: str, network: bool = False) -> list[str]:
    argv = [
        "bwrap",
        "--unshare-all",
        *(["--share-net"] if network else []),
        "--die-with-parent",
        "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/bin", "/sbin",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib", "/lib64",
        "--ro-bind", "/etc", "/etc",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--tmpfs", "/run",
        "--dir", "/home",
        "--bind", str(mountpoint), HOME,
        "--chdir", HOME,
        "--hostname", "capsule",
        "--clearenv",
        "--setenv", "HOME", HOME,
        "--setenv", "PATH", "/usr/local/bin:/usr/bin",
        "--setenv", "TERM", "xterm-256color",
        "--setenv", "LANG", "C.UTF-8",
        "--setenv", "MAZE_CAPSULE", name,
        "--setenv", "PS1", f"[capsule:{_ps1_safe(name)}] \\w \\$ ",
    ]
    if network:
        # /etc/resolv.conf is often a symlink into /run.
        argv += ["--ro-bind-try", "/run/systemd/resolve", "/run/systemd/resolve"]
    return argv + ["/usr/bin/bash", "--norc", "--noprofile", "-i"]


def _ps1_safe(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in " -_.")[:32]


def terminal_argv(mountpoint: Path, name: str, network: bool = False) -> list[str]:
    term = find_terminal()
    if term is None:
        raise RuntimeError("no terminal emulator found")
    binary, prefix = term
    prefix = [p.replace("{title}", f"Capsule · {_ps1_safe(name)}") for p in prefix]
    return [binary, *prefix, *bwrap_argv(mountpoint, name, network)]

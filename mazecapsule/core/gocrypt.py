"""The only module that runs gocryptfs.

Maze Capsule does no cryptography of its own. gocryptfs (AES-256-GCM file
contents, EME-encrypted file names, scrypt-wrapped master key) is mature,
audited, runs without root through FUSE, and its folders open on any Linux
machine with nothing but gocryptfs installed — which is what makes a capsule
independent of this app and of this system.

Rules kept everywhere here:
  * Secrets go in through stdin, never argv or the environment, so they never
    show up in /proc/<pid>/cmdline or environ.
  * stdout/stderr go to temporary files, not pipes. A mount forks a daemon that
    may hold inherited pipes open; with files there is nothing to hang on.
  * The daemon starts in its own session, so closing the app or its terminal
    never kills a mounted capsule mid-write.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

GOCRYPTFS = "gocryptfs"
XRAY = "gocryptfs-xray"
FUSERMOUNT = "fusermount3"

# scrypt cost 2^17: twice gocryptfs' default. Unlocking takes about half a
# second and 128 MiB of memory, which makes guessing passwords that much slower.
SCRYPT_N = 17
MAX_SECRET = 1024

# gocryptfs/internal/exitcodes
_EXIT_REASONS = {
    6: "cipherdir",
    8: "config",
    9: "read_password",
    10: "mountpoint",
    12: "wrong_password",
    19: "fuse",
    22: "empty_password",
    23: "config",
    24: "write_config",
    26: "corrupt",
}


class GocryptError(Exception):
    """reason: a short key the GUI translates; detail: gocryptfs' own words."""

    def __init__(self, reason: str, detail: str = "", code: int | None = None):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail
        self.code = code


def available() -> bool:
    return shutil.which(GOCRYPTFS) is not None and shutil.which(FUSERMOUNT) is not None


def version() -> str:
    try:
        out = subprocess.run([GOCRYPTFS, "-version"], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.match(r"gocryptfs (v[\w.\-]+)", out)
    return m.group(1) if m else ""


def check_secret(secret: str) -> None:
    if not secret:
        raise GocryptError("empty_password")
    if "\n" in secret or "\r" in secret or "\0" in secret:
        raise GocryptError("bad_character")
    if len(secret.encode()) > MAX_SECRET:
        raise GocryptError("too_long")


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    return env


def _run(argv: list[str], stdin: str = "", timeout: float | None = 120) -> tuple[int, str]:
    """Run, feeding `stdin`; returns (exit code, combined output)."""
    with tempfile.TemporaryFile() as out:
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=out, stderr=out,
                                    env=_env(), start_new_session=True, close_fds=True)
        except OSError as e:
            raise GocryptError("missing", f"{argv[0]}: {e.strerror}") from e
        try:
            proc.communicate(stdin.encode(), timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise GocryptError("timeout", " ".join(argv[:2]))
        out.seek(0)
        text = out.read().decode(errors="replace")
    return proc.returncode, text


def _fail(code: int, text: str) -> GocryptError:
    lines = [ln for ln in text.strip().splitlines()
             if ln and not ln.startswith("Reading Password from stdin")
             and not ln.startswith("Reading Masterkey from stdin")]
    return GocryptError(_EXIT_REASONS.get(code, "failed"), "\n".join(lines[-4:]), code)


# ── master key ───────────────────────────────────────────────────────────────
def normalize_master_key(text: str) -> str:
    """64 lowercase hex digits from whatever the user typed (dashes, spaces...)."""
    hexed = re.sub(r"[^0-9a-fA-F]", "", text).lower()
    if len(hexed) != 64:
        raise GocryptError("bad_master_key")
    return hexed


def format_master_key(hexkey: str) -> str:
    """Eight groups of eight, the way gocryptfs prints it."""
    k = normalize_master_key(hexkey)
    return "-".join(k[i:i + 8] for i in range(0, 64, 8))


def dump_master_key(conf: Path, password: str) -> str:
    """The master key, unwrapped from gocryptfs.conf with the password."""
    check_secret(password)
    code, text = _run([XRAY, "-dumpmasterkey", str(conf)], password + "\n", timeout=60)
    if code != 0:
        raise _fail(code, text)
    for line in text.splitlines():
        line = line.strip()
        if re.fullmatch(r"[0-9a-f]{64}", line):
            return line
    raise GocryptError("failed", "no master key in gocryptfs-xray output")


# ── operations ───────────────────────────────────────────────────────────────
def init(cipherdir: Path, password: str) -> str:
    """Create a new encrypted folder; returns its master key (the recovery key).

    gocryptfs itself refuses a non-empty directory, so this can never turn
    existing files into a capsule by accident.
    """
    check_secret(password)
    code, text = _run([GOCRYPTFS, "-init", "-q", "-scryptn", str(SCRYPT_N), str(cipherdir)],
                      password + "\n", timeout=180)
    if code != 0:
        raise _fail(code, text)
    return dump_master_key(cipherdir / "gocryptfs.conf", password)


def mount(cipherdir: Path, mountpoint: Path, *, password: str | None = None,
          master_key: str | None = None, idle_minutes: int = 0,
          read_only: bool = False, config: Path | None = None) -> None:
    """Mount (unlock). gocryptfs refuses a non-empty mount point by itself.

    config: use this gocryptfs.conf instead of the one in the cipher dir (the
    capsule's key backup, when the original is damaged).
    """
    argv = [GOCRYPTFS, "-q"]
    if config is not None:
        argv.append(f"-config={config}")
    if master_key is not None:
        secret = normalize_master_key(master_key)
        argv.append("-masterkey=stdin")
    else:
        secret = password or ""
        check_secret(secret)
    if idle_minutes > 0:
        argv += ["-i", f"{int(idle_minutes)}m"]
    if read_only:
        argv.append("-ro")
    argv += [str(cipherdir), str(mountpoint)]
    code, text = _run(argv, secret + "\n", timeout=90)
    if code != 0:
        raise _fail(code, text)


def unmount(mountpoint: Path, lazy: bool = False) -> None:
    """Lock. Without `lazy`, refuses while a program still has files open."""
    argv = [FUSERMOUNT, "-u"] + (["-z"] if lazy else []) + [str(mountpoint)]
    code, text = _run(argv, timeout=60)
    if code != 0:
        busy = "busy" in text.lower()
        raise GocryptError("busy" if busy else "unmount", text.strip(), code)


def change_password(cipherdir: Path, new_password: str, *, old_password: str | None = None,
                    master_key: str | None = None) -> None:
    """Rewrap the master key under a new password. Files are not touched."""
    check_secret(new_password)
    argv = [GOCRYPTFS, "-passwd", "-q"]
    if master_key is not None:
        argv.append("-masterkey=stdin")
        first = normalize_master_key(master_key)
    else:
        first = old_password or ""
        check_secret(first)
    argv.append(str(cipherdir))
    code, text = _run(argv, f"{first}\n{new_password}\n", timeout=180)
    if code != 0:
        raise _fail(code, text)


def fsck(cipherdir: Path, password: str) -> tuple[bool, str]:
    """Read-only integrity check. Returns (clean, report)."""
    check_secret(password)
    code, text = _run([GOCRYPTFS, "-fsck", "-q", str(cipherdir)], password + "\n", timeout=None)
    if code == 0:
        return True, text
    if code == 26:
        return False, text
    raise _fail(code, text)

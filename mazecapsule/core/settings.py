"""Per-user preferences, in ~/.config/maze-capsule/settings.json."""
from __future__ import annotations

from mazecapsule.core import atomic, paths

DEFAULTS = {
    "language": "en",          # "en" (default) or "tr"
    "idle_minutes": 0,         # auto-lock after inactivity; 0 = off
    "sandbox_network": False,  # sandbox shell gets no network unless allowed
}
LANGUAGES = ("en", "tr")


def _path():
    return paths.config_dir() / "settings.json"


def load() -> dict:
    out = dict(DEFAULTS)
    data = atomic.read_json(_path())
    if isinstance(data, dict):
        for k, v in data.items():
            if k in DEFAULTS and type(v) is type(DEFAULTS[k]):
                out[k] = v
    if out["language"] not in LANGUAGES:
        out["language"] = "en"
    out["idle_minutes"] = max(0, min(out["idle_minutes"], 24 * 60))
    return out


def save(**values) -> None:
    try:
        paths.ensure_private_dir(paths.config_dir())
        atomic.write_json(_path(), {**load(), **values})
    except OSError:
        pass

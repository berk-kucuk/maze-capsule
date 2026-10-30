"""Run slow work (scrypt, mounting, copying) off the UI thread.

Signals are emitted from the pool thread; PyQt delivers them to the callables
on the thread that connected them, i.e. the UI thread.
"""
from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

_live: set["Task"] = set()
_critical: set["Task"] = set()


class _Signals(QObject):
    done = pyqtSignal(object)
    failed = pyqtSignal(object)
    progress = pyqtSignal(object)


class Task(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self.setAutoDelete(False)
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
        except BaseException as e:  # reported to the UI, never swallowed
            self.signals.failed.emit(e)
        else:
            self.signals.done.emit(result)


def run(fn: Callable[..., Any], *args, on_done: Callable[[Any], None] | None = None,
        on_fail: Callable[[BaseException], None] | None = None,
        on_progress: Callable[[Any], None] | None = None,
        with_progress: bool = False, critical: bool = True, **kwargs) -> Task:
    """Start fn(*args, **kwargs) in the pool. With with_progress, fn also gets
    `progress=<callable>` that forwards its argument to on_progress.
    critical=False for read-only work (measuring sizes) that must not keep the
    window from closing."""
    task = Task(fn, *args, **kwargs)
    if with_progress:
        task.kwargs["progress"] = lambda *v: task.signals.progress.emit(v)
    _live.add(task)
    if critical:
        _critical.add(task)

    def finish(cb, value) -> None:
        _live.discard(task)
        _critical.discard(task)
        if cb is not None:
            cb(value)
    task.signals.done.connect(lambda r: finish(on_done, r))
    task.signals.failed.connect(lambda e: finish(on_fail, e))
    if on_progress is not None:
        task.signals.progress.connect(on_progress)
    QThreadPool.globalInstance().start(task)
    return task


def busy() -> bool:
    """True while work that changes something (create, copy, re-key...) runs."""
    return bool(_critical)

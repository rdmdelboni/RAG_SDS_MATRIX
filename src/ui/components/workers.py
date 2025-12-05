"""Threading utilities for background task execution.

Provides signal handlers and thread pool integration for long-running operations
without blocking the UI.
"""

from __future__ import annotations

import traceback
from typing import Callable

from PySide6 import QtCore

from ...utils.logger import get_logger

logger = get_logger(__name__)


class WorkerSignals(QtCore.QObject):
    """Signals emitted by background workers."""

    finished = QtCore.Signal(object)  # Result data
    error = QtCore.Signal(str)  # Error message
    message = QtCore.Signal(str)  # Status messages
    progress = QtCore.Signal(int, str)  # percent, label
    file_result = QtCore.Signal(str, str, str, int)  # filename, chemical, status, row_idx
    data = QtCore.Signal(dict)  # Generic data dict for UI updates


class TaskRunner(QtCore.QRunnable):
    """Generic QRunnable wrapper to execute callables in a thread pool."""

    def __init__(self, fn: Callable, *args, **kwargs) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @QtCore.Slot()
    def run(self) -> None:  # pragma: no cover - Qt thread dispatch
        """Execute the callable and emit appropriate signals."""
        try:
            result = self.fn(*self.args, signals=self.signals, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.error("Worker error: %s", exc)
            logger.debug(traceback.format_exc())
            self.signals.error.emit(str(exc))
            self.signals.finished.emit(None)

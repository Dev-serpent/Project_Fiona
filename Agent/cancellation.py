"""Cancellation primitive for Fiona agent operations."""

from __future__ import annotations

import threading


class CancelledError(RuntimeError):
    """Raised when an operation is cancelled via CancellationToken."""


class CancellationToken:
    """Thread-safe cancellation flag. All methods safe from any thread."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Signal cancellation. May be called from any thread."""
        self._event.set()

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        """Raise CancelledError if cancelled."""
        if self._event.is_set():
            raise CancelledError("Operation was cancelled")

    def reset(self) -> None:
        """Reset the token for reuse."""
        self._event.clear()

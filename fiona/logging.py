"""Structured logging for Fiona.

Produces JSON lines in production, pretty-printed in development.

Usage:
    logger = FionaLogger("browser")
    logger.info("Browser launched", pid=12345, duration_ms=2450)
"""

from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from datetime import datetime, timezone
from typing import TextIO

# ---------------------------------------------------------------------------
# Log level constants
# ---------------------------------------------------------------------------

DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40

_LEVEL_NAMES: dict[int, str] = {
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARNING: "WARNING",
    ERROR: "ERROR",
}

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_DEV_ENV = os.environ.get("FIONA_ENV", "") == "development" or bool(
    os.environ.get("PYTHONDEVMODE")
)
"""True when we should use pretty-print instead of compact JSON."""


def _parse_level(level: str) -> int:
    """Convert a level string to its numeric value (case-insensitive)."""
    normalized = level.upper().strip()
    return {
        "DEBUG": DEBUG,
        "INFO": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
    }.get(normalized, INFO)


def _open_output(output: str) -> TextIO:
    """Return a writable text stream for the given output specifier.

    Built-in values:
      - ``"stdout"`` → ``sys.stdout``
      - ``"stderr"`` → ``sys.stderr``

    Otherwise *output* is treated as a file path (opened for append).
    """
    if output == "stdout":
        return sys.stdout
    if output == "stderr":
        return sys.stderr
    # File-based output – append mode, UTF-8.
    f = open(output, "a", encoding="utf-8")  # noqa: SIM115 — caller owns lifecycle
    return f


# ---------------------------------------------------------------------------
# Logger class
# ---------------------------------------------------------------------------


class FionaLogger:
    """Structured logger that emits JSON lines or pretty-printed records.

    Thread-safe: all public methods acquire an internal reentrant lock.

    Attributes:
        name: Logger name (appears in every record as ``"logger"``).
        level: Minimum numeric severity for records to be emitted.
        output: Stream or path where log lines are written.
    """

    def __init__(
        self,
        name: str,
        level: str = "INFO",
        output: str = "stdout",
    ) -> None:
        """Initialise the logger.

        Args:
            name: Logical name for the logger (e.g. ``"browser"``,
                ``"cad.server"``).
            level: Minimum log level.  One of ``"DEBUG"``, ``"INFO"``,
                ``"WARNING"``, ``"ERROR"``.  Case-insensitive.
            output: Destination.  ``"stdout"``, ``"stderr"``, or a file
                path.  Defaults to ``"stdout"``.
        """
        self.name = name
        self._numeric_level = _parse_level(level)
        self._output_descriptor = output
        self._stream: TextIO | None = None
        self._lock = threading.RLock()

    # -- public API ---------------------------------------------------------

    def debug(self, msg: str, **context: object) -> None:
        """Log a message at DEBUG level.

        Args:
            msg: Human-readable log message.
            **context: Arbitrary key-value pairs attached to the record.
        """
        self._log(DEBUG, msg, context)

    def info(self, msg: str, **context: object) -> None:
        """Log a message at INFO level.

        Args:
            msg: Human-readable log message.
            **context: Arbitrary key-value pairs attached to the record.
        """
        self._log(INFO, msg, context)

    def warning(self, msg: str, **context: object) -> None:
        """Log a message at WARNING level.

        Args:
            msg: Human-readable log message.
            **context: Arbitrary key-value pairs attached to the record.
        """
        self._log(WARNING, msg, context)

    def error(self, msg: str, **context: object) -> None:
        """Log a message at ERROR level.

        Args:
            msg: Human-readable log message.
            **context: Arbitrary key-value pairs attached to the record.
        """
        self._log(ERROR, msg, context)

    # -- internal -----------------------------------------------------------

    def _should_emit(self, level: int) -> bool:
        """Return True when *level* meets the configured threshold."""
        return level >= self._numeric_level

    def _build_record(
        self,
        level: int,
        msg: str,
        context: dict[str, object],
    ) -> dict[str, object]:
        """Assemble the structured log record as a plain dict."""
        record: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": _LEVEL_NAMES.get(level, f"LEVEL_{level}"),
            "logger": self.name,
            "msg": msg,
        }
        record.update(context)
        return record

    def _format_line(self, record: dict[str, object]) -> str:
        """Serialise a record to a single line of text."""
        if _DEV_ENV:
            # Pretty-print for human eyeballs.
            return _pretty_format(record)
        # Production: compact JSON lines.
        return json.dumps(record, default=_json_fallback, ensure_ascii=False) + "\n"

    def _get_stream(self) -> TextIO:
        """Return (and cache) the output stream."""
        if self._stream is None:
            self._stream = _open_output(self._output_descriptor)
        return self._stream

    def _log(self, level: int, msg: str, context: dict[str, object]) -> None:
        """Core emit method — thread-safe."""
        if not self._should_emit(level):
            return

        record = self._build_record(level, msg, context)
        line = self._format_line(record)

        with self._lock:
            stream = self._get_stream()
            stream.write(line)
            stream.flush()

    def __repr__(self) -> str:
        return (
            f"FionaLogger(name={self.name!r}, "
            f"level={_LEVEL_NAMES.get(self._numeric_level, '?')}, "
            f"output={self._output_descriptor!r})"
        )


# ---------------------------------------------------------------------------
# Pretty-print formatter (development mode)
# ---------------------------------------------------------------------------


def _pretty_format(record: dict[str, object]) -> str:
    """Format a log record as a human-readable multi-line string."""
    ts = record.pop("ts", "")
    level = record.pop("level", "?")
    logger_name = record.pop("logger", "")
    msg = record.pop("msg", "")

    lines = [f"[{ts}] {level:<7} {logger_name}  {msg}"]

    # Remaining keys become indented context.
    for key, value in sorted(record.items()):
        if key == "exception":
            lines.append(f"  {key}: {value}")
        else:
            lines.append(f"  {key}: {_short_repr(value)}")

    lines.append("")  # trailing newline
    return "\n".join(lines)


def _short_repr(value: object) -> str:
    """Return a compact repr, truncating if too long."""
    s = repr(value)
    return s if len(s) <= 200 else s[:197] + "..."

# ---------------------------------------------------------------------------
# JSON fallback for non-serialisable types
# ---------------------------------------------------------------------------

def _json_fallback(obj: object) -> str:
    """Fallback serialiser for objects that ``json`` cannot handle natively."""
    return str(obj)


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_loggers: dict[str, FionaLogger] = {}
_loggers_lock = threading.Lock()


def get_logger(name: str, level: str = "INFO", output: str = "stdout") -> FionaLogger:
    """Return a shared ``FionaLogger`` instance for *name*.

    Subsequent calls with the same *name* return the same logger
    (singleton per name).  The first call's *level* and *output*
    arguments are preserved for that logger.

    Args:
        name: Logger name.
        level: Minimum log level (default ``"INFO"``).
        output: Output destination (default ``"stdout"``).

    Returns:
        A ``FionaLogger`` instance.
    """
    with _loggers_lock:
        if name not in _loggers:
            _loggers[name] = FionaLogger(name, level=level, output=output)
        return _loggers[name]

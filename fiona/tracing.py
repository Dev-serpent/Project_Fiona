"""Span-based tracing for performance observability.

Usage:
    tracer = Tracer()
    with tracer.span("browser.navigate", url="https://example.com"):
        result = await navigate(url)
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Generator

from fiona.logging import get_logger

# ---------------------------------------------------------------------------
# Span data type
# ---------------------------------------------------------------------------


@dataclass
class Span:
    """A single unit of tracing work.

    Attributes:
        trace_id: Globally unique identifier shared across all spans
            in a trace.
        span_id: Unique identifier for this span.
        parent_span_id: Span ID of the parent span, or ``None`` for
            root spans.
        operation: Name of the traced operation (e.g.
            ``"browser.navigate"``).
        start_time: Monotonic clock time when the span started
            (``time.monotonic()``).
        end_time: Monotonic clock time when the span ended.  ``None``
            while the span is active.
        status: Span status — ``"ok"`` or ``"error"``.
        attributes: Arbitrary key-value metadata attached to the span.
    """

    trace_id: str
    span_id: str
    parent_span_id: str | None
    operation: str
    start_time: float
    end_time: float | None = None
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float | None:
        """Return the span duration in milliseconds, or ``None`` if
        the span is still open."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000.0


# ---------------------------------------------------------------------------
# Context variable for nesting
# ---------------------------------------------------------------------------

_current_span_id: ContextVar[str | None] = ContextVar(
    "tracing_current_span_id", default=None
)
"""Holds the span_id of the currently active span (per-async-context)."""


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------


class Tracer:
    """Span-based tracer for performance observability.

    Spans are collected in a ``collected_spans`` list and also logged
    via a ``FionaLogger``.  Nesting is supported via
    ``contextvars.ContextVar`` for correct behaviour across asyncio
    tasks.

    Attributes:
        collected_spans: List of all completed ``Span`` instances.  Use
            this for programmatic access (e.g. health endpoints, test
            assertions).
    """

    def __init__(self, logger_name: str = "fiona.tracing") -> None:
        """Initialise a tracer.

        Args:
            logger_name: Name passed to the underlying ``FionaLogger``.
        """
        self._logger = get_logger(logger_name)
        self.collected_spans: list[Span] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @contextmanager
    def span(self, operation: str, **attributes: Any) -> Generator[Span, None, None]:
        """Context manager that creates and records a span.

        The span is started on entry, stopped on exit, and appended to
        ``collected_spans``.  If an exception propagates out of the
        body, the span's status is set to ``"error"`` and the
        exception is re-raised.

        Args:
            operation: Name of the traced operation.
            **attributes: Key-value pairs attached to the span as
                metadata.

        Yields:
            The active ``Span`` instance.

        Example:
            with tracer.span("browser.navigate", url="https://..."):
                result = await navigate(url)
        """
        trace_id = uuid.uuid4().hex[:16]
        span_id = uuid.uuid4().hex[:16]
        parent_span_id = _current_span_id.get()

        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation=operation,
            start_time=time.monotonic(),
            attributes=dict(attributes),
        )

        token = _current_span_id.set(span_id)
        try:
            yield span
        except BaseException as exc:
            span.status = "error"
            span.attributes.setdefault("error", str(exc))
            raise
        finally:
            _current_span_id.reset(token)
            span.end_time = time.monotonic()
            self._emit(span)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(self, span: Span) -> None:
        """Record a completed span: collect it and log it."""
        self.collected_spans.append(span)

        duration = span.duration_ms
        log_context: dict[str, object] = {
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "parent_span_id": span.parent_span_id,
            "operation": span.operation,
            "duration_ms": duration,
            "attributes": span.attributes,
        }

        if span.status == "error":
            self._logger.error("Span finished with error", **log_context)
        else:
            self._logger.info("Span finished", **log_context)

    def clear(self) -> None:
        """Remove all collected spans (useful between test cases)."""
        self.collected_spans.clear()

    def __repr__(self) -> str:
        return f"Tracer(spans_collected={len(self.collected_spans)})"


# ---------------------------------------------------------------------------
# Module-level default tracer
# ---------------------------------------------------------------------------

_default_tracer: Tracer | None = None


def tracer() -> Tracer:
    """Return the module-level default ``Tracer`` instance.

    The tracer is created lazily on first access.  This is the
    recommended way to obtain a tracer for application code that does
    not require a custom instance.

    Returns:
        The shared default ``Tracer``.
    """
    global _default_tracer  # noqa: PLW0603 — intentional module singleton
    if _default_tracer is None:
        _default_tracer = Tracer()
    return _default_tracer

"""Simple metrics collection for instrumentation.

Usage:
    metrics = MetricsRegistry()
    metrics.counter("browser.navigation").inc()
    metrics.histogram("cad.command.duration_ms").observe(42.5)
"""

from __future__ import annotations

import math
import threading
from collections import defaultdict
from typing import Any

# ---------------------------------------------------------------------------
# Metric types
# ---------------------------------------------------------------------------


class Counter:
    """A monotonically increasing counter.

    Thread-safe.

    Attributes:
        name: Metric name.
        tags: Dimensional labels (optional).
    """

    def __init__(self, name: str, tags: dict[str, str] | None = None) -> None:
        """Initialise the counter at zero.

        Args:
            name: Metric name.
            tags: Optional dimensional labels.
        """
        self._name = name
        self._tags = dict(tags) if tags else {}
        self._value: int = 0
        self._lock = threading.Lock()

    def inc(self, value: int = 1) -> None:
        """Increment the counter.

        Args:
            value: Amount to add (must be non-negative).

        Raises:
            ValueError: If *value* is negative.
        """
        if value < 0:
            raise ValueError(f"Counter increment must be non-negative, got {value}")
        with self._lock:
            self._value += value

    def get(self) -> int:
        """Return the current counter value."""
        with self._lock:
            return self._value

    def snapshot(self) -> dict[str, Any]:
        """Return a serialisable representation of this metric."""
        with self._lock:
            return {
                "type": "counter",
                "name": self._name,
                "tags": dict(self._tags),
                "value": self._value,
            }

    @property
    def name(self) -> str:
        return self._name

    @property
    def tags(self) -> dict[str, str]:
        return dict(self._tags)

    def __repr__(self) -> str:
        return f"Counter({self._name}, {self.get()})"


class Gauge:
    """A point-in-time measurement that can go up and down.

    Thread-safe.

    Attributes:
        name: Metric name.
        tags: Dimensional labels (optional).
    """

    def __init__(self, name: str, tags: dict[str, str] | None = None) -> None:
        """Initialise the gauge at zero.

        Args:
            name: Metric name.
            tags: Optional dimensional labels.
        """
        self._name = name
        self._tags = dict(tags) if tags else {}
        self._value: float = 0.0
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        """Set the gauge to an absolute value.

        Args:
            value: New gauge value.
        """
        with self._lock:
            self._value = value

    def inc(self, value: float = 1.0) -> None:
        """Increase the gauge.

        Args:
            value: Amount to add.
        """
        with self._lock:
            self._value += value

    def dec(self, value: float = 1.0) -> None:
        """Decrease the gauge.

        Args:
            value: Amount to subtract.
        """
        with self._lock:
            self._value -= value

    def get(self) -> float:
        """Return the current gauge value."""
        with self._lock:
            return self._value

    def snapshot(self) -> dict[str, Any]:
        """Return a serialisable representation of this metric."""
        with self._lock:
            return {
                "type": "gauge",
                "name": self._name,
                "tags": dict(self._tags),
                "value": self._value,
            }

    @property
    def name(self) -> str:
        return self._name

    @property
    def tags(self) -> dict[str, str]:
        return dict(self._tags)

    def __repr__(self) -> str:
        return f"Gauge({self._name}, {self.get()})"


class Histogram:
    """A histogram of observed values with summary statistics.

    Records every observation and computes quantiles on demand.  Not
    intended for high-cardinality or ultra-low-latency paths — for that,
    use a streaming sketch.

    Thread-safe.

    Attributes:
        name: Metric name.
        tags: Dimensional labels (optional).
    """

    def __init__(self, name: str, tags: dict[str, str] | None = None) -> None:
        """Initialise an empty histogram.

        Args:
            name: Metric name.
            tags: Optional dimensional labels.
        """
        self._name = name
        self._tags = dict(tags) if tags else {}
        self._values: list[float] = []
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        """Record a single observation.

        Args:
            value: The observed value.
        """
        with self._lock:
            self._values.append(value)

    def get_summary(self) -> dict[str, float]:
        """Return a summary dict with count, sum, min, max, p50, p95, p99.

        Returns:
            A dict with the following keys:
            - ``count`` — number of observations
            - ``sum`` — sum of all observations
            - ``min`` — minimum observed value
            - ``max`` — maximum observed value
            - ``avg`` — arithmetic mean
            - ``p50`` — 50th percentile
            - ``p95`` — 95th percentile
            - ``p99`` — 99th percentile

            Returns all zeros when no observations have been recorded.
        """
        with self._lock:
            n = len(self._values)
            if n == 0:
                return {"count": 0, "sum": 0.0, "min": 0.0, "max": 0.0,
                        "avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}

            sorted_vals = sorted(self._values)
            total = sum(sorted_vals)

            return {
                "count": n,
                "sum": total,
                "min": sorted_vals[0],
                "max": sorted_vals[-1],
                "avg": total / n,
                "p50": _percentile(sorted_vals, 50),
                "p95": _percentile(sorted_vals, 95),
                "p99": _percentile(sorted_vals, 99),
            }

    def snapshot(self) -> dict[str, Any]:
        """Return a serialisable representation of this metric."""
        summary = self.get_summary()
        return {
            "type": "histogram",
            "name": self._name,
            "tags": dict(self._tags),
            **summary,
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def tags(self) -> dict[str, str]:
        return dict(self._tags)

    def __repr__(self) -> str:
        s = self.get_summary()
        return (
            f"Histogram({self._name}, "
            f"count={s['count']}, avg={s['avg']:.3f}, p99={s['p99']:.3f})"
        )


def _percentile(sorted_data: list[float], percentile: int) -> float:
    """Return the *percentile*th percentile of a sorted list.

    Uses linear interpolation between adjacent ranks.
    """
    if not sorted_data:
        return 0.0
    k = (percentile / 100.0) * (len(sorted_data) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class MetricsRegistry:
    """Collects and organises application metrics.

    Provides factory methods for ``Counter``, ``Gauge``, and
    ``Histogram`` instances.  Each metric is uniquely identified by its
    name plus optional tags.

    Thread-safe.
    """

    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Metric factories
    # ------------------------------------------------------------------

    def counter(self, name: str, tags: dict[str, str] | None = None) -> Counter:
        """Obtain (or create) a ``Counter`` identified by *name* and *tags*.

        Args:
            name: Metric name.
            tags: Optional dimensional labels.

        Returns:
            The existing or freshly created ``Counter``.
        """
        key = _metric_key(name, tags)
        with self._lock:
            if key not in self._counters:
                self._counters[key] = Counter(name, tags)
            return self._counters[key]

    def gauge(self, name: str, tags: dict[str, str] | None = None) -> Gauge:
        """Obtain (or create) a ``Gauge`` identified by *name* and *tags*.

        Args:
            name: Metric name.
            tags: Optional dimensional labels.

        Returns:
            The existing or freshly created ``Gauge``.
        """
        key = _metric_key(name, tags)
        with self._lock:
            if key not in self._gauges:
                self._gauges[key] = Gauge(name, tags)
            return self._gauges[key]

    def histogram(self, name: str, tags: dict[str, str] | None = None) -> Histogram:
        """Obtain (or create) a ``Histogram`` identified by *name* and *tags*.

        Args:
            name: Metric name.
            tags: Optional dimensional labels.

        Returns:
            The existing or freshly created ``Histogram``.
        """
        key = _metric_key(name, tags)
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = Histogram(name, tags)
            return self._histograms[key]

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_all(self) -> dict[str, list[dict[str, Any]]]:
        """Return a serialisable snapshot of every registered metric.

        The return value is a dict with three keys (``"counters"``,
        ``"gauges"``, ``"histograms"``), each mapped to a list of
        per-metric snapshots.  This is suitable for serving via a
        health / metrics endpoint.

        Returns:
            A dict suitable for JSON serialisation.
        """
        with self._lock:
            return {
                "counters": [c.snapshot() for c in self._counters.values()],
                "gauges": [g.snapshot() for g in self._gauges.values()],
                "histograms": [h.snapshot() for h in self._histograms.values()],
            }

    def clear(self) -> None:
        """Remove all registered metrics (useful between tests)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MetricsRegistry("
                f"{len(self._counters)} counters, "
                f"{len(self._gauges)} gauges, "
                f"{len(self._histograms)} histograms)"
            )


def _metric_key(name: str, tags: dict[str, str] | None) -> str:
    """Build a unique lookup key from name + optional tags."""
    if not tags:
        return name
    # Sort tags so that ``{"a": "1", "b": "2"}`` and
    # ``{"b": "2", "a": "1"}`` produce the same key.
    items = sorted(tags.items())
    tag_part = ",".join(f"{k}={v}" for k, v in items)
    return f"{name}[{tag_part}]"


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_default_registry: MetricsRegistry | None = None
_registry_lock = threading.Lock()


def metrics() -> MetricsRegistry:
    """Return the module-level default ``MetricsRegistry``.

    The registry is created lazily on first access.  Use this in
    application code that does not require a custom registry instance.

    Returns:
        The shared default ``MetricsRegistry``.
    """
    global _default_registry  # noqa: PLW0603 — intentional module singleton
    if _default_registry is None:
        with _registry_lock:
            if _default_registry is None:  # double-checked locking
                _default_registry = MetricsRegistry()
    return _default_registry

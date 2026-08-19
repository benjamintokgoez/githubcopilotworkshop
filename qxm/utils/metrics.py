"""Thread-safe in-process metrics for application observability.

Snapshots are deterministic Python data structures. They are not a direct
Prometheus exposition-format implementation.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any


def _finite_number(value: int | float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{field_name} must be finite")
    return converted


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("metric name must be a non-empty string")
    return name


@dataclass(frozen=True)
class MetricSample:
    """An immutable metric observation."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        _validate_name(self.name)
        _finite_number(self.value, "value")
        _finite_number(self.timestamp, "timestamp")


class Counter:
    """A thread-safe monotonically increasing value."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = _validate_name(name)
        self.description = description
        self._value = 0.0
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0) -> None:
        """Increase the counter by a finite non-negative amount."""
        increment = _finite_number(amount, "amount")
        if increment < 0:
            raise ValueError("counter amount must be non-negative")
        with self._lock:
            new_value = self._value + increment
            if not math.isfinite(new_value):
                raise ValueError("counter result must be finite")
            self._value = new_value

    @property
    def value(self) -> float:
        """Return an atomic counter value."""
        with self._lock:
            return self._value

    def reset(self) -> None:
        """Reset the counter to zero."""
        with self._lock:
            self._value = 0.0


class Gauge:
    """A thread-safe value that can increase or decrease."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = _validate_name(name)
        self.description = description
        self._value = 0.0
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        """Set the gauge to a finite value."""
        new_value = _finite_number(value, "value")
        with self._lock:
            self._value = new_value

    def inc(self, amount: float = 1.0) -> None:
        """Increase the gauge by a finite amount."""
        increment = _finite_number(amount, "amount")
        with self._lock:
            new_value = self._value + increment
            if not math.isfinite(new_value):
                raise ValueError("gauge result must be finite")
            self._value = new_value

    def dec(self, amount: float = 1.0) -> None:
        """Decrease the gauge by a finite amount."""
        decrement = _finite_number(amount, "amount")
        self.inc(-decrement)

    @property
    def value(self) -> float:
        """Return an atomic gauge value."""
        with self._lock:
            return self._value

    def reset(self) -> None:
        """Reset the gauge to zero."""
        with self._lock:
            self._value = 0.0


class Histogram:
    """Track finite observations in cumulative upper-bound buckets."""

    DEFAULT_BUCKETS = (
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    )

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        self.name = _validate_name(name)
        self.description = description
        raw_buckets = self.DEFAULT_BUCKETS if buckets is None else buckets
        if not raw_buckets:
            raise ValueError("histogram requires at least one bucket")
        validated = tuple(sorted(_finite_number(bucket, "bucket") for bucket in raw_buckets))
        if len(set(validated)) != len(validated):
            raise ValueError("histogram buckets must be unique")
        self._buckets = validated
        self._counts = {bucket: 0 for bucket in validated}
        self._sum = 0.0
        self._count = 0
        self._lock = threading.Lock()

    @property
    def buckets(self) -> tuple[float, ...]:
        """Return ordered finite bucket boundaries."""
        return self._buckets

    def observe(self, value: float) -> None:
        """Record one finite observation in every matching cumulative bucket."""
        observation = _finite_number(value, "value")
        with self._lock:
            new_sum = self._sum + observation
            if not math.isfinite(new_sum):
                raise ValueError("histogram sum must remain finite")
            self._sum = new_sum
            self._count += 1
            for bucket in self._buckets:
                if observation <= bucket:
                    self._counts[bucket] += 1

    def _snapshot(self) -> dict[str, Any]:
        with self._lock:
            count = self._count
            total = self._sum
            bucket_counts = {str(bucket): self._counts[bucket] for bucket in self._buckets}
            bucket_counts["+Inf"] = count
            return {
                "buckets": bucket_counts,
                "count": count,
                "mean": total / count if count else 0.0,
                "sum": total,
            }

    @property
    def count(self) -> int:
        """Return the number of observations."""
        with self._lock:
            return self._count

    @property
    def sum(self) -> float:
        """Return the sum of observations."""
        with self._lock:
            return self._sum

    @property
    def mean(self) -> float:
        """Return the arithmetic mean, or zero when empty."""
        with self._lock:
            return self._sum / self._count if self._count else 0.0

    def reset(self) -> None:
        """Remove all observations while preserving bucket configuration."""
        with self._lock:
            self._counts = {bucket: 0 for bucket in self._buckets}
            self._sum = 0.0
            self._count = 0


class MetricsRegistry:
    """Race-safe registry for counters, gauges, and histograms."""

    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._lock = threading.RLock()

    def _ensure_kind(self, name: str, expected: str) -> None:
        kinds = (
            ("counter", self._counters),
            ("gauge", self._gauges),
            ("histogram", self._histograms),
        )
        for kind, metrics in kinds:
            if kind != expected and name in metrics:
                raise ValueError(f"metric {name!r} is already registered as a {kind}")

    def counter(self, name: str, description: str = "") -> Counter:
        """Return the named counter, creating it atomically if necessary."""
        name = _validate_name(name)
        with self._lock:
            self._ensure_kind(name, "counter")
            metric = self._counters.get(name)
            if metric is None:
                metric = Counter(name, description)
                self._counters[name] = metric
            return metric

    def gauge(self, name: str, description: str = "") -> Gauge:
        """Return the named gauge, creating it atomically if necessary."""
        name = _validate_name(name)
        with self._lock:
            self._ensure_kind(name, "gauge")
            metric = self._gauges.get(name)
            if metric is None:
                metric = Gauge(name, description)
                self._gauges[name] = metric
            return metric

    def histogram(
        self,
        name: str,
        description: str = "",
        *,
        buckets: tuple[float, ...] | None = None,
    ) -> Histogram:
        """Return the named histogram, creating it atomically if necessary."""
        name = _validate_name(name)
        with self._lock:
            self._ensure_kind(name, "histogram")
            metric = self._histograms.get(name)
            if metric is None:
                metric = Histogram(name, description, buckets)
                self._histograms[name] = metric
            elif buckets is not None and metric.buckets != tuple(sorted(buckets)):
                raise ValueError(f"histogram {name!r} already has different buckets")
            return metric

    def snapshot(self) -> dict[str, Any]:
        """Return a deterministic point-in-time snapshot of registered metrics."""
        with self._lock:
            counters = sorted(self._counters.items())
            gauges = sorted(self._gauges.items())
            histograms = sorted(self._histograms.items())
        return {
            "counters": {name: metric.value for name, metric in counters},
            "gauges": {name: metric.value for name, metric in gauges},
            "histograms": {name: metric._snapshot() for name, metric in histograms},
        }

    def reset(self) -> None:
        """Reset all registered metric values without invalidating references."""
        with self._lock:
            metrics: tuple[Counter | Gauge | Histogram, ...] = (
                *self._counters.values(),
                *self._gauges.values(),
                *self._histograms.values(),
            )
        for metric in metrics:
            metric.reset()

    def clear(self) -> None:
        """Remove every metric, providing an isolated empty test registry."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


REGISTRY = MetricsRegistry()

orders_submitted = REGISTRY.counter("qxm_orders_submitted", "Total orders submitted")
orders_filled = REGISTRY.counter("qxm_orders_filled", "Total orders fully filled")
orders_cancelled = REGISTRY.counter("qxm_orders_cancelled", "Total orders cancelled")
trades_executed = REGISTRY.counter("qxm_trades_executed", "Total trades executed")
matching_latency = REGISTRY.histogram(
    "qxm_matching_latency_seconds",
    "Order matching latency",
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1),
)
active_orders = REGISTRY.gauge("qxm_active_orders", "Currently active orders")
portfolio_value = REGISTRY.gauge("qxm_portfolio_value", "Current portfolio value")

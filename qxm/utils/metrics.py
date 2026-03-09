"""Prometheus-style metrics collection for trading system observability.

Provides counters, gauges, histograms, and a registry for export.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MetricSample:
    """A single metric observation."""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class Counter:
    """Monotonically increasing counter."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._value: float = 0.0
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0) -> None:
        if amount < 0:
            raise ValueError("Counter can only increase")
        with self._lock:
            self._value += amount

    @property
    def value(self) -> float:
        return self._value


class Gauge:
    """Value that can go up and down."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._value: float = 0.0
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value -= amount

    @property
    def value(self) -> float:
        return self._value


class Histogram:
    """Tracks value distributions across predefined buckets."""

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: Optional[tuple] = None,
    ) -> None:
        self.name = name
        self.description = description
        self._buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self._counts: Dict[float, int] = {b: 0 for b in self._buckets}
        self._counts[float("inf")] = 0
        self._sum: float = 0.0
        self._count: int = 0
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        """Record a single observation."""
        with self._lock:
            self._sum += value
            self._count += 1
            for bucket in self._buckets:
                if value <= bucket:
                    self._counts[bucket] += 1
            self._counts[float("inf")] += 1

    @property
    def count(self) -> int:
        return self._count

    @property
    def sum(self) -> float:
        return self._sum

    @property
    def mean(self) -> float:
        if self._count == 0:
            return 0.0
        return self._sum / self._count


class MetricsRegistry:
    """Central registry for all application metrics."""

    def __init__(self) -> None:
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}

    def counter(self, name: str, description: str = "") -> Counter:
        if name not in self._counters:
            self._counters[name] = Counter(name, description)
        return self._counters[name]

    def gauge(self, name: str, description: str = "") -> Gauge:
        if name not in self._gauges:
            self._gauges[name] = Gauge(name, description)
        return self._gauges[name]

    def histogram(self, name: str, description: str = "", **kwargs: Any) -> Histogram:
        if name not in self._histograms:
            self._histograms[name] = Histogram(name, description, **kwargs)
        return self._histograms[name]

    def snapshot(self) -> Dict[str, Any]:
        """Return current values for all registered metrics."""
        snap: Dict[str, Any] = {"counters": {}, "gauges": {}, "histograms": {}}
        for name, c in self._counters.items():
            snap["counters"][name] = c.value
        for name, g in self._gauges.items():
            snap["gauges"][name] = g.value
        for name, h in self._histograms.items():
            snap["histograms"][name] = {
                "count": h.count,
                "sum": h.sum,
                "mean": h.mean,
            }
        return snap


# Global registry instance
REGISTRY = MetricsRegistry()

# Pre-defined trading metrics
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

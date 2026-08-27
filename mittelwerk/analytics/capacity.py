"""Validated field-service capacity planning: completion-time projection,
cost estimation, and sensitivity ("what-if") analysis.

Numerical routines deliberately use finite ``float`` values; monetary
``Decimal`` values belong at the calling domain boundary. The capacity model
uses descriptor-cached metrics for deterministic completion and cost estimates.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any


def _finite_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _parameters(
    backlog_hours: float,
    crew_size: float,
    hourly_service_rate: float,
    hours_per_crew_per_day: float,
) -> tuple[float, float, float, float]:
    backlog = _finite_float(backlog_hours, "backlog_hours")
    crew = _finite_float(crew_size, "crew_size")
    rate = _finite_float(hourly_service_rate, "hourly_service_rate")
    capacity = _finite_float(hours_per_crew_per_day, "hours_per_crew_per_day")
    if backlog < 0:
        raise ValueError("backlog_hours must be non-negative")
    if crew <= 0:
        raise ValueError("crew_size must be positive")
    if rate <= 0:
        raise ValueError("hourly_service_rate must be positive")
    if capacity <= 0:
        raise ValueError("hours_per_crew_per_day must be positive")
    return backlog, crew, rate, capacity


class CachedMetric:
    """Descriptor that caches a derived metric until a plan parameter changes."""

    def __init__(self, compute_method: str) -> None:
        self._compute_method = compute_method
        self._cache_attr = ""
        self._hash_attr = ""

    def __set_name__(self, owner: type[Any], name: str) -> None:
        self._cache_attr = f"_cached_{name}"
        self._hash_attr = f"_hash_{name}"

    def __get__(self, obj: Any, objtype: type[Any] | None = None) -> Any:
        if obj is None:
            return self
        current_hash = obj._param_hash()
        if getattr(obj, self._hash_attr, None) == current_hash and hasattr(obj, self._cache_attr):
            return getattr(obj, self._cache_attr)
        value = getattr(obj, self._compute_method)()
        setattr(obj, self._cache_attr, value)
        setattr(obj, self._hash_attr, current_hash)
        return value

    def __set__(self, obj: Any, value: Any) -> None:
        raise AttributeError("capacity metrics are read-only computed properties")


class CapacityModel:
    """Project completion time and cost for a backlog worked by a fixed crew,
    with finite-difference sensitivities to crew size, rate, and backlog."""

    completion_days = CachedMetric("_compute_completion_days")
    cost_estimate = CachedMetric("_compute_cost_estimate")
    crew_sensitivity = CachedMetric("_compute_crew_sensitivity")
    rate_sensitivity = CachedMetric("_compute_rate_sensitivity")
    backlog_sensitivity = CachedMetric("_compute_backlog_sensitivity")

    def __init__(
        self,
        backlog_hours: float,
        crew_size: float,
        hourly_service_rate: float,
        hours_per_crew_per_day: float = 8.0,
    ) -> None:
        (
            self.backlog_hours,
            self.crew_size,
            self.hourly_service_rate,
            self.hours_per_crew_per_day,
        ) = _parameters(backlog_hours, crew_size, hourly_service_rate, hours_per_crew_per_day)

    def _current_parameters(self) -> tuple[float, float, float, float]:
        return _parameters(
            self.backlog_hours,
            self.crew_size,
            self.hourly_service_rate,
            self.hours_per_crew_per_day,
        )

    def _param_hash(self) -> int:
        return hash(self._current_parameters())

    @staticmethod
    def _days(backlog: float, crew: float, capacity: float) -> float:
        return backlog / (crew * capacity)

    def _compute_completion_days(self) -> float:
        backlog, crew, _rate, capacity = self._current_parameters()
        return self._days(backlog, crew, capacity)

    def _compute_cost_estimate(self) -> float:
        backlog, _crew, rate, _capacity = self._current_parameters()
        return backlog * rate

    def utilization_rate(self, rated_capacity_hours_per_day: float) -> float:
        """Return crew utilization against a rated daily capacity, clamped to [0, 1]."""
        rated = _finite_float(rated_capacity_hours_per_day, "rated_capacity_hours_per_day")
        if rated <= 0:
            raise ValueError("rated_capacity_hours_per_day must be positive")
        _backlog, crew, _rate, capacity = self._current_parameters()
        return float(min(1.0, max(0.0, (crew * capacity) / rated)))

    def _compute_crew_sensitivity(self) -> float:
        """d(completion_days)/d(crew_size), estimated by central finite difference."""
        backlog, crew, _rate, capacity = self._current_parameters()
        bump = max(crew * 1e-4, 1e-6)
        up = self._days(backlog, crew + bump, capacity)
        down = self._days(backlog, max(crew - bump, 1e-9), capacity)
        return float((up - down) / (2.0 * bump))

    def _compute_rate_sensitivity(self) -> float:
        """d(cost_estimate)/d(hourly_service_rate) — linear, but computed by
        finite difference for consistency with the other sensitivities."""
        backlog, _crew, rate, _capacity = self._current_parameters()
        bump = max(rate * 1e-4, 1e-6)
        up = backlog * (rate + bump)
        down = backlog * (rate - bump)
        return float((up - down) / (2.0 * bump))

    def _compute_backlog_sensitivity(self) -> float:
        """d(completion_days)/d(backlog_hours)."""
        backlog, crew, _rate, capacity = self._current_parameters()
        bump = max(backlog * 1e-4, 1e-6)
        up = self._days(backlog + bump, crew, capacity)
        down = self._days(max(backlog - bump, 0.0), crew, capacity)
        return float((up - down) / (2.0 * bump))

    def metrics_dict(self) -> dict[str, float]:
        """Return every computed metric in one bounded mapping."""
        return {
            "completion_days": self.completion_days,
            "cost_estimate": self.cost_estimate,
            "crew_sensitivity": self.crew_sensitivity,
            "rate_sensitivity": self.rate_sensitivity,
            "backlog_sensitivity": self.backlog_sensitivity,
        }

    def __repr__(self) -> str:
        return (
            f"CapacityModel(backlog_hours={self.backlog_hours} crew_size={self.crew_size} "
            f"rate={self.hourly_service_rate} completion_days={self.completion_days:.2f})"
        )


def aggregate_capacity(
    models: Sequence[CapacityModel], weights: Sequence[float]
) -> dict[str, float]:
    """Aggregate capacity metrics across equal-length model and weight sequences."""
    if len(models) != len(weights):
        raise ValueError("models and weights must have equal lengths")
    aggregate = {
        "completion_days": 0.0,
        "cost_estimate": 0.0,
        "crew_sensitivity": 0.0,
        "rate_sensitivity": 0.0,
        "backlog_sensitivity": 0.0,
    }
    for index in range(len(models)):
        model = models[index]
        if not isinstance(model, CapacityModel):
            raise ValueError("models must contain CapacityModel instances")
        weight = _finite_float(weights[index], f"weights[{index}]")
        for name, value in model.metrics_dict().items():
            aggregate[name] += value * weight
    return aggregate


__all__ = [
    "CachedMetric",
    "CapacityModel",
    "aggregate_capacity",
]

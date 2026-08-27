"""Validated backlog-at-risk, expected-overrun, and capacity stress-test
analytics.

All backlog-at-risk results use one convention: they are non-negative hours
magnitudes representing backlog exposure beyond plan. Numerical routines
intentionally use ``float``/NumPy; callers should convert domain ``Decimal``
hours values at the boundary and retain Decimal in the domain model.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.stats import norm

FloatArray = NDArray[np.float64]


def _finite_float(value: Any, name: str) -> float:
    """Convert a scalar numerical input to a finite float."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _validate_confidence(confidence: float) -> float:
    result = _finite_float(confidence, "confidence")
    if not 0.0 < result < 1.0:
        raise ValueError("confidence must be strictly between 0 and 1")
    return result


def _validate_horizon(horizon_days: int) -> int:
    if isinstance(horizon_days, bool) or not isinstance(horizon_days, int):
        raise ValueError("horizon_days must be a positive integer")
    if horizon_days <= 0:
        raise ValueError("horizon_days must be a positive integer")
    return horizon_days


def _validate_backlog_hours(backlog_hours: float) -> float:
    result = _finite_float(backlog_hours, "backlog_hours")
    if result < 0:
        raise ValueError("backlog_hours must be non-negative")
    return result


def _overruns(backlog_series: Sequence[float]) -> FloatArray:
    """Return finite, non-negative overrun magnitudes from historical backlog
    deltas (positive delta = backlog grew, i.e. an overrun; negative delta =
    backlog shrank)."""
    if len(backlog_series) == 0:
        raise ValueError("backlog_series must not be empty")
    try:
        deltas = np.asarray(backlog_series, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("backlog_series must contain finite numeric values") from exc
    if deltas.ndim != 1 or deltas.size == 0 or not np.isfinite(deltas).all():
        raise ValueError("backlog_series must contain finite numeric values")
    return np.clip(deltas, 0.0, None)


def _percentile(values: FloatArray, confidence: float) -> float:
    """Use an observed order statistic so historical backlog-at-risk is
    reproducible."""
    return float(np.quantile(values, confidence, method="higher"))


def parametric_backlog_risk(
    open_backlog_hours: float,
    hours_volatility: float,
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> float:
    """Return normal-distribution backlog-at-risk as a non-negative hours magnitude.

    ``open_backlog_hours`` is a non-negative exposure basis, so zero backlog
    has zero risk. ``hours_volatility`` is a fractional day-over-day backlog
    variability. The confidence quantile is ``norm.ppf(confidence)``.
    Confidence below 50% corresponds to a favourable-side normal quantile, so
    its risk magnitude is zero.
    """
    backlog = _validate_backlog_hours(open_backlog_hours)
    volatility = _finite_float(hours_volatility, "hours_volatility")
    if volatility < 0:
        raise ValueError("hours_volatility must be non-negative")
    conf = _validate_confidence(confidence)
    horizon = _validate_horizon(horizon_days)
    return float(max(norm.ppf(conf) * volatility * backlog * math.sqrt(horizon), 0.0))


def parametric_backlog_risk_network(
    open_backlog_hours: float,
    weights: np.ndarray,
    cov_matrix: np.ndarray,
    confidence: float = 0.95,
    horizon_days: int = 1,
    psd_tolerance: float = 1e-10,
) -> float:
    """Return covariance-based parametric backlog-at-risk across a network of
    assets, with PSD covariance-matrix validation."""
    backlog = _validate_backlog_hours(open_backlog_hours)
    conf = _validate_confidence(confidence)
    horizon = _validate_horizon(horizon_days)
    tolerance = _finite_float(psd_tolerance, "psd_tolerance")
    if tolerance < 0:
        raise ValueError("psd_tolerance must be non-negative")

    try:
        vector = np.asarray(weights, dtype=float)
        covariance = np.asarray(cov_matrix, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("weights and cov_matrix must be numeric arrays") from exc
    if vector.ndim != 1 or vector.size == 0:
        raise ValueError("weights must be a non-empty one-dimensional array")
    if covariance.ndim != 2 or covariance.shape != (vector.size, vector.size):
        raise ValueError("cov_matrix dimensions must match the weights vector")
    if not np.isfinite(vector).all() or not np.isfinite(covariance).all():
        raise ValueError("weights and cov_matrix must contain finite values")
    if not np.allclose(covariance, covariance.T, rtol=0.0, atol=tolerance):
        raise ValueError("cov_matrix must be symmetric")

    min_eigenvalue = float(np.linalg.eigvalsh(covariance).min())
    if min_eigenvalue < -tolerance:
        raise ValueError("cov_matrix must be positive semidefinite")
    variance = float(vector @ covariance @ vector)
    return parametric_backlog_risk(backlog, math.sqrt(max(variance, 0.0)), conf, horizon)


def historical_backlog_risk(backlog_series: Sequence[float], confidence: float = 0.95) -> float:
    """Return historical backlog-at-risk as a non-negative hours magnitude.

    The percentile is selected from an observed overrun using NumPy's
    ``higher`` method, avoiding interpolation that can understate a sparse
    overrun tail.
    """
    return _percentile(_overruns(backlog_series), _validate_confidence(confidence))


def conditional_backlog_risk(backlog_series: Sequence[float], confidence: float = 0.95) -> float:
    """Return historical expected overrun (beyond the at-risk threshold) as a
    non-negative hours magnitude."""
    overruns = _overruns(backlog_series)
    threshold = _percentile(overruns, _validate_confidence(confidence))
    return float(overruns[overruns >= threshold].mean())


@dataclass(frozen=True)
class CapacityStressResult:
    """Named stress-test outcome with a compact unpackable value surface."""

    name: str
    stressed_backlog_hours: float
    change: float
    overrun: float

    def as_tuple(self) -> tuple[str, float]:
        """Return the ``(name, stressed_backlog_hours)`` representation."""
        return (self.name, self.stressed_backlog_hours)

    def __iter__(self) -> Iterator[object]:
        """Allow two-value unpacking for callers that only need the headline."""
        return iter(self.as_tuple())


def capacity_stress_test(
    open_backlog_hours: float,
    scenarios: Sequence[tuple[str, float]],
) -> list[CapacityStressResult]:
    """Apply fractional demand shocks and report backlog change and overrun."""
    backlog = _validate_backlog_hours(open_backlog_hours)
    results: list[CapacityStressResult] = []
    for scenario in scenarios:
        if len(scenario) != 2:
            raise ValueError("each scenario must be a (name, shock) pair")
        name, shock = scenario
        if not isinstance(name, str) or not name.strip():
            raise ValueError("scenario name must be a non-empty string")
        shock_value = _finite_float(shock, f"shock for {name}")
        if shock_value < -1.0:
            raise ValueError("shock must not be less than -100%")
        stressed = backlog * (1.0 + shock_value)
        change = stressed - backlog
        results.append(
            CapacityStressResult(
                name=name,
                stressed_backlog_hours=stressed,
                change=change,
                overrun=max(change, 0.0),
            )
        )
    return results


class BacklogRiskEngine:
    """Facade for validated parametric and historical backlog-at-risk calculations."""

    def __init__(
        self,
        default_confidence: float = 0.95,
        default_horizon_days: int = 1,
    ) -> None:
        self._confidence = _validate_confidence(default_confidence)
        self._horizon_days = _validate_horizon(default_horizon_days)

    def compute(
        self,
        open_backlog_hours: float,
        hours_volatility: float | None = None,
        backlog_history: Sequence[float] | None = None,
        confidence: float | None = None,
        horizon_days: int | None = None,
    ) -> dict[str, float]:
        """Compute every requested backlog-at-risk measure using shared conventions.

        Historical methods need only backlog history; ``open_backlog_hours``
        is therefore validated as finite here but required to be
        non-negative only when a value-based parametric calculation is
        requested.
        """
        backlog = _finite_float(open_backlog_hours, "open_backlog_hours")
        conf = self._confidence if confidence is None else _validate_confidence(confidence)
        horizon = self._horizon_days if horizon_days is None else _validate_horizon(horizon_days)
        result: dict[str, float] = {}
        if hours_volatility is not None:
            result["parametric_backlog_risk"] = parametric_backlog_risk(
                backlog, hours_volatility, conf, horizon
            )
        if backlog_history is not None:
            result["historical_backlog_risk"] = historical_backlog_risk(backlog_history, conf)
            result["conditional_backlog_risk"] = conditional_backlog_risk(backlog_history, conf)
        return result


__all__ = [
    "parametric_backlog_risk",
    "parametric_backlog_risk_network",
    "historical_backlog_risk",
    "conditional_backlog_risk",
    "CapacityStressResult",
    "capacity_stress_test",
    "BacklogRiskEngine",
]

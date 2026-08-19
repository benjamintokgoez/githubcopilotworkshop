"""Validated Value at Risk, expected shortfall, and stress-test analytics.

All VaR-family results use one convention: they are non-negative loss
magnitudes in the portfolio's base currency.  Numerical routines intentionally
use ``float``/NumPy; callers should convert monetary ``Decimal`` values at the
domain boundary and retain Decimal values in the domain model.
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


def _validate_horizon(holding_period: int) -> int:
    if isinstance(holding_period, bool) or not isinstance(holding_period, int):
        raise ValueError("holding_period must be a positive integer")
    if holding_period <= 0:
        raise ValueError("holding_period must be a positive integer")
    return holding_period


def _validate_portfolio_value(portfolio_value: float) -> float:
    result = _finite_float(portfolio_value, "portfolio_value")
    if result < 0:
        raise ValueError("portfolio_value must be non-negative")
    return result


def _losses(pnl_series: Sequence[float]) -> FloatArray:
    """Return finite, non-negative loss magnitudes from historical P&L."""
    if len(pnl_series) == 0:
        raise ValueError("pnl_series must not be empty")
    try:
        pnl = np.asarray(pnl_series, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("pnl_series must contain finite numeric values") from exc
    if pnl.ndim != 1 or pnl.size == 0 or not np.isfinite(pnl).all():
        raise ValueError("pnl_series must contain finite numeric values")
    # ``np.maximum`` is typed as a ufunc whose ``__call__`` overloads return
    # ``NDArray[Incomplete]`` (numpy's internal alias for ``Any``) for the
    # ndarray/scalar combination used here, so ``np.clip`` (which has
    # precise generic overloads) is used instead for the same elementwise
    # "loss, or zero" semantics.
    return np.clip(-pnl, 0.0, None)


def _percentile(values: FloatArray, confidence: float) -> float:
    """Use an observed order statistic so historical VaR is reproducible."""
    # ``method=`` has been supported since NumPy 1.22; the project's floor
    # (numpy>=1.26) always has it, so no ``interpolation=`` fallback for
    # pre-1.22 NumPy is needed.
    return float(np.quantile(values, confidence, method="higher"))


def parametric_var(
    portfolio_value: float,
    daily_volatility: float,
    confidence: float = 0.95,
    holding_period: int = 1,
) -> float:
    """Return normal-distribution VaR as a non-negative loss magnitude.

    ``portfolio_value`` is a non-negative exposure basis, so zero exposure
    has zero VaR. ``daily_volatility`` is a decimal return standard
    deviation. The confidence quantile is ``norm.ppf(confidence)``.
    Confidence below 50% corresponds to a gain-side normal quantile, so its
    loss magnitude is zero.
    """
    value = _validate_portfolio_value(portfolio_value)
    volatility = _finite_float(daily_volatility, "daily_volatility")
    if volatility < 0:
        raise ValueError("daily_volatility must be non-negative")
    conf = _validate_confidence(confidence)
    horizon = _validate_horizon(holding_period)
    return float(max(norm.ppf(conf) * volatility * value * math.sqrt(horizon), 0.0))


def parametric_var_portfolio(
    portfolio_value: float,
    weights: np.ndarray,
    cov_matrix: np.ndarray,
    confidence: float = 0.95,
    holding_period: int = 1,
    psd_tolerance: float = 1e-10,
) -> float:
    """Return covariance-based parametric VaR with PSD matrix validation."""
    value = _validate_portfolio_value(portfolio_value)
    conf = _validate_confidence(confidence)
    horizon = _validate_horizon(holding_period)
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
    return parametric_var(value, math.sqrt(max(variance, 0.0)), conf, horizon)


def historical_var(pnl_series: Sequence[float], confidence: float = 0.95) -> float:
    """Return historical VaR as a non-negative loss magnitude.

    The percentile is selected from an observed loss using NumPy's ``higher``
    method, avoiding interpolation that can understate a sparse loss tail.
    """
    return _percentile(_losses(pnl_series), _validate_confidence(confidence))


def conditional_var(pnl_series: Sequence[float], confidence: float = 0.95) -> float:
    """Return historical expected shortfall as a non-negative loss magnitude."""
    losses = _losses(pnl_series)
    threshold = _percentile(losses, _validate_confidence(confidence))
    return float(losses[losses >= threshold].mean())


@dataclass(frozen=True)
class StressResult:
    """Named stress-test outcome with an unpackable legacy value surface."""

    name: str
    stressed_value: float
    change: float
    loss: float

    def as_tuple(self) -> tuple[str, float]:
        """Return the former ``(name, stressed_value)`` representation."""
        return (self.name, self.stressed_value)

    def __iter__(self) -> Iterator[object]:
        """Allow existing two-value unpacking code to keep working."""
        return iter(self.as_tuple())


def stress_test(
    portfolio_value: float,
    scenarios: Sequence[tuple[str, float]],
) -> list[StressResult]:
    """Apply fractional shocks and report value change and loss explicitly."""
    value = _validate_portfolio_value(portfolio_value)
    results: list[StressResult] = []
    for scenario in scenarios:
        if len(scenario) != 2:
            raise ValueError("each scenario must be a (name, shock) pair")
        name, shock = scenario
        if not isinstance(name, str) or not name.strip():
            raise ValueError("scenario name must be a non-empty string")
        shock_value = _finite_float(shock, f"shock for {name}")
        if shock_value < -1.0:
            raise ValueError("shock must not be less than -100%")
        stressed_value = value * (1.0 + shock_value)
        change = stressed_value - value
        results.append(
            StressResult(
                name=name,
                stressed_value=stressed_value,
                change=change,
                loss=max(-change, 0.0),
            )
        )
    return results


class VaREngine:
    """Facade for validated parametric and historical VaR calculations."""

    def __init__(
        self,
        default_confidence: float = 0.95,
        default_holding_period: int = 1,
    ) -> None:
        self._confidence = _validate_confidence(default_confidence)
        self._holding_period = _validate_horizon(default_holding_period)

    def compute(
        self,
        portfolio_value: float,
        daily_volatility: float | None = None,
        pnl_history: Sequence[float] | None = None,
        confidence: float | None = None,
        holding_period: int | None = None,
    ) -> dict[str, float]:
        """Compute every requested VaR measure using shared conventions.

        Historical methods need only P&L history; a portfolio value is
        therefore validated as finite here but required to be non-negative
        only when a value-based parametric calculation is requested.
        """
        value = _finite_float(portfolio_value, "portfolio_value")
        conf = self._confidence if confidence is None else _validate_confidence(confidence)
        horizon = (
            self._holding_period if holding_period is None else _validate_horizon(holding_period)
        )
        result: dict[str, float] = {}
        if daily_volatility is not None:
            result["parametric_var"] = parametric_var(value, daily_volatility, conf, horizon)
        if pnl_history is not None:
            result["historical_var"] = historical_var(pnl_history, conf)
            result["conditional_var"] = conditional_var(pnl_history, conf)
        return result

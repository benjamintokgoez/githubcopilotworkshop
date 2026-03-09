"""Value at Risk (VaR) computation using both parametric (variance-covariance)
and historical simulation methods.

Parametric VaR assumes normally distributed returns and uses the z-score
corresponding to the desired confidence level to estimate the maximum
expected loss over a given holding period.

Historical VaR uses the empirical distribution of past P&L to determine
the loss threshold at the desired percentile.
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import List, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import norm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parametric VaR
# ---------------------------------------------------------------------------

def parametric_var(
    portfolio_value: float,
    daily_volatility: float,
    confidence: float = 0.95,
    holding_period: int = 1,
) -> float:
    r"""Compute parametric (variance-covariance) Value at Risk.

    .. math::

        \text{VaR}_{\alpha} = z_{\alpha} \cdot \sigma \cdot V \cdot \sqrt{T}

    where :math:`z_{\alpha}` is the z-score for the left tail,
    :math:`\sigma` is the daily volatility, :math:`V` is the portfolio
    value, and :math:`T` is the holding period in days.

    Parameters
    ----------
    portfolio_value : float
        Current portfolio value in base currency.
    daily_volatility : float
        Annualised or daily standard deviation of portfolio returns.
    confidence : float
        Confidence level (e.g. 0.95 for 95% VaR).
    holding_period : int
        Number of trading days.

    Returns
    -------
    float
        The VaR estimate (positive number representing potential loss).

    .. note::
        **BUG (Challenge 3)** — The z-score is computed as
        ``norm.ppf(confidence)`` which yields a *positive* z-score
        (right-tail).  For a loss measure we need the *left-tail*
        z-score: ``norm.ppf(1 - confidence)``.  The current
        implementation returns a negative VaR (i.e. a "gain"), which is
        incorrect.
    """
    # BUG: should be norm.ppf(1 - confidence) for left-tail loss
    z_score = norm.ppf(confidence)
    var = z_score * daily_volatility * portfolio_value * math.sqrt(holding_period)
    return var


def parametric_var_portfolio(
    portfolio_value: float,
    weights: np.ndarray,
    cov_matrix: np.ndarray,
    confidence: float = 0.95,
    holding_period: int = 1,
) -> float:
    """Multi-asset parametric VaR using the covariance matrix.

    .. math::

        \\sigma_p = \\sqrt{w^T \\Sigma w}

    Then VaR is computed as for the single-asset case using the portfolio
    volatility :math:`\\sigma_p`.
    """
    portfolio_variance = float(weights.T @ cov_matrix @ weights)
    portfolio_vol = math.sqrt(portfolio_variance)
    return parametric_var(portfolio_value, portfolio_vol, confidence, holding_period)


# ---------------------------------------------------------------------------
# Historical VaR
# ---------------------------------------------------------------------------

def historical_var(
    pnl_series: Sequence[float],
    confidence: float = 0.95,
) -> float:
    """Compute historical VaR from an empirical P&L distribution.

    Sorts past P&L observations and returns the loss at the
    ``(1 - confidence)`` percentile.

    Parameters
    ----------
    pnl_series : sequence of float
        Historical daily P&L values.
    confidence : float
        Confidence level (e.g. 0.95).

    Returns
    -------
    float
        The historical VaR estimate.
    """
    if len(pnl_series) < 2:
        return 0.0
    sorted_pnl = sorted(pnl_series)
    index = int((1 - confidence) * len(sorted_pnl))
    index = max(0, min(index, len(sorted_pnl) - 1))
    return -sorted_pnl[index]  # Return as positive loss number


# ---------------------------------------------------------------------------
# Conditional VaR (Expected Shortfall)
# ---------------------------------------------------------------------------

def conditional_var(
    pnl_series: Sequence[float],
    confidence: float = 0.95,
) -> float:
    """Conditional VaR (CVaR / Expected Shortfall) — the expected loss
    *given* that the loss exceeds VaR.

    .. math::

        \\text{CVaR}_{\\alpha} = \\mathbb{E}[L \\mid L > \\text{VaR}_{\\alpha}]
    """
    if len(pnl_series) < 2:
        return 0.0
    sorted_pnl = sorted(pnl_series)
    cutoff = int((1 - confidence) * len(sorted_pnl))
    cutoff = max(1, cutoff)
    tail = sorted_pnl[:cutoff]
    return -float(np.mean(tail))


# ---------------------------------------------------------------------------
# Stress testing
# ---------------------------------------------------------------------------

def stress_test(
    portfolio_value: float,
    scenarios: Sequence[Tuple[str, float]],
) -> List[Tuple[str, float]]:
    """Apply a set of shock scenarios to a portfolio value.

    Parameters
    ----------
    portfolio_value : float
        Current portfolio value.
    scenarios : sequence of (name, shock_pct)
        Named scenarios where ``shock_pct`` is the fractional change
        (e.g. -0.10 for a 10% decline).

    Returns
    -------
    list of (name, stressed_value)
    """
    results = []
    for name, shock in scenarios:
        stressed = portfolio_value * (1 + shock)
        results.append((name, stressed))
    return results


# ---------------------------------------------------------------------------
# VaR engine — aggregates multiple methods
# ---------------------------------------------------------------------------

class VaREngine:
    """Facade that wraps parametric and historical VaR with caching and
    configurable defaults."""

    def __init__(
        self,
        default_confidence: float = 0.95,
        default_holding_period: int = 1,
    ) -> None:
        self._confidence = default_confidence
        self._holding_period = default_holding_period
        self._cache: dict = {}

    def compute(
        self,
        portfolio_value: float,
        daily_volatility: Optional[float] = None,
        pnl_history: Optional[Sequence[float]] = None,
        confidence: Optional[float] = None,
        holding_period: Optional[int] = None,
    ) -> dict:
        conf = confidence or self._confidence
        hp = holding_period or self._holding_period
        result = {}

        if daily_volatility is not None:
            result["parametric_var"] = parametric_var(
                portfolio_value, daily_volatility, conf, hp
            )

        if pnl_history is not None and len(pnl_history) >= 2:
            result["historical_var"] = historical_var(pnl_history, conf)
            result["conditional_var"] = conditional_var(pnl_history, conf)

        return result

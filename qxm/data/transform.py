"""Market data transformations — OHLC resampling, VWAP/TWAP computation,
normalisation, and return series generation for risk analytics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np

from qxm.core.models import Tick

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OHLC aggregation
# ---------------------------------------------------------------------------

def ticks_to_ohlc(
    ticks: List[Tick],
    interval_seconds: int = 60,
) -> List[Dict]:
    """Aggregate a sequence of ticks into OHLC bars.

    Parameters
    ----------
    ticks : list of Tick
        Sorted by timestamp (ascending).
    interval_seconds : int
        Bar duration in seconds.

    Returns
    -------
    list of dict
        Each dict has keys: symbol, open, high, low, close, volume, timestamp.
    """
    if not ticks:
        return []

    bars = []
    current_bar: Optional[Dict] = None
    bar_end: Optional[datetime] = None

    for tick in ticks:
        price = float(tick.last)
        if current_bar is None or tick.timestamp >= bar_end:
            if current_bar is not None:
                bars.append(current_bar)
            bar_start = tick.timestamp.replace(
                second=(tick.timestamp.second // interval_seconds) * min(interval_seconds, 60),
                microsecond=0,
            )
            bar_end = bar_start + timedelta(seconds=interval_seconds)
            current_bar = {
                "symbol": tick.symbol,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": tick.volume,
                "timestamp": bar_start,
            }
        else:
            current_bar["high"] = max(current_bar["high"], price)
            current_bar["low"] = min(current_bar["low"], price)
            current_bar["close"] = price
            current_bar["volume"] += tick.volume

    if current_bar is not None:
        bars.append(current_bar)

    return bars


# ---------------------------------------------------------------------------
# VWAP / TWAP
# ---------------------------------------------------------------------------

def compute_vwap(ticks: List[Tick]) -> Optional[Decimal]:
    """Volume-Weighted Average Price.

    .. math::

        \\text{VWAP} = \\frac{\\sum_i P_i \\cdot V_i}{\\sum_i V_i}
    """
    if not ticks:
        return None
    total_pv = sum(float(t.last) * t.volume for t in ticks)
    total_v = sum(t.volume for t in ticks)
    if total_v == 0:
        return None
    return Decimal(str(round(total_pv / total_v, 6)))


def compute_twap(ticks: List[Tick]) -> Optional[Decimal]:
    """Time-Weighted Average Price — simple arithmetic mean of prices."""
    if not ticks:
        return None
    prices = [float(t.last) for t in ticks]
    return Decimal(str(round(sum(prices) / len(prices), 6)))


# ---------------------------------------------------------------------------
# Return series
# ---------------------------------------------------------------------------

def compute_returns(prices: List[float], log_returns: bool = True) -> np.ndarray:
    """Compute a return series from a price series.

    Parameters
    ----------
    prices : list of float
        Chronologically ordered prices.
    log_returns : bool
        If True, compute log returns; otherwise simple returns.

    Returns
    -------
    np.ndarray
        Array of returns (length = len(prices) - 1).
    """
    arr = np.array(prices, dtype=np.float64)
    if log_returns:
        return np.diff(np.log(arr))
    return np.diff(arr) / arr[:-1]


def compute_volatility(returns: np.ndarray, annualise: bool = True) -> float:
    """Compute the standard deviation of returns.

    If ``annualise`` is True, scales by :math:`\\sqrt{252}` (trading days).
    """
    vol = float(np.std(returns, ddof=1))
    if annualise:
        vol *= np.sqrt(252)
    return vol


# ---------------------------------------------------------------------------
# Price normalisation
# ---------------------------------------------------------------------------

def normalise_prices(
    prices: List[float],
    method: str = "minmax",
) -> np.ndarray:
    """Normalise a price series.

    Methods:
    - ``minmax``: Scale to [0, 1] range.
    - ``zscore``: Standardise to zero mean, unit variance.
    - ``returns``: Convert to cumulative return from first price.
    """
    arr = np.array(prices, dtype=np.float64)
    if method == "minmax":
        mn, mx = arr.min(), arr.max()
        if mx == mn:
            return np.zeros_like(arr)
        return (arr - mn) / (mx - mn)
    elif method == "zscore":
        mean, std = arr.mean(), arr.std(ddof=1)
        if std == 0:
            return np.zeros_like(arr)
        return (arr - mean) / std
    elif method == "returns":
        return arr / arr[0] - 1
    else:
        raise ValueError(f"Unknown normalisation method: {method}")


# ---------------------------------------------------------------------------
# Rolling statistics
# ---------------------------------------------------------------------------

def rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    """Simple rolling mean (moving average)."""
    if len(values) < window:
        return np.array([])
    cumsum = np.cumsum(np.insert(values, 0, 0))
    return (cumsum[window:] - cumsum[:-window]) / window


def rolling_std(values: np.ndarray, window: int) -> np.ndarray:
    """Rolling standard deviation."""
    if len(values) < window:
        return np.array([])
    result = []
    for i in range(len(values) - window + 1):
        result.append(float(np.std(values[i:i + window], ddof=1)))
    return np.array(result)


def exponential_moving_average(
    values: np.ndarray,
    span: int,
) -> np.ndarray:
    """Exponential moving average (EMA) with given span."""
    alpha = 2.0 / (span + 1)
    ema = np.zeros_like(values, dtype=np.float64)
    ema[0] = values[0]
    for i in range(1, len(values)):
        ema[i] = alpha * values[i] + (1 - alpha) * ema[i - 1]
    return ema

"""Market-data transformations for educational analytics."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypedDict

import numpy as np
from numpy.typing import NDArray

from qxm.core.models import Tick

FloatArray = NDArray[np.float64]


class OHLCBar(TypedDict):
    """JSON-friendly OHLC bar representation."""

    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime


def _as_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("tick timestamps must include an explicit timezone offset")
    return timestamp.astimezone(UTC)


def _float_array(values: Sequence[float] | FloatArray) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError("values must be one-dimensional")
    if not np.all(np.isfinite(array)):
        raise ValueError("values must contain only finite numbers")
    return array


def _validate_window(window: int) -> None:
    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise ValueError("window must be a positive integer")


def ticks_to_ohlc(
    ticks: Sequence[Tick],
    interval_seconds: int = 60,
) -> list[OHLCBar]:
    """Sort ticks and aggregate independent symbols into epoch-aligned bars."""
    if (
        isinstance(interval_seconds, bool)
        or not isinstance(interval_seconds, int)
        or interval_seconds <= 0
    ):
        raise ValueError("interval_seconds must be a positive integer")
    if not ticks:
        return []

    sorted_ticks = sorted(
        ticks,
        key=lambda tick: (_as_utc(tick.timestamp), tick.symbol),
    )
    bars_by_bucket: dict[tuple[str, int], OHLCBar] = {}

    for tick in sorted_ticks:
        timestamp = _as_utc(tick.timestamp)
        epoch_seconds = math.floor(timestamp.timestamp())
        bucket = epoch_seconds // interval_seconds
        key = (tick.symbol, bucket)
        price = float(tick.last)
        if not math.isfinite(price):
            raise ValueError("tick prices must be finite")

        bar = bars_by_bucket.get(key)
        if bar is None:
            bucket_start = datetime.fromtimestamp(
                bucket * interval_seconds,
                tz=UTC,
            )
            bars_by_bucket[key] = {
                "symbol": tick.symbol,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": tick.volume,
                "timestamp": bucket_start,
            }
        else:
            bar["high"] = max(bar["high"], price)
            bar["low"] = min(bar["low"], price)
            bar["close"] = price
            bar["volume"] += tick.volume

    return sorted(
        bars_by_bucket.values(),
        key=lambda bar: (bar["timestamp"], bar["symbol"]),
    )


def compute_vwap(ticks: Sequence[Tick]) -> Decimal | None:
    """Return the volume-weighted average last price."""
    if not ticks:
        return None
    if any(tick.volume < 0 for tick in ticks):
        raise ValueError("tick volumes must be non-negative")
    total_volume = sum(tick.volume for tick in ticks)
    if total_volume == 0:
        return None
    total_price_volume = sum(
        (tick.last * tick.volume for tick in ticks),
        start=Decimal("0"),
    )
    return (total_price_volume / total_volume).quantize(Decimal("0.000001"))


def compute_twap(ticks: Sequence[Tick]) -> Decimal | None:
    """Return the arithmetic mean last price."""
    if not ticks:
        return None
    total = sum((tick.last for tick in ticks), start=Decimal("0"))
    return (total / len(ticks)).quantize(Decimal("0.000001"))


def compute_returns(
    prices: Sequence[float] | FloatArray,
    log_returns: bool = True,
) -> FloatArray:
    """Compute log or simple returns from finite, strictly positive prices."""
    array = _float_array(prices)
    if array.size < 2:
        return np.empty(0, dtype=np.float64)
    if np.any(array <= 0):
        raise ValueError("prices must be strictly positive")
    if log_returns:
        return np.diff(np.log(array))
    return np.diff(array) / array[:-1]


def compute_volatility(
    returns: Sequence[float] | FloatArray,
    annualise: bool = True,
) -> float:
    """Compute sample volatility, returning zero for fewer than two returns."""
    array = _float_array(returns)
    if array.size < 2:
        return 0.0
    volatility = float(np.std(array, ddof=1))
    return volatility * math.sqrt(252.0) if annualise else volatility


def normalise_prices(
    prices: Sequence[float] | FloatArray,
    method: str = "minmax",
) -> FloatArray:
    """Normalize prices using min-max, z-score, or cumulative-return scaling."""
    array = _float_array(prices)
    if method not in {"minmax", "zscore", "returns"}:
        raise ValueError(f"Unknown normalisation method: {method}")
    if array.size == 0:
        return np.empty(0, dtype=np.float64)

    if method == "minmax":
        minimum = float(array.min())
        maximum = float(array.max())
        if maximum == minimum:
            return np.zeros_like(array)
        return (array - minimum) / (maximum - minimum)

    if method == "zscore":
        if array.size < 2:
            return np.zeros_like(array)
        standard_deviation = float(array.std(ddof=1))
        if standard_deviation == 0.0:
            return np.zeros_like(array)
        return (array - float(array.mean())) / standard_deviation

    if np.any(array <= 0):
        raise ValueError("prices must be strictly positive for return normalization")
    baseline = float(array[0])
    return array / baseline - 1.0


def rolling_mean(
    values: Sequence[float] | FloatArray,
    window: int,
) -> FloatArray:
    """Compute a valid-window simple moving average."""
    _validate_window(window)
    array = _float_array(values)
    if array.size < window:
        return np.empty(0, dtype=np.float64)
    cumulative = np.cumsum(np.insert(array, 0, 0.0))
    return (cumulative[window:] - cumulative[:-window]) / window


def rolling_std(
    values: Sequence[float] | FloatArray,
    window: int,
) -> FloatArray:
    """Compute valid-window sample standard deviation."""
    _validate_window(window)
    array = _float_array(values)
    if array.size < window:
        return np.empty(0, dtype=np.float64)
    if window == 1:
        return np.zeros(array.size, dtype=np.float64)
    return np.array(
        [np.std(array[index : index + window], ddof=1) for index in range(array.size - window + 1)],
        dtype=np.float64,
    )


def exponential_moving_average(
    values: Sequence[float] | FloatArray,
    span: int,
) -> FloatArray:
    """Compute an EMA aligned one-to-one with the input values."""
    _validate_window(span)
    array = _float_array(values)
    if array.size == 0:
        return np.empty(0, dtype=np.float64)

    alpha = 2.0 / (span + 1.0)
    ema = np.empty(array.size, dtype=np.float64)
    ema[0] = array[0]
    for index in range(1, array.size):
        ema[index] = alpha * array[index] + (1.0 - alpha) * ema[index - 1]
    return ema

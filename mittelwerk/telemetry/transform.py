"""Telemetry reading transformations for interval aggregation and analytics."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypedDict

import numpy as np
from numpy.typing import NDArray

from mittelwerk.core.models import TelemetryReading

FloatArray = NDArray[np.float64]
WORKING_DAYS_PER_YEAR = 260


class IntervalBar(TypedDict):
    """JSON-friendly interval bar representation."""

    asset_id: str
    open_reading: float
    high_reading: float
    low_reading: float
    close_reading: float
    sample_count: int
    timestamp: datetime


def _as_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("reading timestamps must include an explicit timezone offset")
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


def readings_to_intervals(
    readings: Sequence[TelemetryReading],
    interval_seconds: int = 60,
) -> list[IntervalBar]:
    """Sort readings and aggregate independent assets into epoch-aligned bars."""
    if (
        isinstance(interval_seconds, bool)
        or not isinstance(interval_seconds, int)
        or interval_seconds <= 0
    ):
        raise ValueError("interval_seconds must be a positive integer")
    if not readings:
        return []

    sorted_readings = sorted(
        readings,
        key=lambda reading: (_as_utc(reading.timestamp), reading.asset_id),
    )
    bars_by_bucket: dict[tuple[str, int], IntervalBar] = {}

    for reading in sorted_readings:
        timestamp = _as_utc(reading.timestamp)
        epoch_seconds = math.floor(timestamp.timestamp())
        bucket = epoch_seconds // interval_seconds
        key = (reading.asset_id, bucket)
        value = float(reading.last_reading)
        if not math.isfinite(value):
            raise ValueError("reading values must be finite")

        bar = bars_by_bucket.get(key)
        if bar is None:
            bucket_start = datetime.fromtimestamp(bucket * interval_seconds, tz=UTC)
            bars_by_bucket[key] = {
                "asset_id": reading.asset_id,
                "open_reading": value,
                "high_reading": value,
                "low_reading": value,
                "close_reading": value,
                "sample_count": reading.sample_count,
                "timestamp": bucket_start,
            }
        else:
            bar["high_reading"] = max(bar["high_reading"], value)
            bar["low_reading"] = min(bar["low_reading"], value)
            bar["close_reading"] = value
            bar["sample_count"] += reading.sample_count

    return sorted(
        bars_by_bucket.values(),
        key=lambda bar: (bar["timestamp"], bar["asset_id"]),
    )


def compute_weighted_average(readings: Sequence[TelemetryReading]) -> Decimal | None:
    """Return the sample-count-weighted average reading."""
    if not readings:
        return None
    if any(reading.sample_count < 0 for reading in readings):
        raise ValueError("reading sample counts must be non-negative")
    total_sample_count = sum(reading.sample_count for reading in readings)
    if total_sample_count == 0:
        return None
    total_weighted_readings = sum(
        (reading.last_reading * reading.sample_count for reading in readings),
        start=Decimal("0"),
    )
    return (total_weighted_readings / total_sample_count).quantize(Decimal("0.000001"))


def compute_average(readings: Sequence[TelemetryReading]) -> Decimal | None:
    """Return the arithmetic mean reading."""
    if not readings:
        return None
    total = sum((reading.last_reading for reading in readings), start=Decimal("0"))
    return (total / len(readings)).quantize(Decimal("0.000001"))


def compute_deltas(
    readings: Sequence[float] | FloatArray,
    log_deltas: bool = True,
) -> FloatArray:
    """Compute log or simple deltas between successive finite positive readings."""
    array = _float_array(readings)
    if array.size < 2:
        return np.empty(0, dtype=np.float64)
    if np.any(array <= 0):
        raise ValueError("readings must be strictly positive")
    if log_deltas:
        return np.diff(np.log(array))
    return np.diff(array) / array[:-1]


def compute_variability(
    deltas: Sequence[float] | FloatArray,
    annualise: bool = True,
) -> float:
    """Compute sample signal variability, returning zero for fewer than two deltas."""
    array = _float_array(deltas)
    if array.size < 2:
        return 0.0
    variability = float(np.std(array, ddof=1))
    return variability * math.sqrt(WORKING_DAYS_PER_YEAR) if annualise else variability


def normalise_readings(
    readings: Sequence[float] | FloatArray,
    method: str = "minmax",
) -> FloatArray:
    """Normalize readings using min-max, z-score, or cumulative-delta scaling."""
    array = _float_array(readings)
    if method not in {"minmax", "zscore", "deltas"}:
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
        raise ValueError("readings must be strictly positive for delta normalization")
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
    """Compute an exponentially weighted moving average aligned with the input."""
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


__all__ = [
    "FloatArray",
    "IntervalBar",
    "compute_average",
    "compute_deltas",
    "compute_variability",
    "compute_weighted_average",
    "exponential_moving_average",
    "normalise_readings",
    "readings_to_intervals",
    "rolling_mean",
    "rolling_std",
]

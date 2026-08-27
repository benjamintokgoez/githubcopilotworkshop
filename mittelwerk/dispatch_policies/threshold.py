"""Threshold and trend-based dispatch policies."""

from __future__ import annotations

import math
from typing import Any, ClassVar

import numpy as np

from mittelwerk.core.models import Equipment, TelemetryReading
from mittelwerk.dispatch_policies.base import (
    BasePolicy,
    Recommendation,
    RecommendationUrgency,
    _require_int_parameter,
)
from mittelwerk.telemetry.transform import exponential_moving_average


class CapacityBreach(BasePolicy):
    """Detects reading breaches above or below Donchian-style channels."""

    policy_name: ClassVar[str] = "CapacityBreach"
    version: ClassVar[str] = "1.2.0"

    def __init__(
        self,
        equipment: list[Equipment],
        parameters: dict[str, Any] | None = None,
    ) -> None:
        defaults = {"lookback": 20, "deviation_multiplier": 1.5, "min_ticks": 30}
        merged = {**defaults, **(parameters or {})}
        lookback = _require_int_parameter(merged, "lookback", minimum=2)
        min_ticks = _require_int_parameter(merged, "min_ticks", minimum=lookback + 1)
        deviation_multiplier = float(merged["deviation_multiplier"])
        if deviation_multiplier < 0 or not math.isfinite(deviation_multiplier):
            raise ValueError("deviation_multiplier must be finite and non-negative")
        merged["lookback"] = lookback
        merged["min_ticks"] = min_ticks
        super().__init__(equipment, merged)
        self._breach_state: dict[str, str] = {}

    def on_reading(self, reading: TelemetryReading) -> None:
        self._buffer_reading(reading)

    def generate_recommendations(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        lookback = int(self.parameters["lookback"])
        deviation_multiplier = float(self.parameters["deviation_multiplier"])
        min_ticks = int(self.parameters["min_ticks"])

        for asset_id, buf in self._reading_buffer.items():
            if len(buf) < min_ticks:
                continue

            values = np.array([float(reading.last_reading) for reading in buf])
            if np.any(values <= 0):
                raise ValueError("readings must be strictly positive")
            window = values[-(lookback + 1) : -1]
            upper = float(window.max())
            lower = float(window.min())
            current = float(values[-1])

            average_move = float(np.mean(np.abs(np.diff(window))))
            threshold = deviation_multiplier * average_move
            confidence_scale = max(threshold, abs(upper) * 0.001, 1e-12)

            asset = self.equipment[asset_id]
            state = self._breach_state.get(asset_id)

            if current > upper + threshold and state != "high":
                confidence = min(1.0, max(0.0, (current - upper) / confidence_scale))
                recommendations.append(
                    Recommendation(
                        asset=asset,
                        urgency=(
                            RecommendationUrgency.URGENT
                            if confidence > 0.8
                            else RecommendationUrgency.ELEVATED
                        ),
                        target_rate=current + average_move * 2.0,
                        escalation_rate=upper - average_move,
                        confidence=confidence,
                        metadata={
                            "channel_upper": upper,
                            "average_move": average_move,
                            "lookback": lookback,
                        },
                    )
                )
                self._breach_state[asset_id] = "high"

            elif current < lower - threshold and state != "low":
                confidence = min(1.0, max(0.0, (lower - current) / confidence_scale))
                recommendations.append(
                    Recommendation(
                        asset=asset,
                        urgency=(
                            RecommendationUrgency.SUPPRESS
                            if confidence > 0.8
                            else RecommendationUrgency.DEFER
                        ),
                        target_rate=current - average_move * 2.0,
                        escalation_rate=lower + average_move,
                        confidence=confidence,
                        metadata={
                            "channel_lower": lower,
                            "average_move": average_move,
                            "lookback": lookback,
                        },
                    )
                )
                self._breach_state[asset_id] = "low"
            elif lower <= current <= upper:
                self._breach_state.pop(asset_id, None)

        self._recommendations = recommendations
        return recommendations


class TelemetryTrendCrossover(BasePolicy):
    """Dual-EMA crossover policy for telemetry trend recommendations."""

    policy_name: ClassVar[str] = "TelemetryTrendCrossover"
    version: ClassVar[str] = "1.0.0"

    def __init__(
        self,
        equipment: list[Equipment],
        parameters: dict[str, Any] | None = None,
    ) -> None:
        defaults = {"fast_span": 12, "slow_span": 26}
        merged = {**defaults, **(parameters or {})}
        fast_span = _require_int_parameter(merged, "fast_span", minimum=1)
        slow_span = _require_int_parameter(merged, "slow_span", minimum=fast_span + 1)
        merged["fast_span"] = fast_span
        merged["slow_span"] = slow_span
        super().__init__(equipment, merged)

    def on_reading(self, reading: TelemetryReading) -> None:
        self._buffer_reading(reading, max_buffer=200)

    def generate_recommendations(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        fast_span = int(self.parameters["fast_span"])
        slow_span = int(self.parameters["slow_span"])

        for asset_id, buf in self._reading_buffer.items():
            if len(buf) < slow_span + 1:
                continue

            values = np.array([float(reading.last_reading) for reading in buf])
            if np.any(values <= 0):
                raise ValueError("readings must be strictly positive")
            fast_ema = exponential_moving_average(values, fast_span)
            slow_ema = exponential_moving_average(values, slow_span)

            if fast_ema.shape != slow_ema.shape:
                raise RuntimeError("EMA arrays must align with the source readings")
            difference = fast_ema - slow_ema
            asset = self.equipment[asset_id]

            if difference[-1] > 0 and difference[-2] <= 0:
                confidence = min(
                    1.0,
                    max(0.0, abs(float(difference[-1])) / (abs(float(values[-1])) * 0.01)),
                )
                recommendations.append(
                    Recommendation(
                        asset=asset,
                        urgency=RecommendationUrgency.ELEVATED,
                        confidence=confidence,
                        metadata={
                            "ema_difference": float(difference[-1]),
                            "crossover": "rising",
                        },
                    )
                )
            elif difference[-1] < 0 and difference[-2] >= 0:
                confidence = min(
                    1.0,
                    max(0.0, abs(float(difference[-1])) / (abs(float(values[-1])) * 0.01)),
                )
                recommendations.append(
                    Recommendation(
                        asset=asset,
                        urgency=RecommendationUrgency.DEFER,
                        confidence=confidence,
                        metadata={
                            "ema_difference": float(difference[-1]),
                            "crossover": "falling",
                        },
                    )
                )

        self._recommendations = recommendations
        return recommendations


__all__ = ["CapacityBreach", "TelemetryTrendCrossover"]

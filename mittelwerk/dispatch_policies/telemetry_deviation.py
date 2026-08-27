"""Telemetry-band and cross-asset deviation dispatch policies."""

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


class TelemetryBandDeviation(BasePolicy):
    """Band-based deviation policy over telemetry readings."""

    policy_name: ClassVar[str] = "TelemetryBandDeviation"
    version: ClassVar[str] = "1.1.0"

    def __init__(
        self,
        equipment: list[Equipment],
        parameters: dict[str, Any] | None = None,
    ) -> None:
        defaults = {"window": 20, "band_width": 2.0, "min_ticks": 25}
        merged = {**defaults, **(parameters or {})}
        window = _require_int_parameter(merged, "window", minimum=2)
        min_ticks = _require_int_parameter(merged, "min_ticks", minimum=window + 1)
        band_width = float(merged["band_width"])
        if band_width <= 0 or not math.isfinite(band_width):
            raise ValueError("band_width must be finite and positive")
        merged["window"] = window
        merged["min_ticks"] = min_ticks
        super().__init__(equipment, merged)

    def on_reading(self, reading: TelemetryReading) -> None:
        self._buffer_reading(reading, max_buffer=300)

    def generate_recommendations(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        window = int(self.parameters["window"])
        band_width = float(self.parameters["band_width"])
        min_ticks = int(self.parameters["min_ticks"])

        for asset_id, buf in self._reading_buffer.items():
            if len(buf) < min_ticks:
                continue

            values = np.array([float(reading.last_reading) for reading in buf])
            if np.any(values <= 0):
                raise ValueError("readings must be strictly positive")
            history = values[-(window + 1) : -1]
            current = float(values[-1])
            current_ma = float(history.mean())
            current_std = float(history.std(ddof=1))

            upper_band = current_ma + band_width * current_std
            lower_band = current_ma - band_width * current_std

            if current_std < 1e-9:
                continue

            z_score = (current - current_ma) / current_std
            confidence = min(1.0, max(0.0, abs(z_score) / (band_width * 2.0)))
            asset = self.equipment[asset_id]

            if current >= upper_band:
                recommendations.append(
                    Recommendation(
                        asset=asset,
                        urgency=RecommendationUrgency.DEFER,
                        target_rate=current_ma,
                        escalation_rate=upper_band + current_std,
                        confidence=confidence,
                        metadata={
                            "z_score": float(z_score),
                            "upper_band": float(upper_band),
                            "lower_band": float(lower_band),
                            "ma": float(current_ma),
                            "window": window,
                        },
                    )
                )
            elif current <= lower_band:
                recommendations.append(
                    Recommendation(
                        asset=asset,
                        urgency=RecommendationUrgency.ELEVATED,
                        target_rate=current_ma,
                        escalation_rate=lower_band - current_std,
                        confidence=confidence,
                        metadata={
                            "z_score": float(z_score),
                            "upper_band": float(upper_band),
                            "lower_band": float(lower_band),
                            "ma": float(current_ma),
                            "window": window,
                        },
                    )
                )

        self._recommendations = recommendations
        return recommendations


class CrossAssetTelemetryImbalance(BasePolicy):
    """Detect a statistically unusual relative reading across two assets."""

    policy_name: ClassVar[str] = "CrossAssetTelemetryImbalance"
    version: ClassVar[str] = "0.9.0"

    def __init__(
        self,
        equipment: list[Equipment],
        parameters: dict[str, Any] | None = None,
    ) -> None:
        defaults = {"entry_z": 2.0, "exit_z": 0.5, "lookback": 60}
        merged = {**defaults, **(parameters or {})}
        super().__init__(equipment, merged)
        asset_ids = list(self.equipment.keys())
        pair_value = merged.get("pair", asset_ids[:2])
        if (
            not isinstance(pair_value, (tuple, list))
            or len(pair_value) != 2
            or pair_value[0] == pair_value[1]
            or any(asset_id not in self.equipment for asset_id in pair_value)
        ):
            raise ValueError("pair must contain two distinct configured asset_ids")
        self._pair = (str(pair_value[0]), str(pair_value[1]))

        lookback = _require_int_parameter(merged, "lookback", minimum=2)
        entry_z = float(merged["entry_z"])
        exit_z = float(merged["exit_z"])
        if entry_z <= 0 or not math.isfinite(entry_z):
            raise ValueError("entry_z must be finite and positive")
        if exit_z < 0 or exit_z >= entry_z or not math.isfinite(exit_z):
            raise ValueError("exit_z must satisfy 0 <= exit_z < entry_z")
        merged["lookback"] = lookback
        self._active_imbalance: str | None = None

    def on_reading(self, reading: TelemetryReading) -> None:
        self._buffer_reading(reading, max_buffer=200)

    def generate_recommendations(self) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        self._recommendations = recommendations
        lookback = int(self.parameters["lookback"])
        entry_z = float(self.parameters["entry_z"])
        exit_z = float(self.parameters["exit_z"])

        asset_a, asset_b = self._pair
        buf_a = self._reading_buffer.get(asset_a, [])
        buf_b = self._reading_buffer.get(asset_b, [])

        required = lookback + 1
        if len(buf_a) < required or len(buf_b) < required:
            return recommendations

        values_a = np.array(
            [float(reading.last_reading) for reading in buf_a[-required:]], dtype=np.float64
        )
        values_b = np.array(
            [float(reading.last_reading) for reading in buf_b[-required:]], dtype=np.float64
        )
        if np.any(values_a <= 0) or np.any(values_b <= 0):
            raise ValueError("pair readings must be strictly positive")

        spread = np.log(values_a) - np.log(values_b)
        history = spread[:-1]
        spread_mean = float(history.mean())
        spread_std = float(history.std(ddof=1))

        if spread_std < 1e-9:
            return recommendations

        current_spread = float(spread[-1])
        z = float((current_spread - spread_mean) / spread_std)

        first_asset = self.equipment[asset_a]
        second_asset = self.equipment[asset_b]

        if z > entry_z and self._active_imbalance != "first_high":
            confidence = min(1.0, max(0.0, abs(z) / (entry_z * 2.0)))
            recommendations.append(
                Recommendation(
                    asset=first_asset,
                    urgency=RecommendationUrgency.ELEVATED,
                    confidence=confidence,
                    metadata={
                        "z_score": z,
                        "relative_reading_gap": current_spread,
                        "comparison_assets": [asset_a, asset_b],
                        "assessment": "first_asset_high",
                    },
                )
            )
            recommendations.append(
                Recommendation(
                    asset=second_asset,
                    urgency=RecommendationUrgency.DEFER,
                    confidence=confidence,
                    metadata={
                        "z_score": z,
                        "relative_reading_gap": current_spread,
                        "comparison_assets": [asset_a, asset_b],
                        "assessment": "second_asset_reference",
                    },
                )
            )
            self._active_imbalance = "first_high"

        elif z < -entry_z and self._active_imbalance != "first_low":
            confidence = min(1.0, max(0.0, abs(z) / (entry_z * 2.0)))
            recommendations.append(
                Recommendation(
                    asset=first_asset,
                    urgency=RecommendationUrgency.DEFER,
                    confidence=confidence,
                    metadata={
                        "z_score": z,
                        "relative_reading_gap": current_spread,
                        "comparison_assets": [asset_a, asset_b],
                        "assessment": "first_asset_reference",
                    },
                )
            )
            recommendations.append(
                Recommendation(
                    asset=second_asset,
                    urgency=RecommendationUrgency.ELEVATED,
                    confidence=confidence,
                    metadata={
                        "z_score": z,
                        "relative_reading_gap": current_spread,
                        "comparison_assets": [asset_a, asset_b],
                        "assessment": "second_asset_high",
                    },
                )
            )
            self._active_imbalance = "first_low"

        elif abs(z) < exit_z and self._active_imbalance is not None:
            for asset in (first_asset, second_asset):
                recommendations.append(
                    Recommendation(
                        asset=asset,
                        urgency=RecommendationUrgency.ROUTINE,
                        confidence=1.0,
                        metadata={
                            "z_score": z,
                            "comparison_assets": [asset_a, asset_b],
                            "action": "imbalance_resolved",
                        },
                    )
                )
            self._active_imbalance = None

        self._recommendations = recommendations
        return recommendations


__all__ = ["CrossAssetTelemetryImbalance", "TelemetryBandDeviation"]

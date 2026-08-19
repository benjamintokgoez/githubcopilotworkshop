"""Momentum-based trading strategies — breakout and trend-following."""

from __future__ import annotations

import math
from typing import Any, ClassVar

import numpy as np

from qxm.core.models import Instrument, Tick
from qxm.data.transform import exponential_moving_average
from qxm.strategy.base import (
    BaseStrategy,
    Signal,
    SignalStrength,
    _require_int_parameter,
)


class MomentumBreakout(BaseStrategy):
    """Detects price breakouts above/below Donchian channels.

    Uses a lookback window to compute the highest-high / lowest-low
    channel, then generates signals when price breaks through.

    Parameters
    ----------
    lookback : int
        Number of ticks for the Donchian channel (default 20).
    atr_multiplier : float
        Multiplier for the average absolute close-to-close move (default 1.5).
    min_ticks : int
        Minimum buffered ticks before signal generation (default 30).
    """

    strategy_name: ClassVar[str] = "MomentumBreakout"
    version: ClassVar[str] = "1.2.0"

    def __init__(
        self,
        instruments: list[Instrument],
        parameters: dict[str, Any] | None = None,
    ) -> None:
        defaults = {"lookback": 20, "atr_multiplier": 1.5, "min_ticks": 30}
        merged = {**defaults, **(parameters or {})}
        lookback = _require_int_parameter(merged, "lookback", minimum=2)
        min_ticks = _require_int_parameter(merged, "min_ticks", minimum=lookback + 1)
        atr_multiplier = float(merged["atr_multiplier"])
        if atr_multiplier < 0 or not math.isfinite(atr_multiplier):
            raise ValueError("atr_multiplier must be finite and non-negative")
        merged["lookback"] = lookback
        merged["min_ticks"] = min_ticks
        super().__init__(instruments, merged)
        self._breakout_state: dict[str, str] = {}

    def on_tick(self, tick: Tick) -> None:
        self._buffer_tick(tick)

    def generate_signals(self) -> list[Signal]:
        signals: list[Signal] = []
        lookback = int(self.parameters["lookback"])
        atr_mult = float(self.parameters["atr_multiplier"])
        min_ticks = int(self.parameters["min_ticks"])

        for symbol, buf in self._tick_buffer.items():
            if len(buf) < min_ticks:
                continue

            prices = np.array([float(t.last) for t in buf])
            if np.any(prices <= 0):
                raise ValueError("prices must be strictly positive")
            window = prices[-(lookback + 1) : -1]
            upper = float(window.max())
            lower = float(window.min())
            current = float(prices[-1])

            average_move = float(np.mean(np.abs(np.diff(window))))
            threshold = atr_mult * average_move
            confidence_scale = max(threshold, abs(upper) * 0.001, 1e-12)

            instrument = self.instruments[symbol]
            state = self._breakout_state.get(symbol)

            if current > upper + threshold and state != "long":
                confidence = min(1.0, max(0.0, (current - upper) / confidence_scale))
                signals.append(
                    Signal(
                        instrument=instrument,
                        strength=SignalStrength.STRONG_BUY
                        if confidence > 0.8
                        else SignalStrength.BUY,
                        target_price=current + average_move * 2.0,
                        stop_loss=upper - average_move,
                        confidence=confidence,
                        metadata={
                            "channel_upper": upper,
                            "average_move": average_move,
                            "lookback": lookback,
                        },
                    )
                )
                self._breakout_state[symbol] = "long"

            elif current < lower - threshold and state != "short":
                confidence = min(1.0, max(0.0, (lower - current) / confidence_scale))
                signals.append(
                    Signal(
                        instrument=instrument,
                        strength=(
                            SignalStrength.STRONG_SELL if confidence > 0.8 else SignalStrength.SELL
                        ),
                        target_price=current - average_move * 2.0,
                        stop_loss=lower + average_move,
                        confidence=confidence,
                        metadata={
                            "channel_lower": lower,
                            "average_move": average_move,
                            "lookback": lookback,
                        },
                    )
                )
                self._breakout_state[symbol] = "short"
            elif lower <= current <= upper:
                self._breakout_state.pop(symbol, None)

        self._signals = signals
        return signals


class EMACrossover(BaseStrategy):
    """Dual EMA crossover trend-following strategy.

    Generates BUY when fast EMA crosses above slow EMA, SELL when below.

    Parameters
    ----------
    fast_span : int
        Fast EMA span (default 12).
    slow_span : int
        Slow EMA span (default 26).
    """

    strategy_name: ClassVar[str] = "EMACrossover"
    version: ClassVar[str] = "1.0.0"

    def __init__(
        self,
        instruments: list[Instrument],
        parameters: dict[str, Any] | None = None,
    ) -> None:
        defaults = {"fast_span": 12, "slow_span": 26}
        merged = {**defaults, **(parameters or {})}
        fast_span = _require_int_parameter(merged, "fast_span", minimum=1)
        slow_span = _require_int_parameter(
            merged,
            "slow_span",
            minimum=fast_span + 1,
        )
        merged["fast_span"] = fast_span
        merged["slow_span"] = slow_span
        super().__init__(instruments, merged)

    def on_tick(self, tick: Tick) -> None:
        self._buffer_tick(tick, max_buffer=200)

    def generate_signals(self) -> list[Signal]:
        signals: list[Signal] = []
        fast_span = int(self.parameters["fast_span"])
        slow_span = int(self.parameters["slow_span"])

        for symbol, buf in self._tick_buffer.items():
            if len(buf) < slow_span + 1:
                continue

            prices = np.array([float(t.last) for t in buf])
            if np.any(prices <= 0):
                raise ValueError("prices must be strictly positive")
            fast_ema = exponential_moving_average(prices, fast_span)
            slow_ema = exponential_moving_average(prices, slow_span)

            if fast_ema.shape != slow_ema.shape:
                raise RuntimeError("EMA arrays must align with the source prices")
            difference = fast_ema - slow_ema
            instrument = self.instruments[symbol]

            if difference[-1] > 0 and difference[-2] <= 0:
                confidence = min(
                    1.0,
                    max(0.0, abs(float(difference[-1])) / (abs(float(prices[-1])) * 0.01)),
                )
                signals.append(
                    Signal(
                        instrument=instrument,
                        strength=SignalStrength.BUY,
                        confidence=confidence,
                        metadata={"ema_difference": float(difference[-1]), "crossover": "bullish"},
                    )
                )
            elif difference[-1] < 0 and difference[-2] >= 0:
                confidence = min(
                    1.0,
                    max(0.0, abs(float(difference[-1])) / (abs(float(prices[-1])) * 0.01)),
                )
                signals.append(
                    Signal(
                        instrument=instrument,
                        strength=SignalStrength.SELL,
                        confidence=confidence,
                        metadata={"ema_difference": float(difference[-1]), "crossover": "bearish"},
                    )
                )

        self._signals = signals
        return signals

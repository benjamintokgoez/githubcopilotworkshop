"""Momentum-based trading strategies — breakout and trend-following."""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Dict, List, Optional

import numpy as np

from qxm.core.models import Instrument, Tick
from qxm.data.transform import exponential_moving_average, rolling_mean
from qxm.strategy.base import BaseStrategy, Signal, SignalStrength

logger = logging.getLogger(__name__)


class MomentumBreakout(BaseStrategy):
    """Detects price breakouts above/below Donchian channels.

    Uses a lookback window to compute the highest-high / lowest-low
    channel, then generates signals when price breaks through.

    Parameters
    ----------
    lookback : int
        Number of ticks for the Donchian channel (default 20).
    atr_multiplier : float
        Multiplier for Average True Range filter (default 1.5).
    min_ticks : int
        Minimum buffered ticks before signal generation (default 30).
    """

    strategy_name: ClassVar[str] = "MomentumBreakout"
    version: ClassVar[str] = "1.2.0"

    def __init__(
        self,
        instruments: List[Instrument],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        defaults = {"lookback": 20, "atr_multiplier": 1.5, "min_ticks": 30}
        merged = {**defaults, **(parameters or {})}
        super().__init__(instruments, merged)
        self._breakout_state: Dict[str, str] = {}  # symbol → "long"/"short"/""

    def on_tick(self, tick: Tick) -> None:
        self._buffer_tick(tick)

    def generate_signals(self) -> List[Signal]:
        signals: List[Signal] = []
        lookback = int(self.parameters["lookback"])
        atr_mult = float(self.parameters["atr_multiplier"])
        min_ticks = int(self.parameters["min_ticks"])

        for symbol, buf in self._tick_buffer.items():
            if len(buf) < min_ticks:
                continue

            prices = np.array([float(t.last) for t in buf])
            window = prices[-lookback:]
            upper = float(window.max())
            lower = float(window.min())
            current = prices[-1]

            # Compute simple ATR proxy (average range over lookback)
            highs = np.array([float(t.last) for t in buf[-lookback:]])
            lows = highs * 0.998  # simplified low proxy
            atr = float(np.mean(highs - lows))

            instrument = self.instruments[symbol]

            if current > upper + atr * atr_mult:
                confidence = min(1.0, (current - upper) / (atr * atr_mult + 1e-9))
                signals.append(Signal(
                    instrument=instrument,
                    strength=SignalStrength.STRONG_BUY if confidence > 0.8 else SignalStrength.BUY,
                    target_price=current + atr * 2,
                    stop_loss=upper - atr,
                    confidence=confidence,
                    metadata={"channel_upper": upper, "atr": atr},
                ))
                self._breakout_state[symbol] = "long"

            elif current < lower - atr * atr_mult:
                confidence = min(1.0, (lower - current) / (atr * atr_mult + 1e-9))
                signals.append(Signal(
                    instrument=instrument,
                    strength=SignalStrength.STRONG_SELL if confidence > 0.8 else SignalStrength.SELL,
                    target_price=current - atr * 2,
                    stop_loss=lower + atr,
                    confidence=confidence,
                    metadata={"channel_lower": lower, "atr": atr},
                ))
                self._breakout_state[symbol] = "short"

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
    signal_span : int
        Signal line EMA span — MACD-style (default 9).
    """

    strategy_name: ClassVar[str] = "EMACrossover"
    version: ClassVar[str] = "1.0.0"

    def __init__(
        self,
        instruments: List[Instrument],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        defaults = {"fast_span": 12, "slow_span": 26, "signal_span": 9}
        merged = {**defaults, **(parameters or {})}
        super().__init__(instruments, merged)

    def on_tick(self, tick: Tick) -> None:
        self._buffer_tick(tick, max_buffer=200)

    def generate_signals(self) -> List[Signal]:
        signals: List[Signal] = []
        fast_span = int(self.parameters["fast_span"])
        slow_span = int(self.parameters["slow_span"])

        for symbol, buf in self._tick_buffer.items():
            if len(buf) < slow_span + 5:
                continue

            prices = np.array([float(t.last) for t in buf])
            fast_ema = exponential_moving_average(prices, fast_span)
            slow_ema = exponential_moving_average(prices, slow_span)

            macd = fast_ema - slow_ema
            instrument = self.instruments[symbol]

            # Cross detection (last two points)
            if macd[-1] > 0 and macd[-2] <= 0:
                signals.append(Signal(
                    instrument=instrument,
                    strength=SignalStrength.BUY,
                    confidence=min(1.0, abs(macd[-1]) / (prices[-1] * 0.01 + 1e-9)),
                    metadata={"macd": float(macd[-1]), "crossover": "bullish"},
                ))
            elif macd[-1] < 0 and macd[-2] >= 0:
                signals.append(Signal(
                    instrument=instrument,
                    strength=SignalStrength.SELL,
                    confidence=min(1.0, abs(macd[-1]) / (prices[-1] * 0.01 + 1e-9)),
                    metadata={"macd": float(macd[-1]), "crossover": "bearish"},
                ))

        self._signals = signals
        return signals

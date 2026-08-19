"""Mean-reversion trading strategies — Bollinger Bands and z-score based."""

from __future__ import annotations

import math
from typing import Any, ClassVar

import numpy as np

from qxm.core.models import Instrument, Tick
from qxm.strategy.base import (
    BaseStrategy,
    Signal,
    SignalStrength,
    _require_int_parameter,
)


class BollingerMeanReversion(BaseStrategy):
    """Bollinger Band mean-reversion strategy.

    Sells when price touches the upper band, buys when it touches the
    lower band, expecting reversion to the moving average.

    Parameters
    ----------
    window : int
        Rolling window for the moving average (default 20).
    num_std : float
        Number of standard deviations for the bands (default 2.0).
    min_ticks : int
        Minimum ticks before generating signals (default 25).
    """

    strategy_name: ClassVar[str] = "BollingerMeanReversion"
    version: ClassVar[str] = "1.1.0"

    def __init__(
        self,
        instruments: list[Instrument],
        parameters: dict[str, Any] | None = None,
    ) -> None:
        defaults = {"window": 20, "num_std": 2.0, "min_ticks": 25}
        merged = {**defaults, **(parameters or {})}
        window = _require_int_parameter(merged, "window", minimum=2)
        min_ticks = _require_int_parameter(merged, "min_ticks", minimum=window + 1)
        num_std = float(merged["num_std"])
        if num_std <= 0 or not math.isfinite(num_std):
            raise ValueError("num_std must be finite and positive")
        merged["window"] = window
        merged["min_ticks"] = min_ticks
        super().__init__(instruments, merged)

    def on_tick(self, tick: Tick) -> None:
        self._buffer_tick(tick, max_buffer=300)

    def generate_signals(self) -> list[Signal]:
        signals: list[Signal] = []
        window = int(self.parameters["window"])
        num_std = float(self.parameters["num_std"])
        min_ticks = int(self.parameters["min_ticks"])

        for symbol, buf in self._tick_buffer.items():
            if len(buf) < min_ticks:
                continue

            prices = np.array([float(t.last) for t in buf])
            if np.any(prices <= 0):
                raise ValueError("prices must be strictly positive")
            history = prices[-(window + 1) : -1]
            current = float(prices[-1])
            current_ma = float(history.mean())
            current_std = float(history.std(ddof=1))

            upper_band = current_ma + num_std * current_std
            lower_band = current_ma - num_std * current_std

            if current_std < 1e-9:
                continue

            z_score = (current - current_ma) / current_std
            confidence = min(1.0, max(0.0, abs(z_score) / (num_std * 2.0)))
            instrument = self.instruments[symbol]

            if current >= upper_band:
                signals.append(
                    Signal(
                        instrument=instrument,
                        strength=SignalStrength.SELL,
                        target_price=current_ma,
                        stop_loss=upper_band + current_std,
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
                signals.append(
                    Signal(
                        instrument=instrument,
                        strength=SignalStrength.BUY,
                        target_price=current_ma,
                        stop_loss=lower_band - current_std,
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

        self._signals = signals
        return signals


class StatisticalArbitrage(BaseStrategy):
    """Pairs trading / statistical arbitrage strategy.

    Monitors the z-score of the spread between two instruments and
    trades convergence/divergence.

    Parameters
    ----------
    pair : tuple of str
        The two symbols to monitor (default from first two instruments).
    entry_z : float
        Z-score threshold for entry (default 2.0).
    exit_z : float
        Z-score threshold for exit (default 0.5).
    lookback : int
        Window for z-score computation (default 60).
    """

    strategy_name: ClassVar[str] = "StatisticalArbitrage"
    version: ClassVar[str] = "0.9.0"

    def __init__(
        self,
        instruments: list[Instrument],
        parameters: dict[str, Any] | None = None,
    ) -> None:
        defaults = {"entry_z": 2.0, "exit_z": 0.5, "lookback": 60}
        merged = {**defaults, **(parameters or {})}
        super().__init__(instruments, merged)
        symbols = list(self.instruments.keys())
        pair_value = merged.get("pair", symbols[:2])
        if (
            not isinstance(pair_value, (tuple, list))
            or len(pair_value) != 2
            or pair_value[0] == pair_value[1]
            or any(symbol not in self.instruments for symbol in pair_value)
        ):
            raise ValueError("pair must contain two distinct configured symbols")
        self._pair = (str(pair_value[0]), str(pair_value[1]))

        lookback = _require_int_parameter(merged, "lookback", minimum=2)
        entry_z = float(merged["entry_z"])
        exit_z = float(merged["exit_z"])
        if entry_z <= 0 or not math.isfinite(entry_z):
            raise ValueError("entry_z must be finite and positive")
        if exit_z < 0 or exit_z >= entry_z or not math.isfinite(exit_z):
            raise ValueError("exit_z must satisfy 0 <= exit_z < entry_z")
        merged["lookback"] = lookback
        self._in_trade: str | None = None

    def on_tick(self, tick: Tick) -> None:
        self._buffer_tick(tick, max_buffer=200)

    def generate_signals(self) -> list[Signal]:
        signals: list[Signal] = []
        self._signals = signals
        lookback = int(self.parameters["lookback"])
        entry_z = float(self.parameters["entry_z"])
        exit_z = float(self.parameters["exit_z"])

        sym_a, sym_b = self._pair
        buf_a = self._tick_buffer.get(sym_a, [])
        buf_b = self._tick_buffer.get(sym_b, [])

        required = lookback + 1
        if len(buf_a) < required or len(buf_b) < required:
            return signals

        prices_a = np.array([float(t.last) for t in buf_a[-required:]], dtype=np.float64)
        prices_b = np.array([float(t.last) for t in buf_b[-required:]], dtype=np.float64)
        if np.any(prices_a <= 0) or np.any(prices_b <= 0):
            raise ValueError("pair prices must be strictly positive")

        spread = np.log(prices_a) - np.log(prices_b)
        history = spread[:-1]
        spread_mean = float(history.mean())
        spread_std = float(history.std(ddof=1))

        if spread_std < 1e-9:
            return signals

        current_spread = float(spread[-1])
        z = float((current_spread - spread_mean) / spread_std)

        inst_a = self.instruments[sym_a]
        inst_b = self.instruments[sym_b]

        if z > entry_z and self._in_trade != "short_spread":
            confidence = min(1.0, max(0.0, abs(z) / (entry_z * 2.0)))
            signals.append(
                Signal(
                    instrument=inst_a,
                    strength=SignalStrength.SELL,
                    confidence=confidence,
                    metadata={
                        "z_score": z,
                        "log_spread": current_spread,
                        "pair": [sym_a, sym_b],
                        "leg": "sell_first",
                    },
                )
            )
            signals.append(
                Signal(
                    instrument=inst_b,
                    strength=SignalStrength.BUY,
                    confidence=confidence,
                    metadata={
                        "z_score": z,
                        "log_spread": current_spread,
                        "pair": [sym_a, sym_b],
                        "leg": "buy_second",
                    },
                )
            )
            self._in_trade = "short_spread"

        elif z < -entry_z and self._in_trade != "long_spread":
            confidence = min(1.0, max(0.0, abs(z) / (entry_z * 2.0)))
            signals.append(
                Signal(
                    instrument=inst_a,
                    strength=SignalStrength.BUY,
                    confidence=confidence,
                    metadata={
                        "z_score": z,
                        "log_spread": current_spread,
                        "pair": [sym_a, sym_b],
                        "leg": "buy_first",
                    },
                )
            )
            signals.append(
                Signal(
                    instrument=inst_b,
                    strength=SignalStrength.SELL,
                    confidence=confidence,
                    metadata={
                        "z_score": z,
                        "log_spread": current_spread,
                        "pair": [sym_a, sym_b],
                        "leg": "sell_second",
                    },
                )
            )
            self._in_trade = "long_spread"

        elif abs(z) < exit_z and self._in_trade is not None:
            for instrument in (inst_a, inst_b):
                signals.append(
                    Signal(
                        instrument=instrument,
                        strength=SignalStrength.NEUTRAL,
                        confidence=1.0,
                        metadata={
                            "z_score": z,
                            "pair": [sym_a, sym_b],
                            "action": "close_spread",
                        },
                    )
                )
            self._in_trade = None

        self._signals = signals
        return signals

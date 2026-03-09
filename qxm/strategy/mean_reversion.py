"""Mean-reversion trading strategies — Bollinger Bands and z-score based."""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Dict, List, Optional

import numpy as np

from qxm.core.models import Instrument, Tick
from qxm.data.transform import rolling_mean, rolling_std
from qxm.strategy.base import BaseStrategy, Signal, SignalStrength

logger = logging.getLogger(__name__)


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
        instruments: List[Instrument],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        defaults = {"window": 20, "num_std": 2.0, "min_ticks": 25}
        merged = {**defaults, **(parameters or {})}
        super().__init__(instruments, merged)

    def on_tick(self, tick: Tick) -> None:
        self._buffer_tick(tick, max_buffer=300)

    def generate_signals(self) -> List[Signal]:
        signals: List[Signal] = []
        window = int(self.parameters["window"])
        num_std = float(self.parameters["num_std"])
        min_ticks = int(self.parameters["min_ticks"])

        for symbol, buf in self._tick_buffer.items():
            if len(buf) < min_ticks:
                continue

            prices = np.array([float(t.last) for t in buf])
            ma = rolling_mean(prices, window)
            std = rolling_std(prices, window)

            if len(ma) == 0 or len(std) == 0:
                continue

            current = prices[-1]
            current_ma = ma[-1]
            current_std = std[-1]

            upper_band = current_ma + num_std * current_std
            lower_band = current_ma - num_std * current_std

            instrument = self.instruments[symbol]

            if current_std < 1e-9:
                continue

            z_score = (current - current_ma) / current_std

            if current >= upper_band:
                confidence = min(1.0, abs(z_score) / (num_std + 1))
                signals.append(Signal(
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
                    },
                ))
            elif current <= lower_band:
                confidence = min(1.0, abs(z_score) / (num_std + 1))
                signals.append(Signal(
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
                    },
                ))

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
        instruments: List[Instrument],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        defaults = {"entry_z": 2.0, "exit_z": 0.5, "lookback": 60}
        merged = {**defaults, **(parameters or {})}
        super().__init__(instruments, merged)
        symbols = list(self.instruments.keys())
        if len(symbols) >= 2:
            self._pair = (symbols[0], symbols[1])
        else:
            self._pair = (symbols[0], symbols[0]) if symbols else ("", "")
        self._in_trade: Optional[str] = None  # "long_spread" or "short_spread"

    def on_tick(self, tick: Tick) -> None:
        self._buffer_tick(tick, max_buffer=200)

    def generate_signals(self) -> List[Signal]:
        signals: List[Signal] = []
        lookback = int(self.parameters["lookback"])
        entry_z = float(self.parameters["entry_z"])
        exit_z = float(self.parameters["exit_z"])

        sym_a, sym_b = self._pair
        buf_a = self._tick_buffer.get(sym_a, [])
        buf_b = self._tick_buffer.get(sym_b, [])

        if len(buf_a) < lookback or len(buf_b) < lookback:
            return signals

        prices_a = np.array([float(t.last) for t in buf_a[-lookback:]])
        prices_b = np.array([float(t.last) for t in buf_b[-lookback:]])

        # Use ratio-based spread for simplicity
        min_len = min(len(prices_a), len(prices_b))
        spread = prices_a[-min_len:] / prices_b[-min_len:]

        spread_mean = float(spread.mean())
        spread_std = float(spread.std(ddof=1))

        if spread_std < 1e-9:
            return signals

        z = (spread[-1] - spread_mean) / spread_std

        inst_a = self.instruments[sym_a]
        inst_b = self.instruments[sym_b]

        if z > entry_z and self._in_trade != "short_spread":
            signals.append(Signal(
                instrument=inst_a,
                strength=SignalStrength.SELL,
                confidence=min(1.0, abs(z) / (entry_z * 2)),
                metadata={"z_score": z, "spread": float(spread[-1]), "pair": "sell_A"},
            ))
            signals.append(Signal(
                instrument=inst_b,
                strength=SignalStrength.BUY,
                confidence=min(1.0, abs(z) / (entry_z * 2)),
                metadata={"z_score": z, "spread": float(spread[-1]), "pair": "buy_B"},
            ))
            self._in_trade = "short_spread"

        elif z < -entry_z and self._in_trade != "long_spread":
            signals.append(Signal(
                instrument=inst_a,
                strength=SignalStrength.BUY,
                confidence=min(1.0, abs(z) / (entry_z * 2)),
                metadata={"z_score": z, "spread": float(spread[-1]), "pair": "buy_A"},
            ))
            signals.append(Signal(
                instrument=inst_b,
                strength=SignalStrength.SELL,
                confidence=min(1.0, abs(z) / (entry_z * 2)),
                metadata={"z_score": z, "spread": float(spread[-1]), "pair": "sell_B"},
            ))
            self._in_trade = "long_spread"

        elif abs(z) < exit_z and self._in_trade is not None:
            signals.append(Signal(
                instrument=inst_a,
                strength=SignalStrength.NEUTRAL,
                confidence=0.9,
                metadata={"z_score": z, "action": "close_spread"},
            ))
            self._in_trade = None

        self._signals = signals
        return signals

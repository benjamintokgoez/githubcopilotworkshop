"""qxm.strategy — Algorithmic trading strategies with metaclass registration."""

from qxm.strategy.base import BaseStrategy, Signal, SignalStrength, StrategyMeta
from qxm.strategy.mean_reversion import BollingerMeanReversion, StatisticalArbitrage
from qxm.strategy.momentum import EMACrossover, MomentumBreakout

__all__ = [
    "BaseStrategy",
    "Signal",
    "SignalStrength",
    "StrategyMeta",
    "MomentumBreakout",
    "EMACrossover",
    "BollingerMeanReversion",
    "StatisticalArbitrage",
]

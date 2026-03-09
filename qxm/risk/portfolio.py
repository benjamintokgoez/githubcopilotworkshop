"""Portfolio-level risk analytics, P&L attribution, and aggregation.

Supports operator overloading for intuitive portfolio algebra:
    combined = portfolio_a + portfolio_b
    scaled   = portfolio_a * 0.5
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from qxm.core.models import Position, PortfolioSnapshot, RiskMetrics, Tick
from qxm.risk.greeks import OptionPricer, aggregate_greeks
from qxm.risk.var import VaREngine, parametric_var, historical_var, conditional_var

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Portfolio analytics
# ---------------------------------------------------------------------------

class PortfolioAnalytics:
    """Computes portfolio-level risk metrics including VaR, Greeks, and
    performance statistics.

    Supports operator overloading:

    - ``+`` merges two portfolios (union of positions)
    - ``*`` scales all position quantities by a factor
    - ``-`` computes the difference (for hedging analysis)
    """

    def __init__(
        self,
        positions: Optional[List[Position]] = None,
        cash: Decimal = Decimal("0"),
        client_id: str = "SYSTEM",
    ) -> None:
        self._positions: Dict[str, Position] = {}
        self._cash = cash
        self._client_id = client_id
        self._var_engine = VaREngine()
        self._pnl_history: Dict[str, List[float]] = {}
        self._option_pricers: Dict[str, Tuple[OptionPricer, float]] = {}

        if positions:
            for pos in positions:
                self._positions[pos.symbol] = pos

    # -- Position access -------------------------------------------------

    def add_position(self, position: Position) -> None:
        self._positions[position.symbol] = position

    def get_position(self, symbol: str) -> Optional[Position]:
        return self._positions.get(symbol)

    @property
    def positions(self) -> List[Position]:
        return list(self._positions.values())

    @property
    def symbols(self) -> List[str]:
        return list(self._positions.keys())

    # -- Option pricers --------------------------------------------------

    def register_option(
        self,
        symbol: str,
        pricer: OptionPricer,
        quantity: float,
    ) -> None:
        self._option_pricers[symbol] = (pricer, quantity)

    # -- P&L history for VaR ---------------------------------------------

    def record_daily_pnl(self, symbol: str, pnl: float) -> None:
        if symbol not in self._pnl_history:
            self._pnl_history[symbol] = []
        self._pnl_history[symbol].append(pnl)

    def record_portfolio_pnl(self, pnl: float) -> None:
        self.record_daily_pnl("__portfolio__", pnl)

    # -- Valuation -------------------------------------------------------

    @property
    def total_value(self) -> Decimal:
        mv = sum(
            (p.quantity * p.average_entry_price for p in self._positions.values()),
            Decimal("0"),
        )
        return mv + self._cash

    @property
    def total_pnl(self) -> Decimal:
        realised = sum(
            (p.realised_pnl for p in self._positions.values()), Decimal("0")
        )
        unrealised = sum(
            (p.unrealised_pnl for p in self._positions.values()), Decimal("0")
        )
        return realised + unrealised

    # -- Risk metrics computation ----------------------------------------

    def compute_var(
        self,
        daily_volatility: Optional[float] = None,
        confidence: float = 0.95,
    ) -> Dict[str, float]:
        pv = float(self.total_value)
        pnl = self._pnl_history.get("__portfolio__")
        return self._var_engine.compute(
            portfolio_value=pv,
            daily_volatility=daily_volatility,
            pnl_history=pnl,
            confidence=confidence,
        )

    def compute_greeks(self) -> Dict[str, float]:
        if not self._option_pricers:
            return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
        pricers = [p for p, _ in self._option_pricers.values()]
        quantities = [q for _, q in self._option_pricers.values()]
        return aggregate_greeks(pricers, quantities)

    def risk_metrics(
        self,
        daily_volatility: Optional[float] = None,
        confidence_95: float = 0.95,
        confidence_99: float = 0.99,
    ) -> RiskMetrics:
        var_95 = self.compute_var(daily_volatility, confidence_95)
        var_99 = self.compute_var(daily_volatility, confidence_99)
        greeks = self.compute_greeks()

        return RiskMetrics(
            var_95=Decimal(str(var_95.get("parametric_var", 0))),
            var_99=Decimal(str(var_99.get("parametric_var", 0))),
            delta=Decimal(str(greeks["delta"])),
            gamma=Decimal(str(greeks["gamma"])),
            theta=Decimal(str(greeks["theta"])),
            vega=Decimal(str(greeks["vega"])),
            rho=Decimal(str(greeks["rho"])),
        )

    # -- Snapshot --------------------------------------------------------

    def snapshot(self) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            client_id=self._client_id,
            positions=list(self._positions.values()),
            cash_balance=self._cash,
        )

    # -- Performance stats -----------------------------------------------

    def sharpe_ratio(self, risk_free_rate: float = 0.0) -> Optional[float]:
        pnl = self._pnl_history.get("__portfolio__")
        if not pnl or len(pnl) < 2:
            return None
        returns = np.array(pnl)
        excess = returns - risk_free_rate / 252
        std = float(np.std(excess, ddof=1))
        if std == 0:
            return None
        return float(np.mean(excess)) / std * np.sqrt(252)

    def max_drawdown(self) -> Optional[float]:
        pnl = self._pnl_history.get("__portfolio__")
        if not pnl:
            return None
        cumulative = np.cumsum(pnl)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = cumulative - running_max
        return float(np.min(drawdowns))

    # -- Operator overloading -------------------------------------------

    def __add__(self, other: "PortfolioAnalytics") -> "PortfolioAnalytics":
        merged = PortfolioAnalytics(
            cash=self._cash + other._cash,
            client_id=self._client_id,
        )
        for sym, pos in self._positions.items():
            merged._positions[sym] = pos
        for sym, pos in other._positions.items():
            if sym in merged._positions:
                existing = merged._positions[sym]
                existing.quantity += pos.quantity
                existing.realised_pnl += pos.realised_pnl
                existing.unrealised_pnl += pos.unrealised_pnl
            else:
                merged._positions[sym] = pos
        merged._option_pricers.update(self._option_pricers)
        merged._option_pricers.update(other._option_pricers)
        return merged

    def __mul__(self, factor: float) -> "PortfolioAnalytics":
        scaled = PortfolioAnalytics(
            cash=Decimal(str(float(self._cash) * factor)),
            client_id=self._client_id,
        )
        for sym, pos in self._positions.items():
            scaled_pos = Position(
                client_id=pos.client_id,
                symbol=pos.symbol,
                quantity=Decimal(str(float(pos.quantity) * factor)),
                average_entry_price=pos.average_entry_price,
                realised_pnl=Decimal(str(float(pos.realised_pnl) * factor)),
                unrealised_pnl=Decimal(str(float(pos.unrealised_pnl) * factor)),
            )
            scaled._positions[sym] = scaled_pos
        return scaled

    def __rmul__(self, factor: float) -> "PortfolioAnalytics":
        return self.__mul__(factor)

    def __sub__(self, other: "PortfolioAnalytics") -> "PortfolioAnalytics":
        negated = other * -1.0
        return self + negated

    def __repr__(self) -> str:
        return (
            f"PortfolioAnalytics(client={self._client_id}, "
            f"positions={len(self._positions)}, "
            f"value={self.total_value}, "
            f"pnl={self.total_pnl})"
        )

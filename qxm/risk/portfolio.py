"""Portfolio-level risk analytics built around immutable portfolio algebra.

Positions and cash retain ``Decimal`` precision at the domain boundary.
VaR, Greeks, and performance statistics intentionally convert to ``float``
only when invoking their numerical algorithms.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

import numpy as np

from qxm.core.models import PortfolioSnapshot, Position, RiskMetrics
from qxm.risk.greeks import OptionPricer, aggregate_greeks
from qxm.risk.var import VaREngine

PositionProvider = Callable[[], Sequence[Position]]


def _decimal(value: Any, name: str) -> Decimal:
    """Convert a domain-boundary value to a finite Decimal."""
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def _finite_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _clone_position(position: Position) -> Position:
    """Construct a fresh core position without relying on a Pydantic version."""
    if not isinstance(position, Position):
        raise ValueError("positions must contain Position instances")
    return Position(
        client_id=position.client_id,
        symbol=position.symbol,
        quantity=position.quantity,
        average_entry_price=position.average_entry_price,
        realized_pnl=position.realized_pnl,
        unrealized_pnl=position.unrealized_pnl,
        last_price=position.last_price,
        last_updated=position.last_updated,
    )


def _clone_pricer(pricer: OptionPricer) -> OptionPricer:
    return OptionPricer(pricer.S, pricer.K, pricer.T, pricer.r, pricer.sigma, pricer.is_call)


def _market_value(positions: Iterable[Position]) -> Decimal:
    """Sum core position market values without treating signed notionals as cash."""
    return sum((position.market_value() for position in positions), Decimal("0"))


class PortfolioAnalytics:
    """Compute portfolio risk metrics and safely compose independent books.

    A ``position_provider`` can expose engine-owned positions without creating
    a dependency on the engine implementation.  It is consulted before each
    position-derived result, making the provider authoritative.  Use
    :meth:`replace_positions` for explicit one-off synchronization.
    """

    def __init__(
        self,
        positions: Iterable[Position] | None = None,
        cash: Decimal = Decimal("0"),
        client_id: str = "SYSTEM",
        position_provider: PositionProvider | None = None,
        instruments: Mapping[str, object] | None = None,
    ) -> None:
        if not isinstance(client_id, str) or not client_id:
            raise ValueError("client_id must be a non-empty string")
        if position_provider is not None and not callable(position_provider):
            raise ValueError("position_provider must be callable")
        self._positions: dict[str, Position] = {}
        self._cash = _decimal(cash, "cash")
        self._client_id = client_id
        self._position_provider = position_provider
        self._var_engine = VaREngine()
        self._pnl_history: dict[str, list[float]] = {}
        self._option_pricers: dict[str, tuple[OptionPricer, float]] = {}
        # Kept only as a constructor compatibility surface for existing hosts.
        self._instruments = dict(instruments) if instruments is not None else {}
        if positions is not None:
            self.replace_positions(positions)

    def _aggregate_position(self, position: Position) -> None:
        candidate = _clone_position(position)
        existing = self._positions.get(candidate.symbol)
        if existing is None:
            self._positions[candidate.symbol] = candidate
            return

        combined_quantity = existing.quantity + candidate.quantity
        same_side = (
            existing.quantity == 0
            or candidate.quantity == 0
            or (existing.quantity > 0) == (candidate.quantity > 0)
        )
        if combined_quantity == 0:
            average_entry_price = Decimal("0")
            last_price = None
            last_updated = max(existing.last_updated, candidate.last_updated)
        elif same_side:
            total_quantity = abs(existing.quantity) + abs(candidate.quantity)
            average_entry_price = (
                abs(existing.quantity) * existing.average_entry_price
                + abs(candidate.quantity) * candidate.average_entry_price
            ) / total_quantity
            latest_position = (
                existing if existing.last_updated >= candidate.last_updated else candidate
            )
            last_price = latest_position.last_price
            last_updated = latest_position.last_updated
        else:
            surviving_position = (
                existing if abs(existing.quantity) > abs(candidate.quantity) else candidate
            )
            average_entry_price = surviving_position.average_entry_price
            last_price = surviving_position.last_price
            last_updated = surviving_position.last_updated
        self._positions[candidate.symbol] = Position(
            client_id=existing.client_id,
            symbol=existing.symbol,
            quantity=combined_quantity,
            average_entry_price=average_entry_price,
            realized_pnl=existing.realized_pnl + candidate.realized_pnl,
            unrealized_pnl=existing.unrealized_pnl + candidate.unrealized_pnl,
            last_price=last_price,
            last_updated=last_updated,
        )

    def _sync_from_provider(self) -> None:
        if self._position_provider is None:
            return
        provided = self._position_provider()
        if provided is None:
            raise ValueError("position_provider must return a position sequence")
        self._positions = {}
        for position in provided:
            self._aggregate_position(position)

    def _current_positions(self) -> list[Position]:
        self._sync_from_provider()
        return [_clone_position(position) for position in self._positions.values()]

    def replace_positions(self, positions: Iterable[Position]) -> None:
        """Replace local positions with a cloned, symbol-aggregated snapshot."""
        try:
            supplied = list(positions)
        except TypeError as exc:
            raise ValueError("positions must be iterable") from exc
        self._positions = {}
        for position in supplied:
            self._aggregate_position(position)

    def add_position(self, position: Position) -> None:
        """Add a position without retaining the caller's mutable model."""
        self._sync_from_provider()
        self._aggregate_position(position)

    def get_position(self, symbol: str) -> Position | None:
        """Return a defensive copy of a symbol position, if present."""
        self._sync_from_provider()
        position = self._positions.get(symbol)
        return _clone_position(position) if position is not None else None

    @property
    def positions(self) -> list[Position]:
        """Return defensive copies of the current, provider-synchronized book."""
        return self._current_positions()

    @property
    def symbols(self) -> list[str]:
        self._sync_from_provider()
        return list(self._positions)

    def register_option(self, symbol: str, pricer: OptionPricer, quantity: float) -> None:
        """Register an option pricer and its position quantity."""
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("symbol must be a non-empty string")
        if not isinstance(pricer, OptionPricer):
            raise ValueError("pricer must be an OptionPricer")
        self._option_pricers[symbol] = (_clone_pricer(pricer), _finite_float(quantity, "quantity"))

    def record_daily_pnl(self, symbol: str, pnl: float) -> None:
        """Record finite daily P&L for a symbol or the portfolio."""
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("symbol must be a non-empty string")
        self._pnl_history.setdefault(symbol, []).append(_finite_float(pnl, "pnl"))

    def record_portfolio_pnl(self, pnl: float) -> None:
        """Record finite portfolio P&L for historical VaR calculations."""
        self.record_daily_pnl("__portfolio__", pnl)

    @property
    def total_value(self) -> Decimal:
        return _market_value(self._current_positions()) + self._cash

    @property
    def total_pnl(self) -> Decimal:
        return sum(
            (position.total_pnl for position in self._current_positions()),
            Decimal("0"),
        )

    @property
    def gross_exposure(self) -> Decimal:
        """Return absolute position market value used by parametric VaR.

        Market volatility applies to holdings, not cash.  Absolute values
        ensure short-only and net-short books receive the same risk treatment
        as long books with the same notional exposure.
        """
        return sum(
            (abs(position.market_value()) for position in self._current_positions()),
            Decimal("0"),
        )

    def compute_var(
        self, daily_volatility: float | None = None, confidence: float = 0.95
    ) -> dict[str, float]:
        """Compute VaR using gross position exposure for parametric metrics."""
        return self._var_engine.compute(
            portfolio_value=float(self.gross_exposure),
            daily_volatility=daily_volatility,
            pnl_history=self._pnl_history.get("__portfolio__"),
            confidence=confidence,
        )

    def compute_greeks(self) -> dict[str, float]:
        """Aggregate option Greeks from the registered pricers."""
        if not self._option_pricers:
            return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
        pricers = [pricer for pricer, _ in self._option_pricers.values()]
        quantities = [quantity for _, quantity in self._option_pricers.values()]
        return aggregate_greeks(pricers, quantities)

    def risk_metrics(
        self,
        daily_volatility: float | None = None,
        confidence_95: float = 0.95,
        confidence_99: float = 0.99,
    ) -> RiskMetrics:
        """Return the core risk model, converting numerical results to Decimal."""
        var_95 = self.compute_var(daily_volatility, confidence_95)
        var_99 = self.compute_var(daily_volatility, confidence_99)
        greeks = self.compute_greeks()
        return RiskMetrics(
            var_95=Decimal(str(var_95.get("parametric_var", 0.0))),
            var_99=Decimal(str(var_99.get("parametric_var", 0.0))),
            delta=Decimal(str(greeks["delta"])),
            gamma=Decimal(str(greeks["gamma"])),
            theta=Decimal(str(greeks["theta"])),
            vega=Decimal(str(greeks["vega"])),
            rho=Decimal(str(greeks["rho"])),
        )

    def snapshot(self) -> PortfolioSnapshot:
        """Return a fresh core snapshot; timestamp policy is inherited from core."""
        return PortfolioSnapshot(
            client_id=self._client_id,
            positions=self._current_positions(),
            cash_balance=self._cash,
        )

    def sharpe_ratio(self, risk_free_rate: float = 0.0) -> float | None:
        """Return annualized Sharpe ratio from portfolio daily P&L observations."""
        pnl = self._pnl_history.get("__portfolio__")
        if pnl is None or len(pnl) < 2:
            return None
        rate = _finite_float(risk_free_rate, "risk_free_rate")
        excess = np.asarray(pnl, dtype=float) - rate / 252.0
        std = float(np.std(excess, ddof=1))
        if std == 0.0:
            return None
        return float(np.mean(excess) / std * math.sqrt(252.0))

    def max_drawdown(self) -> float | None:
        """Return the most negative cumulative-P&L drawdown."""
        pnl = self._pnl_history.get("__portfolio__")
        if not pnl:
            return None
        cumulative = np.concatenate((np.array([0.0]), np.cumsum(np.asarray(pnl, dtype=float))))
        return float(np.min(cumulative - np.maximum.accumulate(cumulative)))

    def _copy_state_to(self, target: PortfolioAnalytics, factor: float = 1.0) -> None:
        target._pnl_history = {
            symbol: [value * factor for value in history]
            for symbol, history in self._pnl_history.items()
        }
        target._option_pricers = {
            symbol: (_clone_pricer(pricer), quantity * factor)
            for symbol, (pricer, quantity) in self._option_pricers.items()
        }

    def __add__(self, other: PortfolioAnalytics) -> PortfolioAnalytics:
        """Combine portfolios without mutating either book or losing value.

        Opposite-side holdings are netted to the surviving side's cost basis.
        The signed notional removed by netting is reconciled into cash so
        ``combined.total_value`` and total P&L remain additive.
        """
        if not isinstance(other, PortfolioAnalytics):
            return NotImplemented
        left_positions = self._current_positions()
        right_positions = other._current_positions()
        merged = PortfolioAnalytics(
            cash=self._cash + other._cash,
            client_id=self._client_id,
            instruments=self._instruments,
        )
        merged.replace_positions([*left_positions, *right_positions])
        source_market_value = _market_value(left_positions) + _market_value(right_positions)
        merged._cash += source_market_value - _market_value(merged._current_positions())
        self._copy_state_to(merged)
        for symbol, history in other._pnl_history.items():
            if symbol not in merged._pnl_history:
                merged._pnl_history[symbol] = list(history)
            elif len(merged._pnl_history[symbol]) != len(history):
                raise ValueError(f"cannot combine unaligned P&L history for {symbol}")
            else:
                merged._pnl_history[symbol] = [
                    merged._pnl_history[symbol][index] + history[index]
                    for index in range(len(history))
                ]
        for symbol, (pricer, quantity) in other._option_pricers.items():
            existing = merged._option_pricers.get(symbol)
            if existing is None:
                merged._option_pricers[symbol] = (_clone_pricer(pricer), quantity)
            elif existing[0]._param_hash() != pricer._param_hash():
                raise ValueError(f"cannot combine different option pricers for {symbol}")
            else:
                merged._option_pricers[symbol] = (existing[0], existing[1] + quantity)
        return merged

    def __mul__(self, factor: float) -> PortfolioAnalytics:
        """Scale a portfolio into a new independent portfolio."""
        multiplier = _finite_float(factor, "factor")
        scaled = PortfolioAnalytics(
            cash=self._cash * Decimal(str(multiplier)),
            client_id=self._client_id,
            instruments=self._instruments,
        )
        scaled_positions = []
        for position in self._current_positions():
            scaled_positions.append(
                Position(
                    client_id=position.client_id,
                    symbol=position.symbol,
                    quantity=position.quantity * Decimal(str(multiplier)),
                    average_entry_price=position.average_entry_price,
                    realized_pnl=position.realized_pnl * Decimal(str(multiplier)),
                    unrealized_pnl=position.unrealized_pnl * Decimal(str(multiplier)),
                    last_price=position.last_price,
                    last_updated=position.last_updated,
                )
            )
        scaled.replace_positions(scaled_positions)
        self._copy_state_to(scaled, multiplier)
        return scaled

    def __rmul__(self, factor: float) -> PortfolioAnalytics:
        return self * factor

    def __sub__(self, other: PortfolioAnalytics) -> PortfolioAnalytics:
        if not isinstance(other, PortfolioAnalytics):
            return NotImplemented
        return self + (other * -1.0)

    def __repr__(self) -> str:
        return (
            f"PortfolioAnalytics(client={self._client_id}, "
            f"positions={len(self.positions)}, value={self.total_value}, "
            f"pnl={self.total_pnl})"
        )

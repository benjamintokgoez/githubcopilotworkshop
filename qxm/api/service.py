"""Application services shared by the REST routes.

Everything here lives on the FastAPI ``app.state`` of a single application
instance — there are no module-level singletons, so two applications created in
the same process are fully isolated.

The service layer owns the API-local bookkeeping that the core deliberately does
not: which orders were submitted through the API by which client, and a per
client P&L trajectory used by the dashboard chart.  Orders are kept as live
references, so status transitions made by the engine are visible immediately.

It is also the integration point for persistence: every trade produced by a
successful submission is written to the configured
:class:`~qxm.data.store.TimeSeriesStore` off the event loop.  Matching happens
in memory and cannot be rolled back, so this boundary is explicitly
non-atomic — a persistence failure raises :class:`TradePersistenceError`
*after* execution and the API reports exactly that.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from qxm.core.engine import MatchingEngine, OrderSubmission
from qxm.core.events import EventBus
from qxm.core.models import Instrument, Order, Position, Trade, utcnow
from qxm.data.store import TimeSeriesStore
from qxm.risk.portfolio import PortfolioAnalytics

logger = logging.getLogger(__name__)

#: Default display currency for the DACH audience.  The platform performs no FX
#: conversion — the label states the reporting unit, nothing more.
DEFAULT_DISPLAY_CURRENCY = "EUR"
#: Bound on the retained per-client P&L trajectory.
PNL_HISTORY_LIMIT = 500
#: Order-book depth included in the dashboard payload.
DASHBOARD_BOOK_DEPTH = 10


class TradePersistenceError(RuntimeError):
    """Raised when executed trades could not be written to the store.

    The execution itself stands: the in-memory engine is authoritative and the
    order keeps whatever status the match produced.  The error carries only
    reconciliation identifiers — never store internals or credentials, which
    stay in the server log with the original exception attached as ``__cause__``.
    """

    def __init__(self, order: Order, trades: Iterable[Trade]) -> None:
        self.order_id = order.order_id
        self.order_status = order.status.value
        self.filled_quantity = str(order.filled_quantity)
        self.trade_ids = [trade.trade_id for trade in trades]
        super().__init__(
            f"Order {order.order_id!r} executed but "
            f"{len(self.trade_ids)} trade(s) could not be persisted"
        )


@dataclass(frozen=True)
class SubmissionResult:
    """Engine submission plus its directly reported rejection reason."""

    submission: OrderSubmission
    rejection_reason: str | None = None

    @property
    def order(self) -> Order:
        return self.submission.order

    @property
    def trades(self) -> list[Trade]:
        return list(self.submission.trades)

    @property
    def accepted(self) -> bool:
        return self.submission.accepted


@dataclass
class _ClientBook:
    """Per-client API bookkeeping."""

    orders: dict[str, Order] = field(default_factory=dict)
    pnl_history: deque[tuple[datetime, Decimal]] = field(
        default_factory=lambda: deque(maxlen=PNL_HISTORY_LIMIT)
    )
    portfolio: PortfolioAnalytics | None = None


class TradingService:
    """Client-scoped view over the shared matching engine."""

    def __init__(
        self,
        engine: MatchingEngine,
        event_bus: EventBus,
        *,
        display_currency: str = DEFAULT_DISPLAY_CURRENCY,
        daily_volatility: float | None = None,
        store: TimeSeriesStore | None = None,
    ) -> None:
        if (
            not isinstance(display_currency, str)
            or len(display_currency.strip()) != 3
            or not display_currency.strip().isascii()
            or not display_currency.strip().isalpha()
        ):
            raise ValueError("display_currency must be a 3-letter ASCII currency code")
        if daily_volatility is not None:
            if isinstance(daily_volatility, bool) or not isinstance(daily_volatility, (int, float)):
                raise TypeError("daily_volatility must be a number or None")
            if daily_volatility <= 0:
                raise ValueError("daily_volatility must be positive")
        self._engine = engine
        self._event_bus = event_bus
        self._display_currency = display_currency.strip().upper()
        self._daily_volatility = float(daily_volatility) if daily_volatility else None
        self._store = store
        self._instrument_currencies = {
            symbol: instrument.currency for symbol, instrument in self._engine.instruments.items()
        }
        self._books: dict[str, _ClientBook] = {}

    # -- Accessors --------------------------------------------------------

    @property
    def engine(self) -> MatchingEngine:
        return self._engine

    @property
    def display_currency(self) -> str:
        return self._display_currency

    @property
    def store(self) -> TimeSeriesStore | None:
        """The configured store, or ``None`` when persistence is disabled."""
        return self._store

    def _book(self, client_id: str) -> _ClientBook:
        book = self._books.get(client_id)
        if book is None:
            book = _ClientBook()
            self._books[client_id] = book
        return book

    def portfolio_for(self, client_id: str) -> PortfolioAnalytics:
        """Return the client's analytics view, bound to that client's positions.

        Binding a ``position_provider`` per client keeps counterparties from
        netting each other out in a shared portfolio.
        """
        book = self._book(client_id)
        if book.portfolio is None:

            def provider() -> list[Position]:
                return self._engine.client_positions(client_id)

            book.portfolio = PortfolioAnalytics(
                client_id=client_id,
                position_provider=provider,
            )
        return book.portfolio

    def orders_for(self, client_id: str) -> list[Order]:
        """Return the client's API-submitted orders, newest last."""
        orders = list(self._book(client_id).orders.values())
        return sorted(orders, key=lambda order: (order.created_at, order.order_id))

    def get_order(self, client_id: str, order_id: str) -> Order | None:
        return self._book(client_id).orders.get(order_id)

    def active_order_count(self, client_id: str) -> int:
        return sum(1 for order in self._book(client_id).orders.values() if order.is_active)

    def positions_for(self, client_id: str) -> list[Position]:
        return self._engine.client_positions(client_id)

    def currency_for_symbol(self, symbol: str) -> str:
        """Return the configured instrument currency for ``symbol``."""
        try:
            return self._instrument_currencies[symbol]
        except KeyError as exc:
            raise RuntimeError(
                f"Position symbol {symbol!r} has no configured instrument currency"
            ) from exc

    # -- Order flow -------------------------------------------------------

    async def submit_order(self, client_id: str, order: Order) -> SubmissionResult:
        """Submit ``order`` to the engine and register it for this client.

        :class:`~qxm.core.engine.DuplicateOrderError` propagates untouched so the
        route can answer 409 without either order being mutated.

        Executed trades are persisted after the match.  A persistence failure
        raises :class:`TradePersistenceError`; the order stays registered with
        its real, executed status because the match cannot be undone.
        """
        if order.client_id != client_id:
            raise ValueError("order client_id must match the authenticated client")
        submission = await self._engine.submit_order(order)
        self._book(client_id).orders[order.order_id] = order
        self._record_pnl(submission.trades)
        await self._persist_trades(order, submission.trades)
        return SubmissionResult(
            submission=submission,
            rejection_reason=submission.rejection_reason,
        )

    # -- Persistence -------------------------------------------------------

    async def _persist_trades(self, order: Order, trades: Iterable[Trade]) -> None:
        """Write executed trades to the store without blocking the event loop.

        ``store is None`` is the one benign case: persistence is intentionally
        off (see ``create_app(enable_store=False)``) and that is reported at
        startup rather than hidden here.  A *configured* store that is closed is
        not benign — the deployment expects persistence and is not getting it —
        so it raises the same :class:`TradePersistenceError` as a write failure.
        """
        executed = list(trades)
        if not executed:
            return
        store = self._store
        if store is None:
            return
        if store.is_closed:
            logger.error(
                "Cannot persist %d executed trade(s) for order %s: the "
                "configured time-series store is closed",
                len(executed),
                order.order_id,
            )
            raise TradePersistenceError(order, executed)

        payloads = [
            {
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "buy_order_id": trade.buy_order_id,
                "sell_order_id": trade.sell_order_id,
                "price": trade.price,
                "quantity": trade.quantity,
                "buyer_client_id": trade.buyer_client_id,
                "seller_client_id": trade.seller_client_id,
                "timestamp": trade.timestamp,
            }
            for trade in executed
        ]
        try:
            await asyncio.to_thread(store.insert_trades, payloads)
        except Exception as exc:  # translated, logged, and re-raised — never hidden
            logger.exception(
                "Persisting %d executed trade(s) for order %s failed",
                len(executed),
                order.order_id,
            )
            raise TradePersistenceError(order, executed) from exc

    async def cancel_order(self, client_id: str, order_id: str) -> Order | None:
        """Cancel a resting order owned by ``client_id``.

        Returns ``None`` when the order is not resting (already terminal).
        Ownership is checked by the caller through :meth:`get_order`.
        """
        owned = self.get_order(client_id, order_id)
        if owned is None:
            raise KeyError(order_id)
        return await self._engine.cancel_order(order_id, owned.symbol)

    # -- P&L trajectory ----------------------------------------------------

    def _record_pnl(self, trades: Iterable[Trade]) -> None:
        """Append one P&L observation per client touched by ``trades``.

        The series is event-driven and therefore deterministic for a given order
        flow: no trades means no points.
        """
        trade_list = list(trades)
        if not trade_list:
            return
        stamp = trade_list[-1].timestamp
        clients = {trade.buyer_client_id for trade in trade_list}
        clients.update(trade.seller_client_id for trade in trade_list)
        for client_id in sorted(clients):
            total = sum(
                (position.total_pnl for position in self._engine.client_positions(client_id)),
                Decimal("0"),
            )
            self._book(client_id).pnl_history.append((stamp, total))

    def pnl_history(self, client_id: str) -> list[dict[str, str]]:
        return [
            {"timestamp": stamp.isoformat(), "value": str(value)}
            for stamp, value in self._book(client_id).pnl_history
        ]

    # -- Dashboard ---------------------------------------------------------

    def risk_payload(self, client_id: str) -> dict[str, Any]:
        """Risk figures for the client.

        ``var_95`` / ``var_99`` are ``None`` unless a daily volatility
        assumption is configured — the platform does not invent one.
        """
        portfolio = self.portfolio_for(client_id)
        metrics = portfolio.risk_metrics(daily_volatility=self._daily_volatility)
        has_var = self._daily_volatility is not None
        return {
            "var_95": str(metrics.var_95) if has_var else None,
            "var_99": str(metrics.var_99) if has_var else None,
            "delta": str(metrics.delta),
            "gamma": str(metrics.gamma),
            "theta": str(metrics.theta),
            "vega": str(metrics.vega),
            "rho": str(metrics.rho),
            "sharpe_ratio": portfolio.sharpe_ratio(),
            "max_drawdown": portfolio.max_drawdown(),
            "gross_exposure": str(portfolio.gross_exposure),
            "computed_at": metrics.computed_at.isoformat(),
        }

    def position_payload(self, client_id: str) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for position in sorted(self.positions_for(client_id), key=lambda p: p.symbol):
            last_price = position.last_price
            payload.append(
                {
                    "symbol": position.symbol,
                    "currency": self.currency_for_symbol(position.symbol),
                    "quantity": str(position.quantity),
                    "average_entry_price": str(position.average_entry_price),
                    "last_price": None if last_price is None else str(last_price),
                    "market_price": None if last_price is None else str(last_price),
                    "market_value": str(position.market_value()),
                    "realized_pnl": str(position.realized_pnl),
                    "unrealized_pnl": str(position.unrealized_pnl),
                    "total_pnl": str(position.total_pnl),
                }
            )
        return payload

    def order_book_payload(
        self, depth: int = DASHBOARD_BOOK_DEPTH
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """Public market depth per symbol; empty books are included honestly."""
        return {
            symbol: book.depth_snapshot(levels=depth)
            for symbol, book in sorted(self._engine.books.items())
        }

    def dashboard_payload(self, client_id: str) -> dict[str, Any]:
        """Assemble the dashboard contract for one authenticated client."""
        portfolio = self.portfolio_for(client_id)
        positions = self.position_payload(client_id)
        risk = self.risk_payload(client_id)
        snapshot = portfolio.snapshot()
        return {
            "as_of": utcnow(),
            "currency": self._display_currency,
            "kpis": {
                "portfolio_value": str(portfolio.total_value),
                "realized_pnl": str(snapshot.total_realized_pnl),
                "unrealized_pnl": str(snapshot.total_unrealized_pnl),
                "var_95": risk["var_95"],
                "active_orders": self.active_order_count(client_id),
            },
            "positions": positions,
            "pnl_history": self.pnl_history(client_id),
            "risk": risk,
            "order_books": self.order_book_payload(),
        }


def search_instruments_in_memory(
    instruments: Mapping[str, Instrument], query: str, limit: int
) -> list[dict[str, str]]:
    """Case-insensitive substring search over in-memory reference data.

    Used when no database is configured.  The term is compared with plain
    string containment, so SQL metacharacters carry no meaning at all.
    """
    term = query.strip().casefold()
    matches = [
        instrument
        for instrument in instruments.values()
        if term in instrument.symbol.casefold() or term in instrument.name.casefold()
    ]
    matches.sort(key=lambda instrument: instrument.symbol)
    return [
        {
            "symbol": instrument.symbol,
            "name": instrument.name,
            "instrument_type": instrument.instrument_type.value,
            "currency": instrument.currency,
            "exchange": instrument.exchange,
            "tick_size": str(instrument.tick_size),
            "lot_size": str(instrument.lot_size),
        }
        for instrument in matches[:limit]
    ]


__all__ = [
    "DEFAULT_DISPLAY_CURRENCY",
    "PNL_HISTORY_LIMIT",
    "DASHBOARD_BOOK_DEPTH",
    "TradePersistenceError",
    "SubmissionResult",
    "TradingService",
    "search_instruments_in_memory",
]

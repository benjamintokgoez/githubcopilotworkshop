"""FIFO price-time priority matching engine for the QXM exchange.

Supports LIMIT and MARKET orders with GTC / IOC / FOK time-in-force semantics.
Fills always occur at the resting (maker) order's price.

Order types and time-in-force values that would require subsystems the core
does not provide are rejected explicitly rather than behaving dishonestly:

* STOP and STOP_LIMIT need a stop-trigger engine (none exists) and are rejected.
* DAY and GTD need a session clock / expiry processor (none exists); without
  one they would rest forever, so they are rejected too.  GTC / IOC / FOK are
  fully supported.

All lifecycle transitions are published as :class:`DomainEvent` instances via
the :class:`EventBus`, enabling downstream consumers (risk, position manager,
strategy layer) to react asynchronously.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import (
    Protocol,
    runtime_checkable,
)

from qxm.core.book import OrderBook
from qxm.core.events import DomainEvent, EventBus, EventType
from qxm.core.models import (
    Instrument,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
    TimeInForce,
    Trade,
    utcnow,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DuplicateOrderError(Exception):
    """Raised when an ``order_id`` already known to the engine is submitted
    again.  An id becomes known the moment a submission is attempted and stays
    known permanently — including ids whose submission was later rejected or
    killed — so ids are never reusable on the same engine.  Any prior order
    carrying that id is left untouched.  API layers should map this to an
    HTTP 409 Conflict."""

    def __init__(self, order_id: str) -> None:
        self.order_id = order_id
        super().__init__(f"Order {order_id!r} has already been submitted")


# ---------------------------------------------------------------------------
# Risk check protocol (structural subtyping)
# ---------------------------------------------------------------------------


@runtime_checkable
class PreTradeRiskCheck(Protocol):
    """Structural protocol for pre-trade risk validators.  Any object
    implementing ``can_execute`` is accepted without explicit inheritance."""

    def can_execute(self, order: Order, position: Position | None) -> tuple[bool, str]: ...


# ---------------------------------------------------------------------------
# Submission result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderSubmission:
    """Result of :meth:`MatchingEngine.submit_order`."""

    order: Order
    trades: list[Trade] = field(default_factory=list)
    rejection_reason: str | None = None

    @property
    def accepted(self) -> bool:
        return self.order.status is not OrderStatus.REJECTED

    @property
    def filled_quantity(self) -> Decimal:
        return self.order.filled_quantity


# ---------------------------------------------------------------------------
# Position manager — tracks per-client positions
# ---------------------------------------------------------------------------


class PositionManager:
    """In-memory position tracker keyed by ``(client_id, symbol)``."""

    def __init__(self) -> None:
        self._positions: dict[tuple[str, str], Position] = {}

    def get_position(self, client_id: str, symbol: str) -> Position:
        key = (client_id, symbol)
        pos = self._positions.get(key)
        if pos is None:
            pos = Position(client_id=client_id, symbol=symbol)
            self._positions[key] = pos
        return pos

    def peek_position(self, client_id: str, symbol: str) -> Position | None:
        """Return an existing position or ``None`` without creating one."""
        return self._positions.get((client_id, symbol))

    def apply_fill(
        self,
        client_id: str,
        symbol: str,
        side: Side,
        quantity: Decimal,
        price: Decimal,
    ) -> Position:
        pos = self.get_position(client_id, symbol)
        pos.apply_fill(side, quantity, price)
        return pos

    def all_positions(self) -> list[Position]:
        return list(self._positions.values())

    def client_positions(self, client_id: str) -> list[Position]:
        return [p for p in self._positions.values() if p.client_id == client_id]

    def get_positions(self, client_id: str) -> dict[str, Position]:
        """Return ``{symbol: Position}`` for a single client."""
        return {sym: p for (cid, sym), p in self._positions.items() if cid == client_id}

    def mark_symbol(self, symbol: str, mark_price: Decimal) -> None:
        for (_, sym), pos in self._positions.items():
            if sym == symbol and pos.quantity != 0:
                pos.mark_to_market(mark_price)


# ---------------------------------------------------------------------------
# Matching Engine
# ---------------------------------------------------------------------------


class MatchingEngine:
    """FIFO price-time priority matching engine.

    For each incoming order the engine:

    0. Rejects duplicate ``order_id`` submissions (raising
       :class:`DuplicateOrderError`) and any non-NEW order.
    1. Validates the order against instrument reference data (known symbol,
       tick size, lot size) and rejects unsupported order types (STOP/STOP_LIMIT)
       and time-in-force values (DAY/GTD).
    2. Runs the optional pre-trade risk check with the existing position or None.
    3. Matches against the opposite side of the book at the resting price.
    4. Handles the residual per time-in-force: GTC limits rest, IOC/MARKET
       residuals are cancelled (terminal), and FOK never partially fills.
    5. Publishes accepted / rejected / partial / fill / cancel events for both
       the incoming order and every resting order it touches.
    """

    def __init__(
        self,
        event_bus: EventBus,
        instruments: Mapping[str, Instrument] | None = None,
        risk_check: PreTradeRiskCheck | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._instruments: dict[str, Instrument] = dict(instruments) if instruments else {}
        self._risk_check = risk_check
        self._books: dict[str, OrderBook] = {}
        self._position_manager = PositionManager()
        self._trade_log: list[Trade] = []
        self._order_count = 0
        self._known_order_ids: set[str] = set()

    # -- Book management -------------------------------------------------

    def get_or_create_book(self, symbol: str) -> OrderBook:
        book = self._books.get(symbol)
        if book is None:
            book = OrderBook(symbol)
            self._books[symbol] = book
        return book

    def get_book(self, symbol: str) -> OrderBook | None:
        return self._books.get(symbol)

    @property
    def books(self) -> dict[str, OrderBook]:
        return dict(self._books)

    @property
    def instruments(self) -> dict[str, Instrument]:
        return dict(self._instruments)

    @property
    def position_manager(self) -> PositionManager:
        return self._position_manager

    @property
    def trade_log(self) -> list[Trade]:
        return list(self._trade_log)

    @property
    def order_count(self) -> int:
        return self._order_count

    def all_positions(self) -> list[Position]:
        return self._position_manager.all_positions()

    def client_positions(self, client_id: str) -> list[Position]:
        return self._position_manager.client_positions(client_id)

    # -- Boundary validation --------------------------------------------

    def _validate_boundary(self, order: Order) -> tuple[bool, str]:
        """Validate an order against reference data and supported types."""
        if order.order_type in (OrderType.STOP, OrderType.STOP_LIMIT):
            return (
                False,
                f"{order.order_type.value} orders are not supported: no "
                "stop-trigger engine is configured",
            )

        if order.time_in_force in (TimeInForce.DAY, TimeInForce.GTD):
            return (
                False,
                f"{order.time_in_force.value} time-in-force is not supported: no "
                "session-clock / expiry subsystem is configured",
            )

        if self._instruments:
            instrument = self._instruments.get(order.symbol)
            if instrument is None:
                return False, f"Unknown instrument: {order.symbol}"
            if not instrument.is_valid_quantity(order.quantity):
                return (
                    False,
                    f"Quantity {order.quantity} is not a multiple of lot size "
                    f"{instrument.lot_size}",
                )
            if order.price is not None and not instrument.is_valid_price(order.price):
                return (
                    False,
                    f"Price {order.price} is not a multiple of tick size {instrument.tick_size}",
                )
        return True, ""

    # -- Order submission ------------------------------------------------

    async def submit_order(self, order: Order) -> OrderSubmission:
        # Duplicate-id guard first: never mutate or re-emit for an order id the
        # engine already knows (this includes same-object resubmission of a
        # resting order).  Raised cleanly so the API can map it to HTTP 409.
        #
        # The id is reserved *synchronously* here — before the first await —
        # so two concurrent submissions of the same id cannot both pass the
        # guard.  The reservation is permanent: every attempted submission id
        # (including ones that go on to be rejected or fail the non-NEW check)
        # is known thereafter and can never be reused on this engine.
        if order.order_id in self._known_order_ids:
            raise DuplicateOrderError(order.order_id)
        self._known_order_ids.add(order.order_id)

        self._order_count += 1
        await self._publish_order_event(EventType.ORDER_SUBMITTED, order)

        # Only fresh (NEW) orders may enter the engine.
        if order.status is not OrderStatus.NEW:
            return await self._reject(
                order,
                f"cannot submit order in status {order.status.value}; only NEW "
                "orders may be submitted",
            )

        ok, reason = self._validate_boundary(order)
        if not ok:
            return await self._reject(order, reason)

        book = self.get_or_create_book(order.symbol)

        # Pre-trade risk check — pass the existing position (or None); never
        # create a zero position just to run the check.
        if self._risk_check is not None:
            pos = self._position_manager.peek_position(order.client_id, order.symbol)
            allowed, risk_reason = self._risk_check.can_execute(order, pos)
            if not allowed:
                if not isinstance(risk_reason, str):
                    raise TypeError("risk check reason must be a string")
                return await self._reject(order, risk_reason.strip() or "Risk check failed")

        # The order is now admitted to the engine.
        order.status = OrderStatus.ACCEPTED
        order.updated_at = utcnow()
        await self._publish_order_event(EventType.ORDER_ACCEPTED, order)

        # Fill-or-Kill is an accepted order that is killed (cancelled) without
        # any fills if it cannot be fully filled; liquidity stays untouched.
        if order.time_in_force is TimeInForce.FOK and not self._can_fill_fully(order, book):
            order.status = OrderStatus.CANCELLED
            order.updated_at = utcnow()
            await self._publish_order_event(
                EventType.ORDER_CANCELLED,
                order,
                {"reason": "FOK order could not be fully filled"},
            )
            return OrderSubmission(order=order, trades=[])

        fills = self._match(order, book)
        trades = [trade for trade, _ in fills]
        for trade, resting in fills:
            self._trade_log.append(trade)
            await self._publish_trade_event(trade, order)
            # Every resting order touched by the match is finalised too.
            await self._publish_resting_fill(resting)

        if trades:
            last_price = trades[-1].price
            self._position_manager.mark_symbol(order.symbol, last_price)

        await self._finalise(order, book, trades)
        return OrderSubmission(order=order, trades=trades)

    async def _finalise(self, order: Order, book: OrderBook, trades: list[Trade]) -> None:
        if order.is_fully_filled:
            order.status = OrderStatus.FILLED
            order.updated_at = utcnow()
            await self._publish_order_event(EventType.ORDER_FILLED, order)
            return

        # There is residual quantity — first surface any partial execution.
        if trades:
            order.status = OrderStatus.PARTIALLY_FILLED
            order.updated_at = utcnow()
            await self._publish_order_event(EventType.ORDER_PARTIALLY_FILLED, order)

        # Only GTC limit residuals rest; DAY/GTD are rejected at the boundary
        # because there is no session/expiry subsystem to retire them.
        rest_allowed = (
            order.order_type is OrderType.LIMIT and order.time_in_force is TimeInForce.GTC
        )
        if rest_allowed:
            # Residual joins the book and stays active (PARTIALLY_FILLED or,
            # if nothing traded, the already-published ACCEPTED state).
            book.add_order(order)
            return

        # MARKET / IOC (and any FOK residual) cancel the remainder — no market
        # order ever rests.  The order always ends in a terminal CANCELLED
        # state, even when it was partially filled first.
        order.status = OrderStatus.CANCELLED
        order.updated_at = utcnow()
        reason = (
            "IOC residual cancelled"
            if order.time_in_force is TimeInForce.IOC
            else "Market order residual cancelled (no liquidity)"
        )
        await self._publish_order_event(EventType.ORDER_CANCELLED, order, {"reason": reason})

    async def _reject(self, order: Order, reason: str) -> OrderSubmission:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("rejection reason must be a non-empty string")
        reason = reason.strip()
        order.status = OrderStatus.REJECTED
        order.updated_at = utcnow()
        await self._publish_order_event(EventType.ORDER_REJECTED, order, {"reason": reason})
        logger.info("Rejected order %s: %s", order.order_id, reason)
        return OrderSubmission(order=order, trades=[], rejection_reason=reason)

    # -- Matching logic --------------------------------------------------

    def _match(self, incoming: Order, book: OrderBook) -> list[tuple[Trade, Order]]:
        """Match ``incoming`` and return ``(trade, resting_order)`` pairs so the
        caller can finalise each touched resting order exactly once."""
        fills: list[tuple[Trade, Order]] = []

        while incoming.remaining_quantity > 0:
            if incoming.side is Side.BUY:
                resting = book.peek_best_ask_order()
            else:
                resting = book.peek_best_bid_order()
            if resting is None:
                break
            resting_price = resting.price
            if resting_price is None:
                raise RuntimeError("order book invariant violated: resting order has no price")

            # Limit orders only cross when the price is acceptable.
            if incoming.order_type is OrderType.LIMIT:
                incoming_price = incoming.price
                if incoming_price is None:
                    raise RuntimeError("order invariant violated: limit order has no price")
                if incoming.side is Side.BUY and incoming_price < resting_price:
                    break
                if incoming.side is Side.SELL and incoming_price > resting_price:
                    break

            fill_qty = min(incoming.remaining_quantity, resting.remaining_quantity)
            trade = self._execute_fill(incoming, resting, fill_qty, resting_price)
            fills.append((trade, resting))

            if resting.is_fully_filled:
                if incoming.side is Side.BUY:
                    book.pop_best_ask()
                else:
                    book.pop_best_bid()

        return fills

    def _execute_fill(
        self,
        incoming: Order,
        resting: Order,
        quantity: Decimal,
        price: Decimal,
    ) -> Trade:
        now = utcnow()

        incoming.average_fill_price = self._compute_avg_price(
            incoming.average_fill_price, incoming.filled_quantity, price, quantity
        )
        incoming.filled_quantity += quantity
        incoming.updated_at = now

        resting.average_fill_price = self._compute_avg_price(
            resting.average_fill_price, resting.filled_quantity, price, quantity
        )
        resting.filled_quantity += quantity
        resting.updated_at = now
        resting.status = (
            OrderStatus.FILLED if resting.is_fully_filled else OrderStatus.PARTIALLY_FILLED
        )

        if incoming.side is Side.BUY:
            buyer, seller = incoming, resting
        else:
            buyer, seller = resting, incoming

        trade = Trade(
            symbol=incoming.symbol,
            buy_order_id=buyer.order_id,
            sell_order_id=seller.order_id,
            price=price,
            quantity=quantity,
            buyer_client_id=buyer.client_id,
            seller_client_id=seller.client_id,
            aggressor_side=incoming.side,
            timestamp=now,
        )

        self._position_manager.apply_fill(
            buyer.client_id, incoming.symbol, Side.BUY, quantity, price
        )
        self._position_manager.apply_fill(
            seller.client_id, incoming.symbol, Side.SELL, quantity, price
        )

        logger.info(
            "Fill: %s %s qty=%s @ %s | buyer=%s seller=%s",
            incoming.symbol,
            incoming.side.value,
            quantity,
            price,
            buyer.client_id,
            seller.client_id,
        )
        return trade

    @staticmethod
    def _compute_avg_price(
        prev_avg: Decimal | None,
        prev_qty: Decimal,
        new_price: Decimal,
        new_qty: Decimal,
    ) -> Decimal:
        if prev_avg is None or prev_qty == 0:
            return new_price
        total_cost = prev_avg * prev_qty + new_price * new_qty
        return total_cost / (prev_qty + new_qty)

    def _can_fill_fully(self, order: Order, book: OrderBook) -> bool:
        """Return True if ``order`` can be fully filled against current liquidity
        without consuming it (used for FOK pre-checks)."""
        needed = order.remaining_quantity
        available = Decimal("0")
        is_limit = order.order_type is OrderType.LIMIT
        if order.side is Side.BUY:
            for level in book.ask_levels(depth=1_000_000):
                if is_limit and order.price is not None and level.price > order.price:
                    break
                available += level.total_quantity
                if available >= needed:
                    return True
        else:
            for level in book.bid_levels(depth=1_000_000):
                if is_limit and order.price is not None and level.price < order.price:
                    break
                available += level.total_quantity
                if available >= needed:
                    return True
        return available >= needed

    # -- Cancel -----------------------------------------------------------

    async def cancel_order(self, order_id: str, symbol: str | None = None) -> Order | None:
        books: list[OrderBook]
        if symbol is not None:
            book = self._books.get(symbol)
            books = [book] if book is not None else []
        else:
            books = list(self._books.values())

        for book in books:
            order = book.cancel_order(order_id)
            if order is not None:
                order.status = OrderStatus.CANCELLED
                order.updated_at = utcnow()
                await self._publish_order_event(
                    EventType.ORDER_CANCELLED, order, {"reason": "Client requested"}
                )
                return order
        return None

    # -- Event publishing -------------------------------------------------

    async def _publish_order_event(
        self,
        event_type: EventType,
        order: Order,
        extra: dict[str, object] | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "order_id": order.order_id,
            "client_id": order.client_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": str(order.quantity),
            "filled_quantity": str(order.filled_quantity),
            "status": order.status.value,
        }
        if extra:
            payload.update(extra)
        await self._event_bus.publish(
            DomainEvent(
                event_type=event_type,
                source="matching_engine",
                correlation_id=order.order_id,
                payload=payload,
            )
        )

    async def _publish_resting_fill(self, resting: Order) -> None:
        """Publish the lifecycle event for a resting order touched by a match —
        exactly once per fill, mirroring the status set in :meth:`_execute_fill`."""
        event_type = (
            EventType.ORDER_FILLED if resting.is_fully_filled else EventType.ORDER_PARTIALLY_FILLED
        )
        await self._publish_order_event(event_type, resting)

    async def _publish_trade_event(self, trade: Trade, order: Order) -> None:
        await self._event_bus.publish(
            DomainEvent(
                event_type=EventType.TRADE_EXECUTED,
                source="matching_engine",
                correlation_id=order.order_id,
                payload={
                    "trade_id": trade.trade_id,
                    "symbol": trade.symbol,
                    "price": str(trade.price),
                    "quantity": str(trade.quantity),
                    "buy_order_id": trade.buy_order_id,
                    "sell_order_id": trade.sell_order_id,
                    "aggressor_side": trade.aggressor_side.value,
                },
            )
        )
        await self._event_bus.publish(
            DomainEvent(
                event_type=EventType.POSITION_UPDATED,
                source="matching_engine",
                correlation_id=order.order_id,
                payload={
                    "symbol": trade.symbol,
                    "buyer_client_id": trade.buyer_client_id,
                    "seller_client_id": trade.seller_client_id,
                    "price": str(trade.price),
                    "quantity": str(trade.quantity),
                },
            )
        )


__all__ = [
    "DuplicateOrderError",
    "PreTradeRiskCheck",
    "OrderSubmission",
    "PositionManager",
    "MatchingEngine",
]

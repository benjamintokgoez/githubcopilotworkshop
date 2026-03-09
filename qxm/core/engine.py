"""FIFO price-time priority matching engine for the QXM exchange.

Supports limit, market, IOC, FOK, stop, and stop-limit order types.
All fills are published as ``DomainEvent`` instances through the
``EventBus``, enabling downstream consumers (risk, position manager,
strategy layer) to react asynchronously.

The engine is single-threaded per symbol — concurrency across symbols
is achieved by sharding order books and running one engine instance
per symbol group.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Protocol, Sequence, Tuple

from qxm.core.book import OrderBook
from qxm.core.events import DomainEvent, EventBus, EventType
from qxm.core.models import (
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
    Trade,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Risk check protocol (structural subtyping)
# ---------------------------------------------------------------------------

class PreTradeRiskCheck(Protocol):
    """Structural protocol for pre-trade risk validators.  Any object
    implementing ``can_execute`` is accepted without explicit inheritance."""

    def can_execute(self, order: Order, position: Optional[Position]) -> Tuple[bool, str]:
        ...


# ---------------------------------------------------------------------------
# Position manager — tracks per-client positions
# ---------------------------------------------------------------------------

class PositionManager:
    """In-memory position tracker.  Applies fills to running position
    state and computes unrealised P&L against the latest mid price."""

    def __init__(self) -> None:
        self._positions: Dict[Tuple[str, str], Position] = {}  # (client, symbol)

    def get_position(self, client_id: str, symbol: str) -> Position:
        key = (client_id, symbol)
        if key not in self._positions:
            self._positions[key] = Position(client_id=client_id, symbol=symbol)
        return self._positions[key]

    def apply_fill(
        self,
        client_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
    ) -> Position:
        pos = self.get_position(client_id, symbol)
        pos.apply_fill(side, quantity, price)
        return pos

    def all_positions(self) -> List[Position]:
        return list(self._positions.values())

    def client_positions(self, client_id: str) -> List[Position]:
        return [p for p in self._positions.values() if p.client_id == client_id]

    def update_unrealised_pnl(self, symbol: str, mid_price: Decimal) -> None:
        for key, pos in self._positions.items():
            if key[1] == symbol and pos.quantity != 0:
                pos.unrealised_pnl = (mid_price - pos.average_entry_price) * pos.quantity


# ---------------------------------------------------------------------------
# Matching Engine
# ---------------------------------------------------------------------------

class MatchingEngine:
    """FIFO price-time priority matching engine.

    For each incoming order the engine:

    1. Validates the order (pre-trade risk check, if configured).
    2. Attempts to match against the opposite side of the book.
    3. For any remaining unmatched quantity, rests the order on the book
       (for limit/GTC orders) or cancels the residual (IOC/FOK).
    4. Publishes fill, acceptance, or rejection events via the ``EventBus``.

    **BUG (Challenge 3):** Market orders are currently filled at the
    incoming order's limit price instead of the resting order's price.
    The correct behaviour is to fill at the *resting* order's price
    (the maker's price), which is the price already on the book.
    """

    def __init__(
        self,
        event_bus: EventBus,
        risk_check: Optional[PreTradeRiskCheck] = None,
    ) -> None:
        self._books: Dict[str, OrderBook] = {}
        self._event_bus = event_bus
        self._risk_check = risk_check
        self._position_manager = PositionManager()
        self._trade_log: List[Trade] = []
        self._order_count = 0

    # -- Book management -------------------------------------------------

    def get_or_create_book(self, symbol: str) -> OrderBook:
        if symbol not in self._books:
            self._books[symbol] = OrderBook(symbol)
        return self._books[symbol]

    def get_book(self, symbol: str) -> Optional[OrderBook]:
        return self._books.get(symbol)

    @property
    def books(self) -> Dict[str, OrderBook]:
        return dict(self._books)

    @property
    def position_manager(self) -> PositionManager:
        return self._position_manager

    @property
    def trade_log(self) -> List[Trade]:
        return list(self._trade_log)

    # -- Order submission ------------------------------------------------

    async def submit_order(self, order: Order) -> Order:
        self._order_count += 1
        book = self.get_or_create_book(order.symbol)

        # Pre-trade risk check
        if self._risk_check is not None:
            pos = self._position_manager.get_position(order.client_id, order.symbol)
            ok, reason = self._risk_check.can_execute(order, pos)
            if not ok:
                order.status = OrderStatus.REJECTED
                await self._publish_event(
                    EventType.ORDER_REJECTED,
                    order,
                    {"reason": reason},
                )
                return order

        order.status = OrderStatus.ACCEPTED
        await self._publish_event(EventType.ORDER_ACCEPTED, order)

        # Match
        trades = self._match(order, book)

        # Publish trade events
        for trade in trades:
            self._trade_log.append(trade)
            await self._publish_event(
                EventType.TRADE_EXECUTED,
                order,
                {
                    "trade_id": trade.trade_id,
                    "price": str(trade.price),
                    "quantity": str(trade.quantity),
                },
            )

        # Handle residual quantity
        if not order.is_fully_filled:
            if order.order_type in (OrderType.MARKET, OrderType.IOC):
                order.status = OrderStatus.CANCELLED
                await self._publish_event(
                    EventType.ORDER_CANCELLED,
                    order,
                    {"reason": "Residual cancelled (IOC/Market)"},
                )
            elif order.order_type == OrderType.FOK:
                # FOK: should have been all-or-nothing; handled in _match
                pass
            elif order.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT):
                book.add_order(order)
        elif order.is_fully_filled:
            order.status = OrderStatus.FILLED
            await self._publish_event(EventType.ORDER_FILLED, order)

        return order

    # -- Matching logic --------------------------------------------------

    def _match(self, incoming: Order, book: OrderBook) -> List[Trade]:
        trades: List[Trade] = []

        if incoming.order_type == OrderType.FOK:
            if not self._can_fill_fully(incoming, book):
                incoming.status = OrderStatus.CANCELLED
                return trades

        while incoming.remaining_quantity > 0:
            if incoming.side == Side.BUY:
                resting = book.peek_best_ask_order()
            else:
                resting = book.peek_best_bid_order()

            if resting is None:
                break

            # Price compatibility check
            if incoming.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT):
                if incoming.side == Side.BUY and incoming.price < resting.price:
                    break
                if incoming.side == Side.SELL and incoming.price > resting.price:
                    break

            # Determine fill quantity
            fill_qty = min(incoming.remaining_quantity, resting.remaining_quantity)

            # BUG (Challenge 3): Should use resting.price (maker's price)
            # but incorrectly uses incoming.price for market orders
            if incoming.order_type == OrderType.MARKET:
                fill_price = incoming.price if incoming.price else resting.price
            else:
                fill_price = resting.price

            # Execute fill
            trade = self._execute_fill(incoming, resting, fill_qty, fill_price)
            trades.append(trade)

            # Remove fully filled resting order from book
            if resting.is_fully_filled:
                if incoming.side == Side.BUY:
                    book.pop_best_ask()
                else:
                    book.pop_best_bid()

        return trades

    def _execute_fill(
        self,
        incoming: Order,
        resting: Order,
        quantity: Decimal,
        price: Decimal,
    ) -> Trade:
        # Update order states
        incoming.filled_quantity += quantity
        incoming.average_fill_price = self._compute_avg_price(
            incoming.average_fill_price,
            incoming.filled_quantity - quantity,
            price,
            quantity,
        )
        incoming.updated_at = datetime.utcnow()

        resting.filled_quantity += quantity
        resting.average_fill_price = self._compute_avg_price(
            resting.average_fill_price,
            resting.filled_quantity - quantity,
            price,
            quantity,
        )
        resting.updated_at = datetime.utcnow()

        # Determine buyer/seller
        if incoming.side == Side.BUY:
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
        )

        # Update positions
        self._position_manager.apply_fill(
            buyer.client_id, incoming.symbol, Side.BUY, quantity, price
        )
        self._position_manager.apply_fill(
            seller.client_id, incoming.symbol, Side.SELL, quantity, price
        )

        logger.info(
            "Fill: %s %s qty=%s @ %s | buyer=%s seller=%s",
            incoming.symbol,
            incoming.side,
            quantity,
            price,
            buyer.client_id,
            seller.client_id,
        )

        return trade

    @staticmethod
    def _compute_avg_price(
        prev_avg: Optional[Decimal],
        prev_qty: Decimal,
        new_price: Decimal,
        new_qty: Decimal,
    ) -> Decimal:
        if prev_avg is None or prev_qty == 0:
            return new_price
        total_cost = prev_avg * prev_qty + new_price * new_qty
        total_qty = prev_qty + new_qty
        return total_cost / total_qty

    def _can_fill_fully(self, order: Order, book: OrderBook) -> bool:
        """Check whether an FOK order can be fully filled without actually
        consuming liquidity."""
        available = Decimal("0")
        if order.side == Side.BUY:
            for level in book.ask_levels(depth=100):
                if order.price and level.price > order.price:
                    break
                available += level.total_quantity
                if available >= order.quantity:
                    return True
        else:
            for level in book.bid_levels(depth=100):
                if order.price and level.price < order.price:
                    break
                available += level.total_quantity
                if available >= order.quantity:
                    return True
        return available >= order.quantity

    # -- Cancel -----------------------------------------------------------

    async def cancel_order(self, symbol: str, order_id: str) -> Optional[Order]:
        book = self._books.get(symbol)
        if book is None:
            return None
        order = book.cancel_order(order_id)
        if order:
            order.status = OrderStatus.CANCELLED
            await self._publish_event(
                EventType.ORDER_CANCELLED, order, {"reason": "Client requested"}
            )
        return order

    # -- Event publishing -------------------------------------------------

    async def _publish_event(
        self,
        event_type: EventType,
        order: Order,
        extra: Optional[Dict] = None,
    ) -> None:
        payload = {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": str(order.quantity),
            "filled_quantity": str(order.filled_quantity),
            "status": order.status,
        }
        if extra:
            payload.update(extra)

        event = DomainEvent(
            event_type=event_type,
            source="matching_engine",
            correlation_id=order.order_id,
            payload=payload,
        )
        await self._event_bus.publish(event)

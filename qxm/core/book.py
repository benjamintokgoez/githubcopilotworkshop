"""Limit order book (LOB) implementation using sorted containers for
O(log n) insert/remove and O(1) best-bid/best-ask retrieval.

Each price level maintains a FIFO queue of orders at that price.  Bid levels
are sorted descending (best bid = highest price first) by storing *negated*
keys in the ``SortedDict``; ask levels use natural ascending order (best ask =
lowest price first).
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from decimal import Decimal

from sortedcontainers import SortedDict

from qxm.core.models import Order, Side

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Price Level
# ---------------------------------------------------------------------------


class PriceLevel:
    """A single price level containing a FIFO queue of orders at one price.

    ``total_quantity`` is computed from the live ``remaining_quantity`` of the
    resting orders, so it stays accurate even after a resting order is
    partially filled in place.
    """

    __slots__ = ("price", "orders")

    def __init__(self, price: Decimal) -> None:
        self.price = price
        self.orders: deque[Order] = deque()

    def add(self, order: Order) -> None:
        self.orders.append(order)

    def remove_front(self) -> Order | None:
        if not self.orders:
            return None
        return self.orders.popleft()

    def peek_front(self) -> Order | None:
        return self.orders[0] if self.orders else None

    def remove_order(self, order_id: str) -> Order | None:
        for order in self.orders:
            if order.order_id == order_id:
                self.orders.remove(order)
                return order
        return None

    @property
    def total_quantity(self) -> Decimal:
        return sum((o.remaining_quantity for o in self.orders), Decimal("0"))

    @property
    def order_count(self) -> int:
        return len(self.orders)

    @property
    def is_empty(self) -> bool:
        return len(self.orders) == 0

    def __repr__(self) -> str:
        return (
            f"PriceLevel(price={self.price}, qty={self.total_quantity}, orders={len(self.orders)})"
        )


# ---------------------------------------------------------------------------
# Order Book
# ---------------------------------------------------------------------------


class OrderBook:
    """Two-sided limit order book for a single instrument.

    Thread-safety is provided via a reentrant lock; for maximum throughput the
    matching engine serialises access per symbol.
    """

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._bids: SortedDict[Decimal, PriceLevel] = SortedDict()  # key = -price -> PriceLevel
        self._asks: SortedDict[Decimal, PriceLevel] = SortedDict()  # key = +price -> PriceLevel
        self._order_index: dict[str, tuple[Side, Decimal]] = {}
        self._lock = threading.RLock()

    def _side_book(self, side: Side) -> SortedDict[Decimal, PriceLevel]:
        return self._bids if side is Side.BUY else self._asks

    @staticmethod
    def _key(side: Side, price: Decimal) -> Decimal:
        return -price if side is Side.BUY else price

    # -- Insertion ------------------------------------------------------

    def add_order(self, order: Order) -> None:
        """Rest a limit order on the book.  ``order.price`` must be set."""
        if order.price is None:
            raise ValueError("Cannot rest an order without a price")
        with self._lock:
            book = self._side_book(order.side)
            key = self._key(order.side, order.price)
            if key not in book:
                book[key] = PriceLevel(order.price)
            book[key].add(order)
            self._order_index[order.order_id] = (order.side, order.price)

    # -- Cancellation ---------------------------------------------------

    def cancel_order(self, order_id: str) -> Order | None:
        with self._lock:
            entry = self._order_index.pop(order_id, None)
            if entry is None:
                return None
            side, price = entry
            book = self._side_book(side)
            key = self._key(side, price)
            level: PriceLevel | None = book.get(key)
            if level is None:
                return None
            order = level.remove_order(order_id)
            if level.is_empty:
                del book[key]
            return order

    def contains(self, order_id: str) -> bool:
        with self._lock:
            return order_id in self._order_index

    # -- Best price queries ---------------------------------------------

    @property
    def best_bid(self) -> Decimal | None:
        with self._lock:
            if not self._bids:
                return None
            return self._bids.peekitem(0)[1].price

    @property
    def best_ask(self) -> Decimal | None:
        with self._lock:
            if not self._asks:
                return None
            return self._asks.peekitem(0)[1].price

    @property
    def spread(self) -> Decimal | None:
        bb, ba = self.best_bid, self.best_ask
        if bb is not None and ba is not None:
            return ba - bb
        return None

    @property
    def midpoint(self) -> Decimal | None:
        bb, ba = self.best_bid, self.best_ask
        if bb is not None and ba is not None:
            return (bb + ba) / 2
        return None

    # -- Level iteration ------------------------------------------------

    def bid_levels(self, depth: int = 10) -> list[PriceLevel]:
        with self._lock:
            levels: list[PriceLevel] = []
            for _, level in self._bids.items():
                levels.append(level)
                if len(levels) >= depth:
                    break
            return levels

    def ask_levels(self, depth: int = 10) -> list[PriceLevel]:
        with self._lock:
            levels: list[PriceLevel] = []
            for _, level in self._asks.items():
                levels.append(level)
                if len(levels) >= depth:
                    break
            return levels

    # -- Consume liquidity (called by matching engine) ------------------

    def pop_best_bid(self) -> Order | None:
        """Remove and return the highest-priority resting bid order."""
        with self._lock:
            return self._pop_best(self._bids)

    def pop_best_ask(self) -> Order | None:
        """Remove and return the highest-priority resting ask order."""
        with self._lock:
            return self._pop_best(self._asks)

    def _pop_best(self, book: SortedDict[Decimal, PriceLevel]) -> Order | None:
        if not book:
            return None
        key, level = book.peekitem(0)
        order = level.remove_front()
        if order is not None:
            self._order_index.pop(order.order_id, None)
        if level.is_empty:
            del book[key]
        return order

    def peek_best_bid_order(self) -> Order | None:
        with self._lock:
            if not self._bids:
                return None
            return self._bids.peekitem(0)[1].peek_front()

    def peek_best_ask_order(self) -> Order | None:
        with self._lock:
            if not self._asks:
                return None
            return self._asks.peekitem(0)[1].peek_front()

    # -- Depth snapshot --------------------------------------------------

    def depth_snapshot(self, levels: int = 20) -> dict[str, list[dict[str, object]]]:
        with self._lock:
            bids = [
                {
                    "price": str(lvl.price),
                    "quantity": str(lvl.total_quantity),
                    "orders": lvl.order_count,
                }
                for lvl in self.bid_levels(levels)
            ]
            asks = [
                {
                    "price": str(lvl.price),
                    "quantity": str(lvl.total_quantity),
                    "orders": lvl.order_count,
                }
                for lvl in self.ask_levels(levels)
            ]
        return {"bids": bids, "asks": asks}

    # -- Stats -----------------------------------------------------------

    @property
    def bid_depth(self) -> int:
        return len(self._bids)

    @property
    def ask_depth(self) -> int:
        return len(self._asks)

    @property
    def total_orders(self) -> int:
        return len(self._order_index)

    def __repr__(self) -> str:
        return (
            f"OrderBook({self.symbol}: "
            f"bids={self.bid_depth} levels, "
            f"asks={self.ask_depth} levels, "
            f"orders={self.total_orders})"
        )


__all__ = ["PriceLevel", "OrderBook"]

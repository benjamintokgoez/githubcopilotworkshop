"""Limit order book (LOB) implementation using sorted containers for
O(log n) insert/remove and O(1) best-bid/best-ask retrieval.

Each price level maintains a FIFO queue of orders at that price.
Bid levels are sorted descending (best bid = highest price first),
ask levels are sorted ascending (best ask = lowest price first).
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict, deque
from decimal import Decimal
from typing import Deque, Dict, Iterator, List, Optional, Tuple

from sortedcontainers import SortedDict

from qxm.core.models import Order, Side

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Price Level
# ---------------------------------------------------------------------------

class PriceLevel:
    """A single price level in the order book containing a FIFO queue of
    orders at an identical price.

    Attributes:
        price:  The price represented by this level.
        orders: FIFO queue of orders resting at this price.
    """

    __slots__ = ("price", "orders", "_total_quantity")

    def __init__(self, price: Decimal) -> None:
        self.price = price
        self.orders: Deque[Order] = deque()
        self._total_quantity = Decimal("0")

    def add(self, order: Order) -> None:
        self.orders.append(order)
        self._total_quantity += order.remaining_quantity

    def remove_front(self) -> Optional[Order]:
        if not self.orders:
            return None
        order = self.orders.popleft()
        self._total_quantity -= order.remaining_quantity
        return order

    def remove_order(self, order_id: str) -> Optional[Order]:
        for i, order in enumerate(self.orders):
            if order.order_id == order_id:
                self.orders.remove(order)
                self._total_quantity -= order.remaining_quantity
                return order
        return None

    @property
    def total_quantity(self) -> Decimal:
        return self._total_quantity

    @property
    def order_count(self) -> int:
        return len(self.orders)

    @property
    def is_empty(self) -> bool:
        return len(self.orders) == 0

    def __repr__(self) -> str:
        return (
            f"PriceLevel(price={self.price}, "
            f"qty={self._total_quantity}, "
            f"orders={len(self.orders)})"
        )


# ---------------------------------------------------------------------------
# Order Book
# ---------------------------------------------------------------------------

class OrderBook:
    """Two-sided limit order book for a single instrument.

    Internally uses ``SortedDict`` from the ``sortedcontainers`` library:
    - **Bids** are stored with *negated* keys so that the highest bid
      appears first (index 0) in the sorted structure.
    - **Asks** use natural ordering — the lowest ask appears first.

    Thread-safety is achieved via a reentrant lock; however, for maximum
    throughput the matching engine should serialise access per symbol.
    """

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._bids: SortedDict = SortedDict()   # key = -price
        self._asks: SortedDict = SortedDict()   # key = +price
        self._order_index: Dict[str, Tuple[Side, Decimal]] = {}
        self._lock = threading.RLock()

    # -- Insertion ------------------------------------------------------

    def add_order(self, order: Order) -> None:
        with self._lock:
            if order.side == Side.BUY:
                key = -order.price
                book = self._bids
            else:
                key = order.price
                book = self._asks

            if key not in book:
                book[key] = PriceLevel(order.price)
            book[key].add(order)
            self._order_index[order.order_id] = (order.side, order.price)

    # -- Cancellation ---------------------------------------------------

    def cancel_order(self, order_id: str) -> Optional[Order]:
        with self._lock:
            if order_id not in self._order_index:
                return None
            side, price = self._order_index.pop(order_id)
            if side == Side.BUY:
                key = -price
                book = self._bids
            else:
                key = price
                book = self._asks

            level: Optional[PriceLevel] = book.get(key)
            if level is None:
                return None
            order = level.remove_order(order_id)
            if level.is_empty:
                del book[key]
            return order

    # -- Best price queries ---------------------------------------------

    @property
    def best_bid(self) -> Optional[Decimal]:
        with self._lock:
            if not self._bids:
                return None
            return self._bids.peekitem(0)[1].price

    @property
    def best_ask(self) -> Optional[Decimal]:
        with self._lock:
            if not self._asks:
                return None
            return self._asks.peekitem(0)[1].price

    @property
    def spread(self) -> Optional[Decimal]:
        bb, ba = self.best_bid, self.best_ask
        if bb is not None and ba is not None:
            return ba - bb
        return None

    @property
    def midpoint(self) -> Optional[Decimal]:
        bb, ba = self.best_bid, self.best_ask
        if bb is not None and ba is not None:
            return (bb + ba) / 2
        return None

    # -- Level iteration ------------------------------------------------

    def bid_levels(self, depth: int = 10) -> List[PriceLevel]:
        with self._lock:
            levels = []
            for _, level in self._bids.items():
                levels.append(level)
                if len(levels) >= depth:
                    break
            return levels

    def ask_levels(self, depth: int = 10) -> List[PriceLevel]:
        with self._lock:
            levels = []
            for _, level in self._asks.items():
                levels.append(level)
                if len(levels) >= depth:
                    break
            return levels

    # -- Consume liquidity (called by matching engine) ------------------

    def pop_best_bid(self) -> Optional[Order]:
        """Remove and return the highest-priority bid order."""
        with self._lock:
            if not self._bids:
                return None
            key, level = self._bids.peekitem(0)
            order = level.remove_front()
            if order:
                self._order_index.pop(order.order_id, None)
            if level.is_empty:
                del self._bids[key]
            return order

    def pop_best_ask(self) -> Optional[Order]:
        """Remove and return the highest-priority ask order."""
        with self._lock:
            if not self._asks:
                return None
            key, level = self._asks.peekitem(0)
            order = level.remove_front()
            if order:
                self._order_index.pop(order.order_id, None)
            if level.is_empty:
                del self._asks[key]
            return order

    def peek_best_bid_order(self) -> Optional[Order]:
        with self._lock:
            if not self._bids:
                return None
            _, level = self._bids.peekitem(0)
            return level.orders[0] if level.orders else None

    def peek_best_ask_order(self) -> Optional[Order]:
        with self._lock:
            if not self._asks:
                return None
            _, level = self._asks.peekitem(0)
            return level.orders[0] if level.orders else None

    # -- Depth snapshot --------------------------------------------------

    def depth_snapshot(self, levels: int = 20) -> Dict[str, List[Dict]]:
        with self._lock:
            bids = [
                {"price": str(lvl.price), "quantity": str(lvl.total_quantity), "orders": lvl.order_count}
                for lvl in self.bid_levels(levels)
            ]
            asks = [
                {"price": str(lvl.price), "quantity": str(lvl.total_quantity), "orders": lvl.order_count}
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

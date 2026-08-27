"""Dispatch queue implementation using sorted containers for O(log n)
insert/remove and O(1) best-request/best-offer retrieval.

Each rate level maintains a FIFO queue of work orders at that rate. Request
levels are sorted descending (best request = highest acceptable rate first)
by storing *negated* keys in the ``SortedDict``; offer levels use natural
ascending order (best offer = lowest hourly rate first).
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from decimal import Decimal

from sortedcontainers import SortedDict

from mittelwerk.core.models import DispatchSide, WorkOrder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate Level
# ---------------------------------------------------------------------------


class RateLevel:
    """A single rate level containing a FIFO queue of work orders at one rate.

    ``total_hours`` is computed from the live ``remaining_hours`` of the
    resting work orders, so it stays accurate even after a resting work order
    is partially assigned in place.
    """

    __slots__ = ("rate", "work_orders")

    def __init__(self, rate: Decimal) -> None:
        self.rate = rate
        self.work_orders: deque[WorkOrder] = deque()

    def add(self, work_order: WorkOrder) -> None:
        self.work_orders.append(work_order)

    def remove_front(self) -> WorkOrder | None:
        if not self.work_orders:
            return None
        return self.work_orders.popleft()

    def peek_front(self) -> WorkOrder | None:
        return self.work_orders[0] if self.work_orders else None

    def remove_work_order(self, work_order_id: str) -> WorkOrder | None:
        for work_order in self.work_orders:
            if work_order.work_order_id == work_order_id:
                self.work_orders.remove(work_order)
                return work_order
        return None

    @property
    def total_hours(self) -> Decimal:
        return sum((o.remaining_hours for o in self.work_orders), Decimal("0"))

    @property
    def work_order_count(self) -> int:
        return len(self.work_orders)

    @property
    def is_empty(self) -> bool:
        return len(self.work_orders) == 0

    def __repr__(self) -> str:
        return (
            f"RateLevel(rate={self.rate}, hours={self.total_hours}, "
            f"work_orders={len(self.work_orders)})"
        )


# ---------------------------------------------------------------------------
# Dispatch Queue
# ---------------------------------------------------------------------------


class DispatchQueue:
    """Two-sided dispatch queue for a single asset.

    Thread-safety is provided via a reentrant lock; for maximum throughput the
    dispatch engine serialises access per asset.
    """

    def __init__(self, asset_id: str) -> None:
        self.asset_id = asset_id
        self._requests: SortedDict[Decimal, RateLevel] = SortedDict()  # key = -rate
        self._offers: SortedDict[Decimal, RateLevel] = SortedDict()  # key = +rate
        self._work_order_index: dict[str, tuple[DispatchSide, Decimal]] = {}
        self._lock = threading.RLock()

    def _side_queue(self, side: DispatchSide) -> SortedDict[Decimal, RateLevel]:
        return self._requests if side is DispatchSide.REQUEST else self._offers

    @staticmethod
    def _key(side: DispatchSide, rate: Decimal) -> Decimal:
        return -rate if side is DispatchSide.REQUEST else rate

    # -- Insertion ------------------------------------------------------

    def add_work_order(self, work_order: WorkOrder) -> None:
        """Rest a rate-capped work order on the queue. ``work_order.max_hourly_rate``
        must be set."""
        if work_order.max_hourly_rate is None:
            raise ValueError("Cannot rest a work order without a rate")
        with self._lock:
            queue = self._side_queue(work_order.side)
            key = self._key(work_order.side, work_order.max_hourly_rate)
            if key not in queue:
                queue[key] = RateLevel(work_order.max_hourly_rate)
            queue[key].add(work_order)
            self._work_order_index[work_order.work_order_id] = (
                work_order.side,
                work_order.max_hourly_rate,
            )

    # -- Cancellation ---------------------------------------------------

    def cancel_work_order(self, work_order_id: str) -> WorkOrder | None:
        with self._lock:
            entry = self._work_order_index.pop(work_order_id, None)
            if entry is None:
                return None
            side, rate = entry
            queue = self._side_queue(side)
            key = self._key(side, rate)
            level: RateLevel | None = queue.get(key)
            if level is None:
                return None
            work_order = level.remove_work_order(work_order_id)
            if level.is_empty:
                del queue[key]
            return work_order

    def contains(self, work_order_id: str) -> bool:
        with self._lock:
            return work_order_id in self._work_order_index

    # -- Best rate queries ---------------------------------------------

    @property
    def best_request_rate(self) -> Decimal | None:
        with self._lock:
            if not self._requests:
                return None
            return self._requests.peekitem(0)[1].rate

    @property
    def best_offer_rate(self) -> Decimal | None:
        with self._lock:
            if not self._offers:
                return None
            return self._offers.peekitem(0)[1].rate

    @property
    def rate_spread(self) -> Decimal | None:
        br, bo = self.best_request_rate, self.best_offer_rate
        if br is not None and bo is not None:
            return bo - br
        return None

    @property
    def representative_rate(self) -> Decimal | None:
        br, bo = self.best_request_rate, self.best_offer_rate
        if br is not None and bo is not None:
            return (br + bo) / 2
        return None

    # -- Level iteration ------------------------------------------------

    def request_levels(self, depth: int = 10) -> list[RateLevel]:
        with self._lock:
            levels: list[RateLevel] = []
            for _, level in self._requests.items():
                levels.append(level)
                if len(levels) >= depth:
                    break
            return levels

    def offer_levels(self, depth: int = 10) -> list[RateLevel]:
        with self._lock:
            levels: list[RateLevel] = []
            for _, level in self._offers.items():
                levels.append(level)
                if len(levels) >= depth:
                    break
            return levels

    # -- Consume liquidity (called by dispatch engine) ------------------

    def pop_best_request(self) -> WorkOrder | None:
        """Remove and return the highest-priority resting request work order."""
        with self._lock:
            return self._pop_best(self._requests)

    def pop_best_offer(self) -> WorkOrder | None:
        """Remove and return the highest-priority resting offer work order."""
        with self._lock:
            return self._pop_best(self._offers)

    def _pop_best(self, queue: SortedDict[Decimal, RateLevel]) -> WorkOrder | None:
        if not queue:
            return None
        key, level = queue.peekitem(0)
        work_order = level.remove_front()
        if work_order is not None:
            self._work_order_index.pop(work_order.work_order_id, None)
        if level.is_empty:
            del queue[key]
        return work_order

    def peek_best_request_order(self) -> WorkOrder | None:
        with self._lock:
            if not self._requests:
                return None
            return self._requests.peekitem(0)[1].peek_front()

    def peek_best_offer_order(self) -> WorkOrder | None:
        with self._lock:
            if not self._offers:
                return None
            return self._offers.peekitem(0)[1].peek_front()

    # -- Depth snapshot --------------------------------------------------

    def depth_snapshot(self, levels: int = 20) -> dict[str, list[dict[str, object]]]:
        with self._lock:
            requests = [
                {
                    "rate": str(lvl.rate),
                    "hours": str(lvl.total_hours),
                    "work_orders": lvl.work_order_count,
                }
                for lvl in self.request_levels(levels)
            ]
            offers = [
                {
                    "rate": str(lvl.rate),
                    "hours": str(lvl.total_hours),
                    "work_orders": lvl.work_order_count,
                }
                for lvl in self.offer_levels(levels)
            ]
        return {"requests": requests, "offers": offers}

    # -- Stats -----------------------------------------------------------

    @property
    def request_depth(self) -> int:
        return len(self._requests)

    @property
    def offer_depth(self) -> int:
        return len(self._offers)

    @property
    def total_work_orders(self) -> int:
        return len(self._work_order_index)

    def __repr__(self) -> str:
        return (
            f"DispatchQueue({self.asset_id}: "
            f"requests={self.request_depth} levels, "
            f"offers={self.offer_depth} levels, "
            f"work_orders={self.total_work_orders})"
        )


__all__ = ["RateLevel", "DispatchQueue"]

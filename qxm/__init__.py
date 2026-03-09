"""QuantCore (qxm) — Quantitative eXchange Module.

A high-performance order matching engine, risk analytics platform,
and strategy framework for algorithmic trading.

.. note::
    BUG (Challenge 2 — Debugging): This file contains TWO planted bugs:
    1. Circular import: imports ``qxm.data.handler`` which doesn't exist
       (was renamed to ``qxm.data.feed``).
    2. The circular import also triggers an ImportError that masks the
       real issue.
"""

from qxm.core import (
    DomainEvent,
    EventBus,
    EventLog,
    EventType,
    Instrument,
    MatchingEngine,
    Order,
    OrderBook,
    OrderStatus,
    OrderType,
    Position,
    PositionManager,
    Side,
    Tick,
    Trade,
)

# ──────────────────────────────────────────────────────────────────
# BUG (Challenge 2 — Debugging): Module was renamed from
# ``qxm.data.handler`` to ``qxm.data.feed``.  This import will
# raise ImportError.
# ──────────────────────────────────────────────────────────────────
from qxm.data.handler import MarketDataFeed  # noqa: F401

__version__ = "0.4.0"
__all__ = [
    "DomainEvent",
    "EventBus",
    "EventLog",
    "EventType",
    "Instrument",
    "MarketDataFeed",
    "MatchingEngine",
    "Order",
    "OrderBook",
    "OrderStatus",
    "OrderType",
    "Position",
    "PositionManager",
    "Side",
    "Tick",
    "Trade",
]

"""QuantCore public package interface.

The top-level package exposes the core trading primitives without importing
the optional API or MCP integrations. Market data is loaded on first access so
``import qxm`` remains suitable for lightweight clients.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qxm.core import (
    DomainEvent,
    EventBus,
    EventLog,
    EventType,
    Instrument,
    InstrumentType,
    MatchingEngine,
    OptionType,
    Order,
    OrderBook,
    OrderStatus,
    OrderSubmission,
    OrderType,
    PortfolioSnapshot,
    Position,
    PositionManager,
    PreTradeRiskCheck,
    PriceLevel,
    RiskMetrics,
    Side,
    Tick,
    TimeInForce,
    Trade,
    utcnow,
)

if TYPE_CHECKING:
    from qxm.data.feed import MarketDataFeed

__version__ = "0.5.0"

__all__ = [
    "DomainEvent",
    "EventBus",
    "EventLog",
    "EventType",
    "Instrument",
    "InstrumentType",
    "MarketDataFeed",
    "MatchingEngine",
    "OptionType",
    "Order",
    "OrderBook",
    "OrderStatus",
    "OrderSubmission",
    "OrderType",
    "PortfolioSnapshot",
    "Position",
    "PositionManager",
    "PreTradeRiskCheck",
    "PriceLevel",
    "RiskMetrics",
    "Side",
    "Tick",
    "TimeInForce",
    "Trade",
    "utcnow",
]


def __getattr__(name: str) -> Any:
    """Load optional public objects only when callers request them."""
    if name == "MarketDataFeed":
        from qxm.data.feed import MarketDataFeed

        globals()[name] = MarketDataFeed
        return MarketDataFeed
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return the stable public package namespace."""
    return sorted(set(globals()) | set(__all__))

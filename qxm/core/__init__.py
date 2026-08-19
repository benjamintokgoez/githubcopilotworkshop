"""QXM core — order matching, book management, domain models, and event
sourcing primitives."""

from qxm.core.book import OrderBook, PriceLevel
from qxm.core.engine import (
    DuplicateOrderError,
    MatchingEngine,
    OrderSubmission,
    PositionManager,
    PreTradeRiskCheck,
)
from qxm.core.events import DomainEvent, EventBus, EventLog, EventType
from qxm.core.models import (
    Instrument,
    InstrumentType,
    OptionType,
    Order,
    OrderStatus,
    OrderType,
    PortfolioSnapshot,
    Position,
    RiskMetrics,
    Side,
    Tick,
    TimeInForce,
    Trade,
    ensure_utc,
    utcnow,
)

__all__ = [
    "DomainEvent",
    "DuplicateOrderError",
    "EventBus",
    "EventLog",
    "EventType",
    "Instrument",
    "InstrumentType",
    "MatchingEngine",
    "OptionType",
    "Order",
    "OrderBook",
    "OrderStatus",
    "OrderSubmission",
    "OrderType",
    "Position",
    "PositionManager",
    "PortfolioSnapshot",
    "PreTradeRiskCheck",
    "PriceLevel",
    "RiskMetrics",
    "Side",
    "Tick",
    "TimeInForce",
    "Trade",
    "ensure_utc",
    "utcnow",
]

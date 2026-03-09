"""Strategy framework — metaclass-based auto-registration, abstract base,
signal generation, and lifecycle management for algorithmic strategies.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional, Type

from qxm.core.models import Instrument, Order, OrderType, Side, Tick, TimeInForce

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal types
# ---------------------------------------------------------------------------

class SignalStrength(Enum):
    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class Signal:
    """A trading signal produced by a strategy."""

    instrument: Instrument
    strength: SignalStrength
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_actionable(self) -> bool:
        return self.strength != SignalStrength.NEUTRAL and self.confidence >= 0.5


# ---------------------------------------------------------------------------
# Strategy metaclass — auto-registration
# ---------------------------------------------------------------------------

class StrategyMeta(abc.ABCMeta):
    """Metaclass that automatically registers strategy subclasses.

    Every concrete (non-abstract) subclass of :class:`BaseStrategy` is
    stored in a global registry keyed by its ``strategy_name`` class
    variable (falling back to the class name).

    This allows dynamic strategy discovery at runtime — e.g.::

        strat_cls = StrategyMeta.get("MomentumBreakout")
        strat = strat_cls(instruments=[...])
    """

    _registry: Dict[str, Type["BaseStrategy"]] = {}

    def __new__(
        mcs,
        name: str,
        bases: tuple,
        namespace: dict,
        **kwargs: Any,
    ) -> StrategyMeta:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        # Only register concrete subclasses (skip the abstract base itself)
        if not getattr(cls, "__abstractmethods__", frozenset()):
            key = getattr(cls, "strategy_name", name)
            if key in mcs._registry:
                logger.warning(
                    "Strategy name %r already registered — overwriting with %s",
                    key,
                    name,
                )
            mcs._registry[key] = cls  # type: ignore[assignment]
            logger.debug("Registered strategy: %s", key)
        return cls  # type: ignore[return-value]

    @classmethod
    def get(mcs, name: str) -> Type["BaseStrategy"]:
        """Retrieve a strategy class by name."""
        try:
            return mcs._registry[name]
        except KeyError:
            raise KeyError(
                f"Unknown strategy {name!r}. "
                f"Available: {list(mcs._registry)}"
            )

    @classmethod
    def list_strategies(mcs) -> List[str]:
        return list(mcs._registry.keys())


# ---------------------------------------------------------------------------
# Abstract base strategy
# ---------------------------------------------------------------------------

class BaseStrategy(metaclass=StrategyMeta):
    """Abstract base for all trading strategies.

    Subclasses must implement:
    - ``on_tick`` — process incoming market data.
    - ``generate_signals`` — produce a list of :class:`Signal` objects.

    Optionally override:
    - ``on_fill`` — react to order fills.
    - ``on_start`` / ``on_stop`` — lifecycle hooks.

    Attributes
    ----------
    strategy_name : ClassVar[str]
        Human-readable name used for registry lookup.
    version : ClassVar[str]
        Strategy version for audit purposes.
    """

    strategy_name: ClassVar[str] = "BaseStrategy"
    version: ClassVar[str] = "0.0.0"

    def __init__(
        self,
        instruments: List[Instrument],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.instruments = {inst.symbol: inst for inst in instruments}
        self.parameters = parameters or {}
        self._tick_buffer: Dict[str, List[Tick]] = {
            inst.symbol: [] for inst in instruments
        }
        self._signals: List[Signal] = []
        self._is_running: bool = False
        self._position_exposure: Dict[str, float] = {}

    # -- lifecycle -----------------------------------------------------------

    def on_start(self) -> None:
        """Called when the strategy begins running."""
        logger.info("%s v%s started", self.strategy_name, self.version)
        self._is_running = True

    def on_stop(self) -> None:
        """Called when the strategy is halted."""
        logger.info("%s stopped", self.strategy_name)
        self._is_running = False

    # -- abstract methods ----------------------------------------------------

    @abc.abstractmethod
    def on_tick(self, tick: Tick) -> None:
        """Process a single market-data tick."""
        ...

    @abc.abstractmethod
    def generate_signals(self) -> List[Signal]:
        """Produce trading signals based on buffered data."""
        ...

    # -- optional hooks ------------------------------------------------------

    def on_fill(self, order: Order, fill_price: float, fill_qty: int) -> None:
        """React to an order fill (default: update exposure tracking)."""
        sign = 1 if order.side == Side.BUY else -1
        current = self._position_exposure.get(order.symbol, 0.0)
        self._position_exposure[order.symbol] = current + sign * fill_qty * fill_price

    # -- helpers -------------------------------------------------------------

    def _buffer_tick(self, tick: Tick, max_buffer: int = 500) -> None:
        """Add a tick to the per-symbol buffer, evicting oldest if full."""
        buf = self._tick_buffer.get(tick.symbol)
        if buf is None:
            return
        buf.append(tick)
        if len(buf) > max_buffer:
            buf.pop(0)

    def create_order(
        self,
        symbol: str,
        side: Side,
        quantity: int,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        time_in_force: TimeInForce = TimeInForce.GTC,
        client_id: str = "strategy",
    ) -> Order:
        """Convenience factory for creating orders."""
        return Order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            client_id=client_id,
            time_in_force=time_in_force,
        )

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name={self.strategy_name!r} "
            f"v={self.version} instruments={list(self.instruments)}>"
        )

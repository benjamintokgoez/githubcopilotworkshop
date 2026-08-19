"""Strategy framework — metaclass-based auto-registration, abstract base,
signal generation, and lifecycle management for algorithmic strategies.
"""

from __future__ import annotations

import abc
import inspect
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar

from qxm.core.models import Instrument, Order, OrderType, Side, Tick, TimeInForce

logger = logging.getLogger(__name__)


def _require_int_parameter(
    parameters: dict[str, Any],
    name: str,
    *,
    minimum: int,
) -> int:
    """Return a strict integer strategy parameter at or above ``minimum``."""
    value = parameters[name]
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


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
    target_price: float | None = None
    stop_loss: float | None = None
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("signal timestamp must include an explicit timezone offset")
        self.timestamp = self.timestamp.astimezone(UTC)
        self.metadata = dict(self.metadata)
        try:
            json.dumps(self.metadata, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must contain only JSON-compatible values") from exc

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

    _registry: dict[str, type[BaseStrategy]] = {}

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> StrategyMeta:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        if bases and not inspect.isabstract(cls):
            # ``BaseStrategy`` is defined further down in this module and is
            # the only class using this metaclass; this check also gives
            # mypy a precise ``type[BaseStrategy]`` narrowing for the
            # registry assignment below instead of an ``Any``/unchecked cast.
            if not issubclass(cls, BaseStrategy):
                raise TypeError(f"{name} must subclass BaseStrategy to use StrategyMeta")
            key = namespace.get("strategy_name", name)
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"{name}.strategy_name must be a non-empty string")
            existing = mcs._registry.get(key)
            if existing is not None and existing is not cls:
                raise ValueError(
                    f"Strategy name {key!r} is already registered by {existing.__name__}"
                )
            mcs._registry[key] = cls
            logger.debug("Registered strategy: %s", key)
        return cls

    @classmethod
    def get(mcs, name: str) -> type[BaseStrategy]:
        """Retrieve a strategy class by name."""
        try:
            return mcs._registry[name]
        except KeyError as exc:
            raise KeyError(
                f"Unknown strategy {name!r}. Available: {mcs.list_strategies()}"
            ) from exc

    @classmethod
    def list_strategies(mcs) -> list[str]:
        """Return registered concrete strategy names in stable order."""
        return sorted(mcs._registry)


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
        instruments: list[Instrument],
        parameters: dict[str, Any] | None = None,
    ) -> None:
        symbols = [instrument.symbol for instrument in instruments]
        if len(symbols) != len(set(symbols)):
            raise ValueError("instruments must have unique symbols")
        self.instruments = {inst.symbol: inst for inst in instruments}
        self.parameters = dict(parameters or {})
        self._tick_buffer: dict[str, list[Tick]] = {inst.symbol: [] for inst in instruments}
        self._signals: list[Signal] = []
        self._is_running: bool = False
        self._position_exposure: dict[str, float] = {}

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
    def generate_signals(self) -> list[Signal]:
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
            raise ValueError(
                f"Tick symbol {tick.symbol!r} is not configured for {self.strategy_name}"
            )
        buf.append(tick)
        if len(buf) > max_buffer:
            del buf[: len(buf) - max_buffer]

    def create_order(
        self,
        symbol: str,
        side: Side,
        quantity: int,
        price: float | None = None,
        order_type: OrderType | None = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        client_id: str = "strategy",
    ) -> Order:
        """Create an order, inferring MARKET without a price and LIMIT with one."""
        normalized_symbol = symbol.strip().upper()
        if normalized_symbol not in self.instruments:
            raise ValueError(
                f"Order symbol {normalized_symbol!r} is not configured for {self.strategy_name}"
            )
        resolved_order_type = (
            order_type
            if order_type is not None
            else OrderType.LIMIT
            if price is not None
            else OrderType.MARKET
        )
        return Order(
            symbol=normalized_symbol,
            side=side,
            order_type=resolved_order_type,
            quantity=quantity,
            price=price,
            client_id=client_id,
            time_in_force=time_in_force,
        )

    @property
    def is_running(self) -> bool:
        """Whether the strategy lifecycle has been started."""
        return self._is_running

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name={self.strategy_name!r} "
            f"v={self.version} instruments={list(self.instruments)}>"
        )

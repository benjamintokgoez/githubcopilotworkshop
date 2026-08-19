"""QXM domain models — canonical representations for orders, trades, positions,
and instrument metadata used throughout the matching engine, risk layer, and
API surface.

All monetary values are represented as :class:`~decimal.Decimal` to avoid
IEEE-754 floating-point artefacts common in financial systems.  Models use
Pydantic v2 conventions (``field_validator`` / ``model_validator`` /
``model_config``) and serialise cleanly to JSON: ``Decimal`` renders as a
string and ``datetime`` / ``date`` as ISO-8601.
"""

from __future__ import annotations

import enum
import re
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def utcnow() -> datetime:
    """Timezone-aware UTC ``now`` used for every timestamp in the core."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Reject naive datetimes and normalise any aware offset to UTC.

    The core's invariant is aware-UTC everywhere, so every externally supplied
    timestamp is funnelled through this helper.
    """
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError("datetime must be timezone-aware; naive datetimes are rejected")
    return dt.astimezone(UTC)


# Reusable aware-UTC datetime field type: parses input, rejects naive values,
# and normalises aware offsets to UTC.
AwareUTC = Annotated[datetime, AfterValidator(ensure_utc)]


_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._/\-]*$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def _to_decimal(value: object) -> Decimal:
    """Coerce arbitrary numeric input to :class:`Decimal` without float noise."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):  # guard: bool is an int subclass
        raise TypeError("boolean is not a valid numeric value")
    return Decimal(str(value))


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Side(enum.StrEnum):
    BUY = "BUY"
    SELL = "SELL"

    @property
    def opposite(self) -> Side:
        return Side.SELL if self is Side.BUY else Side.BUY

    @property
    def sign(self) -> int:
        """+1 for BUY, -1 for SELL — signed position delta direction."""
        return 1 if self is Side.BUY else -1


class OrderType(enum.StrEnum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(enum.StrEnum):
    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

    @property
    def is_terminal(self) -> bool:
        return self in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        )


class InstrumentType(enum.StrEnum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    OPTION = "OPTION"
    FUTURE = "FUTURE"
    FX = "FX"
    CRYPTO = "CRYPTO"


class OptionType(enum.StrEnum):
    CALL = "CALL"
    PUT = "PUT"


class TimeInForce(enum.StrEnum):
    GTC = "GTC"  # Good-Till-Cancel
    DAY = "DAY"
    IOC = "IOC"  # Immediate-or-Cancel
    FOK = "FOK"  # Fill-or-Kill
    GTD = "GTD"  # Good-Till-Date


# ---------------------------------------------------------------------------
# Instrument
# ---------------------------------------------------------------------------


class Instrument(BaseModel):
    """Static reference data for a tradeable instrument.

    ``tick_size`` (minimum price increment) and ``lot_size`` (minimum order
    quantity increment) are decimals and may be fractional — crypto lots such
    as ``0.001`` are common.  Options additionally carry ``option_type``,
    ``strike`` and ``expiry``.
    """

    model_config = ConfigDict(validate_assignment=True)

    symbol: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1)
    instrument_type: InstrumentType
    tick_size: Decimal = Field(..., gt=0)
    lot_size: Decimal = Field(default=Decimal("1"), gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    exchange: str = Field(default="XQXM", min_length=1)
    underlying: str | None = None
    strike: Decimal | None = None
    expiry: date | None = None
    option_type: OptionType | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalise_symbol(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip().upper()
        return v

    @field_validator("symbol")
    @classmethod
    def _check_symbol(cls, v: str) -> str:
        if not _SYMBOL_RE.match(v):
            raise ValueError(f"Invalid symbol {v!r}: must be alphanumeric with . _ / - separators")
        return v

    @field_validator("currency", mode="before")
    @classmethod
    def _upper_currency(cls, v: object) -> object:
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, v: str) -> str:
        if not _CURRENCY_RE.fullmatch(v):
            raise ValueError("currency must be a three-letter ASCII code")
        return v

    @field_validator("tick_size", "lot_size", "strike", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: object) -> object:
        return _to_decimal(v) if v is not None else v

    @model_validator(mode="after")
    def _validate_option_fields(self) -> Instrument:
        if self.instrument_type is InstrumentType.OPTION:
            if self.option_type is None:
                raise ValueError("Options require an option_type (CALL/PUT)")
            if self.strike is None or self.strike <= 0:
                raise ValueError("Options require a positive strike price")
            if self.expiry is None:
                raise ValueError("Options require an expiry date")
        return self

    @property
    def is_option(self) -> bool:
        return self.instrument_type is InstrumentType.OPTION

    def round_price(self, price: Decimal) -> Decimal:
        """Round ``price`` to the nearest valid tick."""
        price = _to_decimal(price)
        steps = (price / self.tick_size).quantize(Decimal("1"))
        return steps * self.tick_size

    def is_valid_price(self, price: Decimal) -> bool:
        price = _to_decimal(price)
        if price <= 0:
            return False
        return (price % self.tick_size) == 0

    def is_valid_quantity(self, quantity: Decimal) -> bool:
        quantity = _to_decimal(quantity)
        if quantity <= 0:
            return False
        return (quantity % self.lot_size) == 0


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------


class Order(BaseModel):
    """A client order.  ``LIMIT`` / ``STOP_LIMIT`` require a positive ``price``;
    ``STOP`` / ``STOP_LIMIT`` require a positive ``stop_price``.  ``IOC`` / ``FOK``
    semantics are expressed through ``time_in_force`` rather than ``order_type``.
    """

    model_config = ConfigDict(validate_assignment=True)

    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1, max_length=32)
    side: Side
    order_type: OrderType
    quantity: Decimal = Field(..., gt=0)
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    average_fill_price: Decimal | None = None
    created_at: AwareUTC = Field(default_factory=utcnow)
    updated_at: AwareUTC | None = None
    signature: str | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalise_symbol(cls, v: object) -> object:
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator(
        "quantity",
        "price",
        "stop_price",
        "filled_quantity",
        "average_fill_price",
        mode="before",
    )
    @classmethod
    def _coerce_decimal(cls, v: object) -> object:
        return _to_decimal(v) if v is not None else v

    @model_validator(mode="after")
    def _validate_order(self) -> Order:
        if self.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT):
            if self.price is None or self.price <= 0:
                raise ValueError(f"{self.order_type.value} orders require a positive price")
        if self.order_type in (OrderType.STOP, OrderType.STOP_LIMIT):
            if self.stop_price is None or self.stop_price <= 0:
                raise ValueError(f"{self.order_type.value} orders require a positive stop_price")
        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity cannot exceed quantity")
        return self

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.filled_quantity

    @property
    def is_fully_filled(self) -> bool:
        return self.filled_quantity >= self.quantity

    @property
    def is_buy(self) -> bool:
        return self.side is Side.BUY

    @property
    def is_active(self) -> bool:
        return not self.status.is_terminal


# ---------------------------------------------------------------------------
# Trade
# ---------------------------------------------------------------------------


class Trade(BaseModel):
    trade_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    buy_order_id: str
    sell_order_id: str
    price: Decimal = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0)
    buyer_client_id: str
    seller_client_id: str
    aggressor_side: Side
    timestamp: AwareUTC = Field(default_factory=utcnow)

    @field_validator("price", "quantity", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: object) -> object:
        return _to_decimal(v) if v is not None else v

    @property
    def notional(self) -> Decimal:
        return self.price * self.quantity


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------


class Position(BaseModel):
    """Signed position with realised/unrealised P&L accounting.

    ``quantity`` is signed: positive for long, negative for short.
    ``average_entry_price`` is the volume-weighted entry price of the currently
    open exposure and is reset when the position flips through zero.
    """

    model_config = ConfigDict(validate_assignment=True)

    client_id: str
    symbol: str
    quantity: Decimal = Decimal("0")
    average_entry_price: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    last_price: Decimal | None = None
    last_updated: AwareUTC = Field(default_factory=utcnow)

    @property
    def is_flat(self) -> bool:
        return self.quantity == 0

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0

    @property
    def total_pnl(self) -> Decimal:
        return self.realized_pnl + self.unrealized_pnl

    def market_value(self, mark_price: Decimal | None = None) -> Decimal:
        price = mark_price if mark_price is not None else self.last_price
        if price is None:
            price = self.average_entry_price
        return self.quantity * _to_decimal(price)

    def apply_fill(self, side: Side, fill_qty: Decimal, fill_price: Decimal) -> Decimal:
        """Apply a fill and return the realised P&L generated by this fill.

        Handles opening, increasing, reducing, closing and flipping a position
        with correct volume-weighted average entry price and realised P&L when
        reducing or crossing through zero.
        """
        fill_qty = _to_decimal(fill_qty)
        fill_price = _to_decimal(fill_price)
        if fill_qty <= 0:
            raise ValueError("fill_qty must be positive")

        signed_delta = fill_qty * side.sign
        realised = Decimal("0")

        if self.quantity == 0:
            self.quantity = signed_delta
            self.average_entry_price = fill_price
        elif (self.quantity > 0) == (signed_delta > 0):
            new_qty = self.quantity + signed_delta
            total_cost = self.average_entry_price * abs(self.quantity) + fill_price * fill_qty
            self.quantity = new_qty
            self.average_entry_price = total_cost / abs(new_qty)
        else:
            closing_qty = min(fill_qty, abs(self.quantity))
            position_sign = 1 if self.quantity > 0 else -1
            realised = (fill_price - self.average_entry_price) * closing_qty * position_sign
            self.realized_pnl += realised
            new_qty = self.quantity + signed_delta
            if new_qty == 0:
                self.quantity = Decimal("0")
                self.average_entry_price = Decimal("0")
            elif (new_qty > 0) == (self.quantity > 0):
                self.quantity = new_qty
            else:
                self.quantity = new_qty
                self.average_entry_price = fill_price

        self.last_price = fill_price
        self.last_updated = utcnow()
        self._recompute_unrealized(fill_price)
        return realised

    def mark_to_market(self, mark_price: Decimal) -> Decimal:
        """Update unrealised P&L against ``mark_price`` and return it."""
        mark_price = _to_decimal(mark_price)
        self.last_price = mark_price
        self._recompute_unrealized(mark_price)
        self.last_updated = utcnow()
        return self.unrealized_pnl

    def _recompute_unrealized(self, mark_price: Decimal) -> None:
        if self.quantity == 0:
            self.unrealized_pnl = Decimal("0")
        else:
            self.unrealized_pnl = (mark_price - self.average_entry_price) * self.quantity


# ---------------------------------------------------------------------------
# Portfolio snapshot — aggregated view across positions
# ---------------------------------------------------------------------------


class PortfolioSnapshot(BaseModel):
    client_id: str
    positions: list[Position] = Field(default_factory=list)
    total_market_value: Decimal = Decimal("0")
    total_realized_pnl: Decimal = Decimal("0")
    total_unrealized_pnl: Decimal = Decimal("0")
    cash_balance: Decimal = Decimal("0")
    timestamp: AwareUTC = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _aggregate(self) -> PortfolioSnapshot:
        positions: Sequence[Position] = self.positions
        self.total_realized_pnl = sum((p.realized_pnl for p in positions), Decimal("0"))
        self.total_unrealized_pnl = sum((p.unrealized_pnl for p in positions), Decimal("0"))
        self.total_market_value = self.cash_balance + sum(
            (p.market_value() for p in positions), Decimal("0")
        )
        return self


# ---------------------------------------------------------------------------
# Market data tick — uses __slots__ for performance
# ---------------------------------------------------------------------------


class Tick:
    """Lightweight market data tick.  Uses ``__slots__`` to minimise per-object
    memory overhead — critical when processing millions of ticks per session."""

    __slots__ = ("symbol", "bid", "ask", "last", "volume", "timestamp")

    def __init__(
        self,
        symbol: str,
        bid: Decimal,
        ask: Decimal,
        last: Decimal,
        volume: int,
        timestamp: datetime | None = None,
    ) -> None:
        normalized_symbol = symbol.strip().upper() if isinstance(symbol, str) else ""
        if not _SYMBOL_RE.fullmatch(normalized_symbol):
            raise ValueError("symbol must be a valid non-empty instrument symbol")

        decimal_bid = _to_decimal(bid)
        decimal_ask = _to_decimal(ask)
        decimal_last = _to_decimal(last)
        if any(
            not value.is_finite() or value <= 0
            for value in (decimal_bid, decimal_ask, decimal_last)
        ):
            raise ValueError("bid, ask, and last must be finite and positive")
        if decimal_bid > decimal_ask:
            raise ValueError("bid must not exceed ask")
        if isinstance(volume, bool) or not isinstance(volume, int) or volume < 0:
            raise ValueError("volume must be a non-negative integer")

        self.symbol = normalized_symbol
        self.bid = decimal_bid
        self.ask = decimal_ask
        self.last = decimal_last
        self.volume = volume
        self.timestamp = ensure_utc(timestamp) if timestamp is not None else utcnow()

    def mid(self) -> Decimal:
        return (self.bid + self.ask) / 2

    def spread(self) -> Decimal:
        return self.ask - self.bid

    def __repr__(self) -> str:
        return (
            f"Tick({self.symbol} B={self.bid} A={self.ask} "
            f"L={self.last} V={self.volume} @{self.timestamp})"
        )


# ---------------------------------------------------------------------------
# Risk metrics container
# ---------------------------------------------------------------------------


class RiskMetrics(BaseModel):
    """Aggregated risk metrics for a portfolio or position."""

    symbol: str | None = None
    var_95: Decimal = Decimal("0")
    var_99: Decimal = Decimal("0")
    delta: Decimal = Decimal("0")
    gamma: Decimal = Decimal("0")
    theta: Decimal = Decimal("0")
    vega: Decimal = Decimal("0")
    rho: Decimal = Decimal("0")
    sharpe_ratio: Decimal | None = None
    max_drawdown: Decimal | None = None
    computed_at: AwareUTC = Field(default_factory=utcnow)


__all__ = [
    "utcnow",
    "ensure_utc",
    "AwareUTC",
    "Side",
    "OrderType",
    "OrderStatus",
    "InstrumentType",
    "OptionType",
    "TimeInForce",
    "Instrument",
    "Order",
    "Trade",
    "Position",
    "PortfolioSnapshot",
    "Tick",
    "RiskMetrics",
]

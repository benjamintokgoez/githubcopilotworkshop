"""QXM domain models — canonical representations for orders, trades, positions,
and instrument metadata used throughout the matching engine, risk layer, and
API surface.

All monetary values are represented as :class:`~decimal.Decimal` to avoid
IEEE-754 floating-point artefacts common in financial systems.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field, validator, root_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Side(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, enum.Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    IOC = "IOC"          # Immediate-or-Cancel
    FOK = "FOK"          # Fill-or-Kill


class OrderStatus(str, enum.Enum):
    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class InstrumentType(str, enum.Enum):
    EQUITY = "EQUITY"
    OPTION_CALL = "OPTION_CALL"
    OPTION_PUT = "OPTION_PUT"
    FUTURE = "FUTURE"
    FX_SPOT = "FX_SPOT"


class TimeInForce(str, enum.Enum):
    GTC = "GTC"          # Good-Till-Cancel
    DAY = "DAY"
    IOC = "IOC"
    FOK = "FOK"
    GTD = "GTD"          # Good-Till-Date


# ---------------------------------------------------------------------------
# Custom Pydantic type — demonstrates __get_validators__ (v1 pattern)
# ---------------------------------------------------------------------------

class TickSize:
    """Constrained decimal representing the minimum price increment for an
    instrument.  Uses pydantic v1 ``__get_validators__`` protocol so that
    it can be used directly as a field type."""

    __slots__ = ("_value",)

    def __init__(self, value: Decimal) -> None:
        if value <= 0:
            raise ValueError(f"TickSize must be positive, got {value}")
        self._value = value

    @classmethod
    def __get_validators__(cls):
        yield cls._validate

    @classmethod
    def _validate(cls, v: Any) -> "TickSize":
        if isinstance(v, cls):
            return v
        return cls(Decimal(str(v)))

    @property
    def value(self) -> Decimal:
        return self._value

    def __repr__(self) -> str:
        return f"TickSize({self._value})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TickSize):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)


# ---------------------------------------------------------------------------
# Instrument
# ---------------------------------------------------------------------------

class Instrument(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=12)
    name: str
    instrument_type: InstrumentType
    tick_size: TickSize
    lot_size: int = Field(default=1, ge=1)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    exchange: str = Field(default="XQXM")
    # Option-specific fields (populated only for options)
    underlying: Optional[str] = None
    strike: Optional[Decimal] = None
    expiry: Optional[datetime] = None

    @validator("strike", always=True)
    def _validate_strike(cls, v, values):
        itype = values.get("instrument_type")
        if itype in (InstrumentType.OPTION_CALL, InstrumentType.OPTION_PUT):
            if v is None or v <= 0:
                raise ValueError("Options require a positive strike price")
        return v

    @validator("expiry", always=True)
    def _validate_expiry(cls, v, values):
        itype = values.get("instrument_type")
        if itype in (InstrumentType.OPTION_CALL, InstrumentType.OPTION_PUT):
            if v is None:
                raise ValueError("Options require an expiry date")
        return v

    @root_validator(pre=True)
    def _normalise_symbol(cls, values):
        if "symbol" in values and isinstance(values["symbol"], str):
            values["symbol"] = values["symbol"].upper().strip()
        return values

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            Decimal: str,
            datetime: lambda dt: dt.isoformat(),
            TickSize: lambda ts: str(ts.value),
        }


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

class Order(BaseModel):
    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Optional[Decimal] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    signature: Optional[str] = None

    @validator("quantity")
    def _quantity_positive(cls, v):
        if v <= 0:
            raise ValueError("Order quantity must be positive")
        return v

    @validator("price", always=True)
    def _price_required_for_limit(cls, v, values):
        otype = values.get("order_type")
        if otype in (OrderType.LIMIT, OrderType.STOP_LIMIT):
            if v is None or v <= 0:
                raise ValueError(f"{otype} orders require a positive price")
        return v

    @validator("stop_price", always=True)
    def _stop_price_required(cls, v, values):
        otype = values.get("order_type")
        if otype in (OrderType.STOP, OrderType.STOP_LIMIT):
            if v is None or v <= 0:
                raise ValueError(f"{otype} orders require a positive stop_price")
        return v

    @root_validator
    def _compute_status(cls, values):
        filled = values.get("filled_quantity", Decimal("0"))
        qty = values.get("quantity", Decimal("0"))
        if filled > 0 and filled < qty:
            values["status"] = OrderStatus.PARTIALLY_FILLED
        elif filled >= qty and qty > 0:
            values["status"] = OrderStatus.FILLED
        return values

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.filled_quantity

    @property
    def is_fully_filled(self) -> bool:
        return self.filled_quantity >= self.quantity

    class Config:
        arbitrary_types_allowed = True
        use_enum_values = True
        json_encoders = {
            Decimal: str,
            datetime: lambda dt: dt.isoformat(),
        }


# ---------------------------------------------------------------------------
# Trade
# ---------------------------------------------------------------------------

class Trade(BaseModel):
    trade_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    buy_order_id: str
    sell_order_id: str
    price: Decimal
    quantity: Decimal
    buyer_client_id: str
    seller_client_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @validator("price")
    def _price_positive(cls, v):
        if v <= 0:
            raise ValueError("Trade price must be positive")
        return v

    @validator("quantity")
    def _quantity_positive(cls, v):
        if v <= 0:
            raise ValueError("Trade quantity must be positive")
        return v

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda dt: dt.isoformat(),
        }


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------

class Position(BaseModel):
    client_id: str
    symbol: str
    quantity: Decimal = Decimal("0")
    average_entry_price: Decimal = Decimal("0")
    realised_pnl: Decimal = Decimal("0")
    unrealised_pnl: Decimal = Decimal("0")
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @property
    def market_value(self) -> Decimal:
        return self.quantity * self.average_entry_price

    @property
    def total_pnl(self) -> Decimal:
        return self.realised_pnl + self.unrealised_pnl

    def apply_fill(self, side: str, fill_qty: Decimal, fill_price: Decimal) -> None:
        if side == Side.BUY:
            total_cost = self.average_entry_price * self.quantity + fill_price * fill_qty
            self.quantity += fill_qty
            self.average_entry_price = total_cost / self.quantity if self.quantity else Decimal("0")
        else:
            if fill_qty <= self.quantity:
                pnl = (fill_price - self.average_entry_price) * fill_qty
                self.realised_pnl += pnl
                self.quantity -= fill_qty
            else:
                pnl = (fill_price - self.average_entry_price) * self.quantity
                self.realised_pnl += pnl
                remaining = fill_qty - self.quantity
                self.quantity = -remaining
                self.average_entry_price = fill_price
        self.last_updated = datetime.utcnow()

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda dt: dt.isoformat(),
        }


# ---------------------------------------------------------------------------
# Portfolio snapshot — aggregated view across positions
# ---------------------------------------------------------------------------

class PortfolioSnapshot(BaseModel):
    client_id: str
    positions: List[Position] = Field(default_factory=list)
    total_value: Decimal = Decimal("0")
    total_realised_pnl: Decimal = Decimal("0")
    total_unrealised_pnl: Decimal = Decimal("0")
    cash_balance: Decimal = Decimal("0")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @root_validator
    def _aggregate(cls, values):
        positions: Sequence[Position] = values.get("positions", [])
        values["total_realised_pnl"] = sum(
            (p.realised_pnl for p in positions), Decimal("0")
        )
        values["total_unrealised_pnl"] = sum(
            (p.unrealised_pnl for p in positions), Decimal("0")
        )
        values["total_value"] = values.get("cash_balance", Decimal("0")) + sum(
            (p.market_value for p in positions), Decimal("0")
        )
        return values

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda dt: dt.isoformat(),
        }


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
        timestamp: datetime,
    ) -> None:
        self.symbol = symbol
        self.bid = bid
        self.ask = ask
        self.last = last
        self.volume = volume
        self.timestamp = timestamp

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
    symbol: Optional[str] = None
    var_95: Decimal = Decimal("0")
    var_99: Decimal = Decimal("0")
    delta: Decimal = Decimal("0")
    gamma: Decimal = Decimal("0")
    theta: Decimal = Decimal("0")
    vega: Decimal = Decimal("0")
    rho: Decimal = Decimal("0")
    sharpe_ratio: Optional[Decimal] = None
    max_drawdown: Optional[Decimal] = None
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda dt: dt.isoformat(),
        }


# ---------------------------------------------------------------------------
# Forward reference resolution (v1 pattern)
# ---------------------------------------------------------------------------
PortfolioSnapshot.update_forward_refs()
Instrument.update_forward_refs()

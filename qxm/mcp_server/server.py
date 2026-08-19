"""High-level MCP v2 server for QuantCore's local simulation runtime.

The default server is read-only. Mutating tools are registered only when a
caller explicitly opts in and binds a client identity while constructing the
server. Importing this module performs no I/O and starts no processes.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, NoReturn, Protocol, cast

from mcp import MCPError
from mcp.server import MCPServer
from mcp.types import INVALID_PARAMS, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from qxm import __version__
from qxm.core.engine import DuplicateOrderError, MatchingEngine, OrderSubmission
from qxm.core.events import EventBus
from qxm.core.models import (
    Instrument,
    InstrumentType,
    OptionType,
    Order,
    OrderStatus,
    OrderType,
    Side,
    TimeInForce,
    Trade,
    utcnow,
)
from qxm.risk.var import VaREngine

DEFAULT_INSTRUMENTS_PATH = Path(__file__).resolve().parents[2] / "instruments.json"
MAX_INSTRUMENT_RESULTS = 50
MAX_BOOK_DEPTH = 20
MAX_PNL_OBSERVATIONS = 256
MAX_ORDER_QUANTITY = Decimal("10000")
MAX_SERIALIZED_TRADES = 100
MAX_CLIENT_ID_LENGTH = 64
MAX_REJECTION_REASON_LENGTH = 256
REJECTION_DETAIL_UNAVAILABLE = (
    "Local simulation engine rejected the order; detailed reason unavailable"
)
_CLIENT_ID_PATTERN = re.compile(rf"[A-Za-z0-9][A-Za-z0-9._:@/-]{{0,{MAX_CLIENT_ID_LENGTH - 1}}}")

SymbolInput = Annotated[
    str,
    Field(
        min_length=1,
        max_length=32,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/\-]*$",
        description="Local simulated instrument symbol.",
    ),
]
OrderIdInput = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:\-]*$",
        description="Client-supplied or server-generated simulated order identifier.",
    ),
]
QuantityInput = Annotated[
    Decimal,
    Field(
        gt=0,
        le=MAX_ORDER_QUANTITY,
        max_digits=24,
        decimal_places=8,
        allow_inf_nan=False,
        description=(
            "Positive simulated quantity up to 10,000; strings preserve decimal precision."
        ),
    ),
]
PriceInput = Annotated[
    Decimal,
    Field(
        gt=0,
        le=Decimal("1000000000000"),
        max_digits=24,
        decimal_places=8,
        allow_inf_nan=False,
        description="Positive simulated limit price; strings preserve decimal precision.",
    ),
]
PortfolioValueInput = Annotated[
    Decimal,
    Field(
        ge=0,
        le=Decimal("1000000000000000"),
        max_digits=24,
        decimal_places=8,
        allow_inf_nan=False,
    ),
]
VolatilityInput = Annotated[
    Decimal,
    Field(ge=0, le=Decimal("10"), max_digits=12, decimal_places=10, allow_inf_nan=False),
]
ConfidenceInput = Annotated[
    Decimal,
    Field(gt=0, lt=1, max_digits=12, decimal_places=10, allow_inf_nan=False),
]
PnlObservation = Annotated[
    Decimal,
    Field(
        ge=Decimal("-1000000000000000"),
        le=Decimal("1000000000000000"),
        max_digits=24,
        decimal_places=8,
        allow_inf_nan=False,
    ),
]
PnlHistoryInput = Annotated[
    list[PnlObservation],
    Field(min_length=1, max_length=MAX_PNL_OBSERVATIONS),
]


class SupportedOrderType(StrEnum):
    """Order types backed by the current simulation engine."""

    LIMIT = "LIMIT"
    MARKET = "MARKET"


class SupportedTimeInForce(StrEnum):
    """Time-in-force values backed by the current simulation engine."""

    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class RiskCalculator(Protocol):
    """Structural contract for the risk calculator injected into a server."""

    def compute(
        self,
        portfolio_value: float,
        daily_volatility: float | None = None,
        pnl_history: Sequence[float] | None = None,
        confidence: float | None = None,
        holding_period: int | None = None,
    ) -> dict[str, float]:
        """Compute requested VaR-family loss magnitudes."""


class _ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    environment: Literal["SIMULATION"] = "SIMULATION"


class InstrumentSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    name: str
    instrument_type: InstrumentType
    tick_size: Decimal
    lot_size: Decimal
    currency: str
    exchange: str
    underlying: str | None
    strike: Decimal | None
    expiry: date | None
    option_type: OptionType | None


class InstrumentListResult(_ToolResult):
    total: int
    offset: int
    limit: int
    returned: int
    instruments: list[InstrumentSummary]


class BookLevelResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    price: Decimal
    quantity: Decimal
    orders: int


class MarketSnapshotResult(_ToolResult):
    symbol: str
    as_of: datetime
    requested_depth: int
    best_bid: Decimal | None
    best_ask: Decimal | None
    spread: Decimal | None
    midpoint: Decimal | None
    bids: list[BookLevelResult]
    asks: list[BookLevelResult]


class RiskCalculationResult(_ToolResult):
    as_of: datetime
    confidence: Decimal
    holding_period: int
    pnl_observations: int
    parametric_var: Decimal | None
    historical_var: Decimal | None
    conditional_var: Decimal | None


class TradeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    trade_id: str
    buy_order_id: str
    sell_order_id: str
    price: Decimal
    quantity: Decimal
    aggressor_side: Side
    timestamp: datetime


class OrderResult(_ToolResult):
    order_id: str
    symbol: str
    side: Side
    order_type: OrderType
    time_in_force: TimeInForce
    status: OrderStatus
    accepted: bool
    quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    price: Decimal | None
    average_fill_price: Decimal | None
    created_at: datetime
    updated_at: datetime | None
    rejection_reason: Annotated[str | None, Field(max_length=MAX_REJECTION_REASON_LENGTH)]
    trade_count: Annotated[int, Field(ge=0)]
    returned_trade_count: Annotated[int, Field(ge=0, le=MAX_SERIALIZED_TRADES)]
    trades_truncated: bool
    trades: Annotated[list[TradeResult], Field(max_length=MAX_SERIALIZED_TRADES)]


class CancellationResult(_ToolResult):
    order_id: str
    symbol: str
    status: OrderStatus
    updated_at: datetime


def _invalid_params(message: str) -> NoReturn:
    raise MCPError(code=INVALID_PARAMS, message=message)


def _copy_instruments(instruments: Mapping[str, Instrument]) -> dict[str, Instrument]:
    if not instruments:
        raise ValueError("At least one simulated instrument is required")

    copied: dict[str, Instrument] = {}
    for key, instrument in instruments.items():
        canonical_symbol = key.strip().upper()
        if canonical_symbol != instrument.symbol:
            raise ValueError(
                f"Instrument mapping key {key!r} does not match symbol {instrument.symbol!r}"
            )
        if canonical_symbol in copied:
            raise ValueError(f"Duplicate simulated instrument symbol: {canonical_symbol}")
        copied[canonical_symbol] = instrument
    return copied


def _instrument_summary(instrument: Instrument) -> InstrumentSummary:
    return InstrumentSummary(
        symbol=instrument.symbol,
        name=instrument.name,
        instrument_type=instrument.instrument_type,
        tick_size=instrument.tick_size,
        lot_size=instrument.lot_size,
        currency=instrument.currency,
        exchange=instrument.exchange,
        underlying=instrument.underlying,
        strike=instrument.strike,
        expiry=instrument.expiry,
        option_type=instrument.option_type,
    )


def _trade_result(trade: Trade) -> TradeResult:
    return TradeResult(
        trade_id=trade.trade_id,
        buy_order_id=trade.buy_order_id,
        sell_order_id=trade.sell_order_id,
        price=trade.price,
        quantity=trade.quantity,
        aggressor_side=trade.aggressor_side,
        timestamp=trade.timestamp,
    )


def _order_result(submission: OrderSubmission) -> OrderResult:
    order = submission.order
    trade_count = len(submission.trades)
    retained_trades = submission.trades[:MAX_SERIALIZED_TRADES]
    return OrderResult(
        order_id=order.order_id,
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        time_in_force=order.time_in_force,
        status=order.status,
        accepted=submission.accepted,
        quantity=order.quantity,
        filled_quantity=order.filled_quantity,
        remaining_quantity=order.remaining_quantity,
        price=order.price,
        average_fill_price=order.average_fill_price,
        created_at=order.created_at,
        updated_at=order.updated_at,
        rejection_reason=_bounded_rejection_reason(submission),
        trade_count=trade_count,
        returned_trade_count=len(retained_trades),
        trades_truncated=trade_count > len(retained_trades),
        trades=[_trade_result(trade) for trade in retained_trades],
    )


def _bounded_rejection_reason(submission: OrderSubmission) -> str | None:
    if submission.order.status is not OrderStatus.REJECTED:
        return None
    reason = submission.rejection_reason or REJECTION_DETAIL_UNAVAILABLE
    if len(reason) <= MAX_REJECTION_REASON_LENGTH:
        return reason
    return f"{reason[: MAX_REJECTION_REASON_LENGTH - 3]}..."


def _loss_decimal(value: float, metric: str) -> Decimal:
    if not math.isfinite(value) or value < 0:
        raise RuntimeError(f"Risk calculator returned an invalid {metric} loss magnitude")
    return Decimal(str(value))


def _load_instruments(path: Path) -> dict[str, Instrument]:
    if not path.is_file():
        raise FileNotFoundError(f"Instruments file not found: {path}")

    data = cast(object, json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal))
    if not isinstance(data, list):
        raise ValueError(f"Instruments file must contain a JSON array: {path}")

    instruments: dict[str, Instrument] = {}
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Instrument entry {index} must be a JSON object")
        instrument = Instrument.model_validate(item)
        if instrument.symbol in instruments:
            raise ValueError(f"Duplicate instrument symbol: {instrument.symbol}")
        instruments[instrument.symbol] = instrument
    if not instruments:
        raise ValueError(f"Instruments file contains no instruments: {path}")
    return instruments


def create_mcp_server(
    engine: MatchingEngine,
    instruments: Mapping[str, Instrument],
    *,
    risk_calculator: RiskCalculator | None = None,
    allow_writes: bool = False,
    client_id: str | None = None,
) -> MCPServer[None]:
    """Create an isolated MCP server around injected local simulation state.

    ``allow_writes`` controls whether mutation tools are registered at all.
    When enabled, ``client_id`` is captured by the handlers and is never
    accepted as a tool argument.
    """

    instrument_map = _copy_instruments(instruments)
    if engine.instruments != instrument_map:
        raise ValueError("MatchingEngine instruments must match the MCP instrument mapping")

    bound_client_id: str | None = None
    if allow_writes:
        if client_id is None or _CLIENT_ID_PATTERN.fullmatch(client_id) is None:
            raise ValueError(
                f"Write-enabled client_id must be 1-{MAX_CLIENT_ID_LENGTH} ASCII "
                "characters using letters, digits, '.', '_', ':', '@', '/', or '-'"
            )
        bound_client_id = client_id

    calculator = risk_calculator if risk_calculator is not None else VaREngine()
    mcp: MCPServer[None] = MCPServer(
        name="quantcore-simulation",
        title="QuantCore Simulation",
        description="Bounded tools for the local QuantCore educational trading simulation.",
        instructions=(
            "All instruments, order books, trades, and risk results are local simulated "
            "data. This server cannot reach live markets."
        ),
        version=__version__,
        log_level="WARNING",
    )
    owned_open_order_ids: set[str] = set()

    def require_instrument(symbol: str) -> Instrument:
        canonical = symbol.upper()
        instrument = instrument_map.get(canonical)
        if instrument is None:
            _invalid_params(f"Unknown simulated instrument: {canonical}")
        return instrument

    @mcp.tool(
        description=(
            "List bounded local simulated instrument reference data. "
            "No live market or network data is used."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def list_instruments(
        limit: Annotated[int, Field(ge=1, le=MAX_INSTRUMENT_RESULTS)] = 20,
        offset: Annotated[int, Field(ge=0, le=10_000)] = 0,
    ) -> InstrumentListResult:
        ordered = [instrument_map[symbol] for symbol in sorted(instrument_map)]
        selected = ordered[offset : offset + limit]
        return InstrumentListResult(
            total=len(ordered),
            offset=offset,
            limit=limit,
            returned=len(selected),
            instruments=[_instrument_summary(instrument) for instrument in selected],
        )

    @mcp.tool(
        description=(
            "Return a bounded snapshot of a local simulated order book. "
            "An inactive known symbol has empty bid and ask arrays."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def get_order_book(
        symbol: SymbolInput,
        depth: Annotated[int, Field(ge=1, le=MAX_BOOK_DEPTH)] = 5,
    ) -> MarketSnapshotResult:
        instrument = require_instrument(symbol)
        book = engine.get_book(instrument.symbol)
        if book is None:
            return MarketSnapshotResult(
                symbol=instrument.symbol,
                as_of=utcnow(),
                requested_depth=depth,
                best_bid=None,
                best_ask=None,
                spread=None,
                midpoint=None,
                bids=[],
                asks=[],
            )

        bids = [
            BookLevelResult(
                price=level.price,
                quantity=level.total_quantity,
                orders=level.order_count,
            )
            for level in book.bid_levels(depth)
        ]
        asks = [
            BookLevelResult(
                price=level.price,
                quantity=level.total_quantity,
                orders=level.order_count,
            )
            for level in book.ask_levels(depth)
        ]
        return MarketSnapshotResult(
            symbol=instrument.symbol,
            as_of=utcnow(),
            requested_depth=depth,
            best_bid=book.best_bid,
            best_ask=book.best_ask,
            spread=book.spread,
            midpoint=book.midpoint,
            bids=bids,
            asks=asks,
        )

    @mcp.tool(
        description=(
            "Calculate bounded VaR and expected-shortfall loss magnitudes from caller-provided "
            "simulated inputs. Provide daily_volatility, pnl_history, or both."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def calculate_risk(
        portfolio_value: PortfolioValueInput,
        daily_volatility: VolatilityInput | None = None,
        pnl_history: PnlHistoryInput | None = None,
        confidence: ConfidenceInput = Decimal("0.95"),
        holding_period: Annotated[int, Field(ge=1, le=252)] = 1,
    ) -> RiskCalculationResult:
        if daily_volatility is None and pnl_history is None:
            _invalid_params("Provide daily_volatility, pnl_history, or both")

        float_history = (
            [float(observation) for observation in pnl_history] if pnl_history is not None else None
        )
        calculated = calculator.compute(
            portfolio_value=float(portfolio_value),
            daily_volatility=(float(daily_volatility) if daily_volatility is not None else None),
            pnl_history=float_history,
            confidence=float(confidence),
            holding_period=holding_period,
        )
        parametric = (
            _loss_decimal(calculated["parametric_var"], "parametric VaR")
            if daily_volatility is not None
            else None
        )
        historical = (
            _loss_decimal(calculated["historical_var"], "historical VaR")
            if pnl_history is not None
            else None
        )
        conditional = (
            _loss_decimal(calculated["conditional_var"], "conditional VaR")
            if pnl_history is not None
            else None
        )
        return RiskCalculationResult(
            as_of=utcnow(),
            confidence=confidence,
            holding_period=holding_period,
            pnl_observations=len(pnl_history) if pnl_history is not None else 0,
            parametric_var=parametric,
            historical_var=historical,
            conditional_var=conditional,
        )

    if allow_writes:
        if bound_client_id is None:
            raise RuntimeError("Write-enabled server is missing its bound client identity")

        @mcp.tool(
            description=(
                "Submit an order only to this server's local simulated matching engine. "
                "This never routes to a broker or live market."
            ),
            annotations=ToolAnnotations(
                readOnlyHint=False,
                destructiveHint=True,
                idempotentHint=False,
                openWorldHint=False,
            ),
        )
        async def submit_order(
            symbol: SymbolInput,
            side: Side,
            quantity: QuantityInput,
            order_type: SupportedOrderType = SupportedOrderType.LIMIT,
            price: PriceInput | None = None,
            time_in_force: SupportedTimeInForce = SupportedTimeInForce.GTC,
            order_id: OrderIdInput | None = None,
        ) -> OrderResult:
            instrument = require_instrument(symbol)
            if order_type is SupportedOrderType.LIMIT and price is None:
                _invalid_params("LIMIT orders require a price")
            if order_type is SupportedOrderType.MARKET and price is not None:
                _invalid_params("MARKET orders must not include a price")

            order_data: dict[str, object] = {
                "client_id": bound_client_id,
                "symbol": instrument.symbol,
                "side": side,
                "order_type": OrderType(order_type.value),
                "quantity": quantity,
                "price": price,
                "time_in_force": TimeInForce(time_in_force.value),
            }
            if order_id is not None:
                order_data["order_id"] = order_id
            order = Order.model_validate(order_data)
            try:
                submission = await engine.submit_order(order)
            except DuplicateOrderError as exc:
                _invalid_params(str(exc))

            if order.is_active:
                owned_open_order_ids.add(order.order_id)
            return _order_result(submission)

        @mcp.tool(
            description=(
                "Cancel an open order previously submitted by this MCP server identity "
                "in the local simulation. This never contacts a live market."
            ),
            annotations=ToolAnnotations(
                readOnlyHint=False,
                destructiveHint=True,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )
        async def cancel_order(order_id: OrderIdInput) -> CancellationResult:
            if order_id not in owned_open_order_ids:
                _invalid_params("Open simulated order not found for this MCP client")

            order = await engine.cancel_order(order_id)
            owned_open_order_ids.discard(order_id)
            if order is None:
                _invalid_params("Open simulated order not found for this MCP client")
            if order.updated_at is None:
                raise RuntimeError("Cancelled order is missing its update timestamp")
            return CancellationResult(
                order_id=order.order_id,
                symbol=order.symbol,
                status=order.status,
                updated_at=order.updated_at,
            )

    return mcp


def create_default_mcp_server(
    *,
    instruments_path: Path | None = None,
) -> MCPServer[None]:
    """Build a fresh read-only server from local repository configuration."""

    instruments = _load_instruments(instruments_path or DEFAULT_INSTRUMENTS_PATH)
    engine = MatchingEngine(event_bus=EventBus(), instruments=instruments)
    return create_mcp_server(engine=engine, instruments=instruments)


def run_server() -> None:
    """Run a fresh read-only QuantCore MCP server over stdio."""

    create_default_mcp_server().run()


if __name__ == "__main__":
    run_server()


__all__ = [
    "RiskCalculator",
    "create_default_mcp_server",
    "create_mcp_server",
    "run_server",
]

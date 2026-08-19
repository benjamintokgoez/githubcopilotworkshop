"""Focused tests for the rebuilt QXM core runtime (Pydantic v2).

Covers FIFO price-time priority, maker fill pricing, depth after partial
fills, IOC/FOK time-in-force, cancellation, pre-trade risk rejection,
instrument/tick/lot boundary validation, event delivery/replay,
long/short/crossing position P&L, aware-UTC timestamp enforcement, honest
DAY/GTD rejection, order lifecycle boundaries (duplicate ids / non-NEW), and
EventBus configuration/subscriber-id hardening.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from qxm.core.engine import DuplicateOrderError, MatchingEngine, OrderSubmission
from qxm.core.events import DomainEvent, EventBus, EventLog, EventType
from qxm.core.models import (
    Instrument,
    InstrumentType,
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
)

D = Decimal


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _instruments() -> dict[str, Instrument]:
    return {
        "AAPL": Instrument(
            symbol="AAPL",
            name="Apple Inc.",
            instrument_type=InstrumentType.EQUITY,
            tick_size="0.01",
            lot_size="1",
        ),
        "BTC-USD": Instrument(
            symbol="BTC-USD",
            name="Bitcoin / US Dollar",
            instrument_type=InstrumentType.CRYPTO,
            tick_size="0.01",
            lot_size="0.001",
        ),
    }


def _engine(risk_check=None) -> MatchingEngine:
    return MatchingEngine(
        event_bus=EventBus(),
        instruments=_instruments(),
        risk_check=risk_check,
    )


def _order(
    side: Side,
    quantity,
    price=None,
    *,
    symbol: str = "AAPL",
    order_type: OrderType = OrderType.LIMIT,
    tif: TimeInForce = TimeInForce.GTC,
    client_id: str = "c1",
    stop_price=None,
) -> Order:
    return Order(
        client_id=client_id,
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=D(str(quantity)),
        price=None if price is None else D(str(price)),
        stop_price=None if stop_price is None else D(str(stop_price)),
        time_in_force=tif,
    )


def _events_for(eng: MatchingEngine, order_id: str) -> list[DomainEvent]:
    """Return all events correlated to ``order_id``, in publication order."""
    return [e for e in eng._event_bus.replay() if e.correlation_id == order_id]


# ---------------------------------------------------------------------------
# FIFO price-time priority
# ---------------------------------------------------------------------------


async def test_fifo_price_time_priority() -> None:
    eng = _engine()
    maker_a = _order(Side.SELL, 5, 100, client_id="A")
    maker_b = _order(Side.SELL, 5, 100, client_id="B")
    await eng.submit_order(maker_a)
    await eng.submit_order(maker_b)

    taker = _order(Side.BUY, 6, 100, client_id="T")
    result = await eng.submit_order(taker)

    assert isinstance(result, OrderSubmission)
    # First resting order (A) must be consumed before B (time priority).
    assert result.trades[0].sell_order_id == maker_a.order_id
    assert result.trades[0].quantity == D("5")
    assert result.trades[1].sell_order_id == maker_b.order_id
    assert result.trades[1].quantity == D("1")
    assert taker.status is OrderStatus.FILLED
    # B has 4 left resting.
    book = eng.get_book("AAPL")
    assert book is not None
    assert book.best_ask == D("100")
    assert book.ask_levels()[0].total_quantity == D("4")


async def test_price_priority_best_level_first() -> None:
    eng = _engine()
    await eng.submit_order(_order(Side.SELL, 5, 101, client_id="A"))
    await eng.submit_order(_order(Side.SELL, 5, 100, client_id="B"))
    taker = _order(Side.BUY, 5, 101, client_id="T")
    result = await eng.submit_order(taker)
    # Best (lowest) ask 100 fills first.
    assert result.trades[0].price == D("100")


# ---------------------------------------------------------------------------
# Maker (resting) fill price
# ---------------------------------------------------------------------------


async def test_fill_at_resting_maker_price_limit() -> None:
    eng = _engine()
    await eng.submit_order(_order(Side.SELL, 5, 101, client_id="M"))
    taker = _order(Side.BUY, 5, 105, client_id="T")  # crosses aggressively
    result = await eng.submit_order(taker)
    assert len(result.trades) == 1
    assert result.trades[0].price == D("101")  # maker's price, not 105
    assert taker.average_fill_price == D("101")


async def test_market_order_fills_at_maker_price_and_never_rests() -> None:
    eng = _engine()
    await eng.submit_order(_order(Side.SELL, 4, 102, client_id="M"))
    taker = _order(Side.BUY, 10, order_type=OrderType.MARKET, client_id="T")
    result = await eng.submit_order(taker)
    assert result.trades[0].price == D("102")
    assert taker.filled_quantity == D("4")
    # Residual must be cancelled, never rested.
    book = eng.get_book("AAPL")
    assert book is not None
    assert book.bid_depth == 0
    # A partially filled market order whose residual is cancelled ends terminal.
    assert taker.status is OrderStatus.CANCELLED
    assert taker.status.is_terminal


# ---------------------------------------------------------------------------
# Depth after partial fills
# ---------------------------------------------------------------------------


async def test_depth_accurate_after_partial_fill() -> None:
    eng = _engine()
    await eng.submit_order(_order(Side.SELL, 10, 100, client_id="M"))
    await eng.submit_order(_order(Side.BUY, 3, 100, client_id="T"))
    book = eng.get_book("AAPL")
    assert book is not None
    level = book.ask_levels()[0]
    assert level.total_quantity == D("7")
    assert level.order_count == 1
    snap = book.depth_snapshot()
    assert snap["asks"][0]["quantity"] == "7"


# ---------------------------------------------------------------------------
# Time in force: IOC / FOK
# ---------------------------------------------------------------------------


async def test_ioc_cancels_residual() -> None:
    eng = _engine()
    await eng.submit_order(_order(Side.SELL, 3, 100, client_id="M"))
    taker = _order(Side.BUY, 10, 100, tif=TimeInForce.IOC, client_id="T")
    result = await eng.submit_order(taker)
    assert taker.filled_quantity == D("3")
    # Residual cancelled -> terminal CANCELLED, not left nonterminal off-book.
    assert taker.status is OrderStatus.CANCELLED
    assert taker.status.is_terminal
    book = eng.get_book("AAPL")
    assert book is not None
    assert book.bid_depth == 0  # residual not rested
    assert len(result.trades) == 1
    # The partial-fill event must precede the cancellation event.
    kinds = [
        e.event_type
        for e in _events_for(eng, taker.order_id)
        if e.event_type in (EventType.ORDER_PARTIALLY_FILLED, EventType.ORDER_CANCELLED)
    ]
    assert kinds == [EventType.ORDER_PARTIALLY_FILLED, EventType.ORDER_CANCELLED]


async def test_ioc_no_liquidity_is_cancelled() -> None:
    eng = _engine()
    taker = _order(Side.BUY, 5, 100, tif=TimeInForce.IOC, client_id="T")
    result = await eng.submit_order(taker)
    assert result.trades == []
    assert taker.status is OrderStatus.CANCELLED
    book = eng.get_book("AAPL")
    assert book is not None
    assert book.bid_depth == 0


async def test_fok_killed_when_not_fully_fillable() -> None:
    eng = _engine()
    await eng.submit_order(_order(Side.SELL, 3, 100, client_id="M"))
    taker = _order(Side.BUY, 10, 100, tif=TimeInForce.FOK, client_id="T")
    result = await eng.submit_order(taker)
    assert result.trades == []
    # An unfillable FOK is accepted then killed (cancelled), not rejected.
    assert taker.status is OrderStatus.CANCELLED
    kinds = [e.event_type for e in _events_for(eng, taker.order_id)]
    assert kinds == [
        EventType.ORDER_SUBMITTED,
        EventType.ORDER_ACCEPTED,
        EventType.ORDER_CANCELLED,
    ]
    cancel_evt = _events_for(eng, taker.order_id)[-1]
    assert "fully filled" in cancel_evt.payload["reason"]
    # Resting liquidity untouched.
    book = eng.get_book("AAPL")
    assert book is not None
    assert book.ask_levels()[0].total_quantity == D("3")


async def test_fok_fills_when_fully_available() -> None:
    eng = _engine()
    await eng.submit_order(_order(Side.SELL, 6, 100, client_id="M1"))
    await eng.submit_order(_order(Side.SELL, 6, 100, client_id="M2"))
    taker = _order(Side.BUY, 10, 100, tif=TimeInForce.FOK, client_id="T")
    result = await eng.submit_order(taker)
    assert taker.status is OrderStatus.FILLED
    assert taker.filled_quantity == D("10")
    assert sum(t.quantity for t in result.trades) == D("10")


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


async def test_cancel_resting_order() -> None:
    eng = _engine()
    resting = _order(Side.BUY, 5, 99, client_id="M")
    await eng.submit_order(resting)
    cancelled = await eng.cancel_order(resting.order_id)  # symbol omitted
    assert cancelled is not None
    assert cancelled.order_id == resting.order_id
    assert cancelled.status is OrderStatus.CANCELLED
    book = eng.get_book("AAPL")
    assert book is not None
    assert book.total_orders == 0
    # Cancelling again returns None (no stale index).
    assert await eng.cancel_order(resting.order_id) is None


async def test_cancel_with_symbol_hint() -> None:
    eng = _engine()
    resting = _order(Side.SELL, 5, 101, client_id="M")
    await eng.submit_order(resting)
    cancelled = await eng.cancel_order(resting.order_id, symbol="AAPL")
    assert cancelled is not None
    assert await eng.cancel_order("does-not-exist", symbol="AAPL") is None


# ---------------------------------------------------------------------------
# Risk rejection
# ---------------------------------------------------------------------------


class _RejectAll:
    def can_execute(self, order: Order, position: Position | None) -> tuple[bool, str]:
        return False, "blocked by risk"


async def test_risk_check_rejection() -> None:
    eng = _engine(risk_check=_RejectAll())
    taker = _order(Side.BUY, 5, 100, client_id="T")
    result = await eng.submit_order(taker)
    assert result.trades == []
    assert result.rejection_reason == "blocked by risk"
    assert taker.status is OrderStatus.REJECTED
    rejected = eng._event_bus.replay(event_types={EventType.ORDER_REJECTED})
    assert rejected and rejected[-1].payload["reason"] == "blocked by risk"


# ---------------------------------------------------------------------------
# Boundary validation: instrument / tick / lot / unsupported type
# ---------------------------------------------------------------------------


async def test_reject_unknown_instrument() -> None:
    eng = _engine()
    order = _order(Side.BUY, 1, 100, symbol="ZZZZ", client_id="T")
    result = await eng.submit_order(order)
    assert order.status is OrderStatus.REJECTED
    assert result.trades == []


async def test_reject_invalid_tick() -> None:
    eng = _engine()
    order = _order(Side.BUY, 1, "150.005", client_id="T")  # not a multiple of 0.01
    await eng.submit_order(order)
    assert order.status is OrderStatus.REJECTED


async def test_reject_invalid_lot() -> None:
    eng = _engine()
    order = _order(Side.BUY, "0.0005", 100, symbol="BTC-USD", client_id="T")
    await eng.submit_order(order)
    assert order.status is OrderStatus.REJECTED


async def test_valid_fractional_lot_accepted() -> None:
    eng = _engine()
    order = _order(Side.BUY, "0.002", 100, symbol="BTC-USD", client_id="T")
    await eng.submit_order(order)
    assert order.status is OrderStatus.ACCEPTED  # resting, no crossing liquidity


def test_instrument_currency_is_normalized_and_rejects_non_codes() -> None:
    instrument = Instrument(
        symbol="SAP",
        name="SAP SE",
        instrument_type=InstrumentType.EQUITY,
        tick_size="0.01",
        currency=" eur ",
    )
    assert instrument.currency == "EUR"

    with pytest.raises(ValueError, match="three-letter ASCII"):
        Instrument(
            symbol="SAP",
            name="SAP SE",
            instrument_type=InstrumentType.EQUITY,
            tick_size="0.01",
            currency="€€€",
        )


async def test_reject_bare_stop_order() -> None:
    eng = _engine()
    order = _order(Side.BUY, 1, order_type=OrderType.STOP, stop_price=100, client_id="T")
    result = await eng.submit_order(order)
    assert order.status is OrderStatus.REJECTED
    assert result.trades == []


# ---------------------------------------------------------------------------
# Event delivery (callback subscribed after start) + replay
# ---------------------------------------------------------------------------


async def test_callback_delivery_after_start() -> None:
    bus = EventBus()
    eng = MatchingEngine(event_bus=bus, instruments=_instruments())
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    await bus.start()
    bus.subscribe({EventType.ORDER_ACCEPTED, EventType.TRADE_EXECUTED}, handler)

    await eng.submit_order(_order(Side.SELL, 5, 100, client_id="M"))
    await eng.submit_order(_order(Side.BUY, 5, 100, client_id="T"))
    await bus.stop()  # drains queued events before returning

    types = {e.event_type for e in received}
    assert EventType.ORDER_ACCEPTED in types
    assert EventType.TRADE_EXECUTED in types


async def test_engine_bus_replay() -> None:
    eng = _engine()
    await eng.submit_order(_order(Side.SELL, 5, 100, client_id="M"))
    await eng.submit_order(_order(Side.BUY, 5, 100, client_id="T"))
    accepted = eng._event_bus.replay(event_types={EventType.ORDER_ACCEPTED})
    filled = eng._event_bus.replay(event_types={EventType.ORDER_FILLED})
    assert len(accepted) == 2
    # Both the incoming taker and the fully-consumed resting maker are filled.
    assert len(filled) == 2


def test_event_log_bounded_replay() -> None:
    log = EventLog(max_size=3)
    seqs = [log.append(DomainEvent(event_type=EventType.SYSTEM_STATUS)) for _ in range(5)]
    assert seqs == [0, 1, 2, 3, 4]
    assert log.size == 3
    assert log.base_sequence == 2
    # Replaying from 0 clamps to the oldest retained event (seq 2).
    assert len(log.replay(0)) == 3
    # Replaying from a later sequence returns only newer events.
    assert len(log.replay(4)) == 1


# ---------------------------------------------------------------------------
# Position accounting: long / short / crossing
# ---------------------------------------------------------------------------


def test_long_position_realized_and_unrealized() -> None:
    pos = Position(client_id="c", symbol="AAPL")
    pos.apply_fill(Side.BUY, D("10"), D("100"))
    assert pos.quantity == D("10")
    assert pos.average_entry_price == D("100")
    realised = pos.apply_fill(Side.SELL, D("4"), D("110"))
    assert realised == D("40")
    assert pos.realized_pnl == D("40")
    assert pos.quantity == D("6")
    assert pos.average_entry_price == D("100")
    pos.mark_to_market(D("110"))
    assert pos.unrealized_pnl == D("60")  # (110-100)*6


def test_short_position_realized_pnl() -> None:
    pos = Position(client_id="c", symbol="AAPL")
    pos.apply_fill(Side.SELL, D("10"), D("100"))
    assert pos.quantity == D("-10")
    realised = pos.apply_fill(Side.BUY, D("4"), D("90"))
    assert realised == D("40")  # covered 4 @ 90 vs avg 100
    assert pos.quantity == D("-6")
    assert pos.average_entry_price == D("100")
    pos.mark_to_market(D("90"))
    assert pos.unrealized_pnl == D("60")  # (90-100)*-6


def test_position_average_price_on_increase() -> None:
    pos = Position(client_id="c", symbol="AAPL")
    pos.apply_fill(Side.BUY, D("10"), D("100"))
    pos.apply_fill(Side.BUY, D("10"), D("120"))
    assert pos.quantity == D("20")
    assert pos.average_entry_price == D("110")


def test_position_crossing_through_zero() -> None:
    pos = Position(client_id="c", symbol="AAPL")
    pos.apply_fill(Side.BUY, D("5"), D("100"))
    realised = pos.apply_fill(Side.SELL, D("8"), D("110"))
    assert realised == D("50")  # closed 5 @ +10
    assert pos.quantity == D("-3")  # flipped short
    assert pos.average_entry_price == D("110")  # remainder opens at fill price


async def test_engine_updates_both_sides_positions() -> None:
    eng = _engine()
    await eng.submit_order(_order(Side.SELL, 5, 100, client_id="seller"))
    await eng.submit_order(_order(Side.BUY, 5, 100, client_id="buyer"))
    buyer = eng.position_manager.get_position("buyer", "AAPL")
    seller = eng.position_manager.get_position("seller", "AAPL")
    assert buyer.quantity == D("5")
    assert seller.quantity == D("-5")
    assert eng.position_manager.get_positions("buyer")["AAPL"].quantity == D("5")


# ---------------------------------------------------------------------------
# Resting (maker) order finalization
# ---------------------------------------------------------------------------


async def test_resting_order_partial_fill_status_and_event() -> None:
    eng = _engine()
    maker = _order(Side.SELL, 10, 100, client_id="M")
    await eng.submit_order(maker)
    await eng.submit_order(_order(Side.BUY, 4, 100, client_id="T"))

    # Resting order state updated in place.
    assert maker.status is OrderStatus.PARTIALLY_FILLED
    assert maker.filled_quantity == D("4")
    assert maker.updated_at is not None
    # Exactly one partial-fill lifecycle event for the resting order.
    maker_events = [
        e.event_type
        for e in _events_for(eng, maker.order_id)
        if e.event_type in (EventType.ORDER_PARTIALLY_FILLED, EventType.ORDER_FILLED)
    ]
    assert maker_events == [EventType.ORDER_PARTIALLY_FILLED]


async def test_resting_order_full_fill_status_and_event() -> None:
    eng = _engine()
    maker = _order(Side.SELL, 5, 100, client_id="M")
    await eng.submit_order(maker)
    await eng.submit_order(_order(Side.BUY, 5, 100, client_id="T"))

    assert maker.status is OrderStatus.FILLED
    assert maker.updated_at is not None
    maker_fill_events = [
        e.event_type
        for e in _events_for(eng, maker.order_id)
        if e.event_type in (EventType.ORDER_PARTIALLY_FILLED, EventType.ORDER_FILLED)
    ]
    # Consumed in a single fill -> exactly one ORDER_FILLED, no partial.
    assert maker_fill_events == [EventType.ORDER_FILLED]


async def test_risk_check_receives_none_position_and_creates_none() -> None:
    seen: list[Position | None] = []

    class _Recorder:
        def can_execute(self, order, position):
            seen.append(position)
            return False, "no"

    eng = _engine(risk_check=_Recorder())
    await eng.submit_order(_order(Side.BUY, 5, 100, client_id="fresh"))
    # The check saw None (no pre-existing position) and none was stored.
    assert seen == [None]
    assert eng.position_manager.peek_position("fresh", "AAPL") is None
    assert eng.position_manager.all_positions() == []


# ---------------------------------------------------------------------------
# Aware-UTC timestamp enforcement
# ---------------------------------------------------------------------------

_PLUS2 = timezone(timedelta(hours=2))


def test_defaults_are_aware_utc() -> None:
    order = _order(Side.BUY, 1, 100)
    assert order.created_at.tzinfo == UTC
    trade = Trade(
        symbol="AAPL",
        buy_order_id="b",
        sell_order_id="s",
        price=D("100"),
        quantity=D("1"),
        buyer_client_id="b",
        seller_client_id="s",
        aggressor_side=Side.BUY,
    )
    assert trade.timestamp.tzinfo == UTC
    assert Tick("AAPL", D("1"), D("2"), D("1.5"), 10).timestamp.tzinfo == UTC
    assert DomainEvent().timestamp.tzinfo == UTC


def test_order_normalizes_aware_offset_to_utc() -> None:
    naive_wall = datetime(2026, 1, 1, 12, 0, 0)
    order = Order(
        client_id="c",
        symbol="AAPL",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=D("1"),
        price=D("100"),
        created_at=naive_wall.replace(tzinfo=_PLUS2),
    )
    assert order.created_at.tzinfo == UTC
    assert order.created_at == datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)


def test_order_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        Order(
            client_id="c",
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=D("1"),
            price=D("100"),
            created_at=datetime(2026, 1, 1, 12, 0, 0),  # naive
        )


def test_trade_and_position_reject_naive_and_normalize() -> None:
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=_PLUS2)
    trade = Trade(
        symbol="AAPL",
        buy_order_id="b",
        sell_order_id="s",
        price=D("100"),
        quantity=D("1"),
        buyer_client_id="b",
        seller_client_id="s",
        aggressor_side=Side.BUY,
        timestamp=ts,
    )
    assert trade.timestamp == datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        Position(client_id="c", symbol="AAPL", last_updated=datetime(2026, 1, 1))
    snap = PortfolioSnapshot(client_id="c", timestamp=ts)
    assert snap.timestamp.tzinfo == UTC
    metrics = RiskMetrics(computed_at=ts)
    assert metrics.computed_at.tzinfo == UTC


def test_tick_and_event_reject_naive() -> None:
    with pytest.raises(ValueError):
        Tick("AAPL", D("1"), D("2"), D("1.5"), 10, timestamp=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        DomainEvent(timestamp=datetime(2026, 1, 1))
    # Aware offset is normalized to UTC.
    ev = DomainEvent(timestamp=datetime(2026, 1, 1, 12, tzinfo=_PLUS2))
    assert ev.timestamp == datetime(2026, 1, 1, 10, tzinfo=UTC)


@pytest.mark.parametrize(
    ("bid", "ask", "last", "volume", "message"),
    [
        ("2", "1", "1.5", 10, "bid must not exceed ask"),
        ("0", "1", "0.5", 10, "finite and positive"),
        ("1", "2", "1.5", -1, "non-negative integer"),
        ("1", "2", "1.5", True, "non-negative integer"),
    ],
)
def test_tick_rejects_invalid_market_data(
    bid: str,
    ask: str,
    last: str,
    volume: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        Tick("AAPL", D(bid), D(ask), D(last), volume)


# ---------------------------------------------------------------------------
# Honest DAY / GTD rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tif", [TimeInForce.DAY, TimeInForce.GTD])
async def test_day_and_gtd_rejected(tif: TimeInForce) -> None:
    eng = _engine()
    order = _order(Side.BUY, 1, 100, tif=tif, client_id="T")
    result = await eng.submit_order(order)
    assert order.status is OrderStatus.REJECTED
    assert result.trades == []
    reason = _events_for(eng, order.order_id)[-1].payload["reason"]
    assert "session" in reason or "expiry" in reason
    # Nothing rested.
    book = eng.get_book("AAPL")
    assert book is None or book.total_orders == 0


# ---------------------------------------------------------------------------
# Lifecycle boundaries: updated_at, non-NEW, duplicate order id
# ---------------------------------------------------------------------------


async def test_updated_at_set_on_accept_and_reject() -> None:
    eng = _engine()
    resting = _order(Side.BUY, 1, 99, client_id="T")
    await eng.submit_order(resting)
    assert resting.status is OrderStatus.ACCEPTED
    assert resting.updated_at is not None
    assert resting.updated_at.tzinfo == UTC

    bad = _order(Side.BUY, 1, 100, symbol="ZZZZ", client_id="T")
    await eng.submit_order(bad)
    assert bad.status is OrderStatus.REJECTED
    assert bad.updated_at is not None


async def test_non_new_order_rejected() -> None:
    eng = _engine()
    order = _order(Side.BUY, 1, 100, client_id="T")
    order.status = OrderStatus.ACCEPTED  # pretend it was already processed
    result = await eng.submit_order(order)
    assert order.status is OrderStatus.REJECTED
    assert result.trades == []
    assert "only NEW" in _events_for(eng, order.order_id)[-1].payload["reason"]


async def test_duplicate_same_object_resubmission_raises_and_preserves_original() -> None:
    eng = _engine()
    resting = _order(Side.BUY, 5, 99, client_id="T")
    await eng.submit_order(resting)
    assert resting.status is OrderStatus.ACCEPTED

    with pytest.raises(DuplicateOrderError) as excinfo:
        await eng.submit_order(resting)  # same object, already resting
    assert excinfo.value.order_id == resting.order_id
    # Original is untouched: still ACCEPTED, unfilled, still on the book.
    assert resting.status is OrderStatus.ACCEPTED
    assert resting.filled_quantity == D("0")
    book = eng.get_book("AAPL")
    assert book is not None
    assert book.total_orders == 1


async def test_duplicate_distinct_object_same_id_raises() -> None:
    eng = _engine()
    first = _order(Side.BUY, 5, 99, client_id="T")
    await eng.submit_order(first)
    clone = Order(
        order_id=first.order_id,
        client_id="T",
        symbol="AAPL",
        side=Side.SELL,
        order_type=OrderType.LIMIT,
        quantity=D("5"),
        price=D("101"),
    )
    with pytest.raises(DuplicateOrderError):
        await eng.submit_order(clone)
    # The distinct clone is not mutated by the engine.
    assert clone.status is OrderStatus.NEW
    assert first.status is OrderStatus.ACCEPTED


# ---------------------------------------------------------------------------
# EventBus configuration & subscriber-id hardening
# ---------------------------------------------------------------------------


def test_event_bus_rejects_bad_max_queue() -> None:
    with pytest.raises(ValueError):
        EventBus(max_queue=0)
    with pytest.raises(ValueError):
        EventBus(max_queue=-5)
    with pytest.raises(TypeError):
        EventBus(max_queue=True)  # bool is not a valid int here


async def test_duplicate_callback_subscriber_id_rejected_without_orphaning() -> None:
    bus = EventBus()
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    await bus.start()
    bus.subscribe(set(), handler, subscriber_id="dup")
    task = bus._dispatch_tasks["dup"]

    with pytest.raises(ValueError):
        bus.subscribe(set(), handler, subscriber_id="dup")
    # Original subscription and its dispatch task are intact (not orphaned).
    assert len(bus._subscriptions) == 1
    assert bus._dispatch_tasks["dup"] is task
    assert not task.cancelled()

    await bus.publish(DomainEvent(event_type=EventType.SYSTEM_STATUS))
    await bus.stop()
    assert len(received) == 1


async def test_duplicate_stream_subscriber_id_rejected() -> None:
    bus = EventBus()

    async def handler(event: DomainEvent) -> None:  # pragma: no cover - not invoked
        return None

    bus.subscribe(set(), handler, subscriber_id="s")
    gen = bus.stream(set(), subscriber_id="s")
    with pytest.raises(ValueError):
        await gen.__anext__()
    assert len(bus._subscriptions) == 1


# ---------------------------------------------------------------------------
# Concurrent same-id submission race & id-reuse-after-rejection
# ---------------------------------------------------------------------------


async def test_concurrent_same_id_submissions_only_one_proceeds() -> None:
    eng = _engine()
    oid = "race-1"
    first = Order(
        order_id=oid,
        client_id="T",
        symbol="AAPL",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=D("5"),
        price=D("99"),
    )
    # A distinct object carrying the same id, submitted concurrently.
    second = Order(
        order_id=oid,
        client_id="T",
        symbol="AAPL",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=D("3"),
        price=D("98"),
    )
    results = await asyncio.gather(
        eng.submit_order(first),
        eng.submit_order(second),
        return_exceptions=True,
    )
    dupes = [r for r in results if isinstance(r, DuplicateOrderError)]
    oks = [r for r in results if isinstance(r, OrderSubmission)]
    assert len(dupes) == 1
    assert len(oks) == 1
    assert dupes[0].order_id == oid

    winner = oks[0].order
    assert winner.status is OrderStatus.ACCEPTED
    # Exactly one order rested — no duplicate book entry from the loser.
    book = eng.get_book("AAPL")
    assert book is not None
    assert book.total_orders == 1

    # The loser emitted no lifecycle events: exactly one SUBMITTED/ACCEPTED
    # exists for the id, both belonging to the winner.
    events = _events_for(eng, oid)
    submitted = [e for e in events if e.event_type is EventType.ORDER_SUBMITTED]
    accepted = [e for e in events if e.event_type is EventType.ORDER_ACCEPTED]
    assert len(submitted) == 1
    assert len(accepted) == 1


async def test_id_from_rejected_submission_is_not_reusable() -> None:
    eng = _engine()
    oid = "reuse-1"
    rejected = Order(
        order_id=oid,
        client_id="T",
        symbol="ZZZZ",  # unknown instrument -> boundary rejection
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=D("1"),
        price=D("100"),
    )
    result = await eng.submit_order(rejected)
    assert rejected.status is OrderStatus.REJECTED
    assert result.trades == []

    # The id is known permanently even though the submission was rejected.
    reuse = Order(
        order_id=oid,
        client_id="T",
        symbol="AAPL",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=D("1"),
        price=D("100"),
    )
    with pytest.raises(DuplicateOrderError):
        await eng.submit_order(reuse)
    # The reuse attempt was not processed at all.
    assert reuse.status is OrderStatus.NEW


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))

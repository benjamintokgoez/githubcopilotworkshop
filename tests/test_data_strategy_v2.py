"""Focused tests for deterministic market data, transforms, and strategies."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
import websockets

from qxm.core.events import DomainEvent, EventBus, EventType
from qxm.core.models import Instrument, OrderType, Side, Tick
from qxm.data.feed import MarketDataFeed, WebSocketFeedAdapter
from qxm.data.transform import (
    compute_returns,
    compute_volatility,
    exponential_moving_average,
    normalise_prices,
    rolling_mean,
    rolling_std,
    ticks_to_ohlc,
)
from qxm.strategy import (
    BollingerMeanReversion,
    EMACrossover,
    MomentumBreakout,
    Signal,
    SignalStrength,
    StatisticalArbitrage,
    StrategyMeta,
)


class RecordingEventBus(EventBus):
    """Event bus that records publications without relying on dispatch tasks."""

    def __init__(self) -> None:
        super().__init__(persist=False)
        self.events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


class FakeWebSocket:
    """Finite async WebSocket stream for adapter lifecycle tests."""

    def __init__(self, messages: list[str] | None = None) -> None:
        self._messages = iter(messages or [])
        self.sent: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    def __aiter__(self) -> FakeWebSocket:
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._messages)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket

    async def __aenter__(self) -> FakeWebSocket:
        return self.websocket

    async def __aexit__(self, *_args: object) -> None:
        return None


class FakeConnectFactory:
    def __init__(self, messages: list[str] | None = None) -> None:
        self.messages = messages or []
        self.calls = 0
        self.sockets: list[FakeWebSocket] = []

    def __call__(self, _url: str) -> FakeConnection:
        self.calls += 1
        websocket = FakeWebSocket(list(self.messages))
        self.sockets.append(websocket)
        return FakeConnection(websocket)


def make_tick(
    symbol: str,
    price: float,
    timestamp: datetime,
    *,
    volume: int = 100,
) -> Tick:
    value = Decimal(str(price))
    return Tick(
        symbol=symbol,
        bid=value - Decimal("0.01"),
        ask=value + Decimal("0.01"),
        last=value,
        volume=volume,
        timestamp=timestamp,
    )


@pytest.mark.asyncio
async def test_feed_start_generation_stop_and_events() -> None:
    bus = RecordingEventBus()
    feed = MarketDataFeed(bus, ["AAPL"], tick_interval=60.0, seed=7)

    await feed.start()
    stream = feed.generate_ticks()
    tick = await anext(stream)

    assert feed.is_running
    assert tick.timestamp.tzinfo is not None
    assert tick.timestamp.utcoffset() == UTC.utcoffset(tick.timestamp)
    assert feed.get_latest_tick("AAPL") is tick
    assert bus.events[0].event_type == EventType.MARKET_DATA_TICK
    assert bus.events[0].payload["timestamp"].endswith("+00:00")

    pending_tick = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    await feed.stop()

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(pending_tick, timeout=0.5)
    assert not feed.is_running


@pytest.mark.asyncio
async def test_feed_prices_are_deterministic_with_seed() -> None:
    first = MarketDataFeed(RecordingEventBus(), ["UNKNOWN", "AAPL"], tick_interval=0, seed=11)
    second = MarketDataFeed(RecordingEventBus(), ["UNKNOWN", "AAPL"], tick_interval=0, seed=11)
    await first.start()
    await second.start()

    first_stream = first.generate_ticks()
    second_stream = second.generate_ticks()
    first_ticks = [await anext(first_stream), await anext(first_stream)]
    second_ticks = [await anext(second_stream), await anext(second_stream)]

    assert [(tick.symbol, tick.bid, tick.ask, tick.last, tick.volume) for tick in first_ticks] == [
        (tick.symbol, tick.bid, tick.ask, tick.last, tick.volume) for tick in second_ticks
    ]
    await first.stop()
    await second.stop()


def test_external_timestamps_reject_naive_and_normalize_offsets(
    instruments: dict[str, Instrument],
) -> None:
    adapter = WebSocketFeedAdapter("wss://example.invalid", ["AAPL"], RecordingEventBus())
    tick_data: dict[str, Any] = {
        "symbol": "AAPL",
        "bid": "99.99",
        "ask": "100.01",
        "last": "100",
        "volume": 10,
        "timestamp": "2026-08-19T12:00:00+02:00",
    }

    tick = adapter._parse_tick(tick_data)
    assert tick is not None
    assert tick.timestamp == datetime(2026, 8, 19, 10, tzinfo=UTC)

    tick_data["timestamp"] = "2026-08-19T12:00:00"
    assert adapter._parse_tick(tick_data) is None

    aware_signal = Signal(
        instrument=instruments["AAPL"],
        strength=SignalStrength.NEUTRAL,
        timestamp=datetime(
            2026,
            8,
            19,
            12,
            tzinfo=timezone(timedelta(hours=2)),
        ),
    )
    assert aware_signal.timestamp == datetime(2026, 8, 19, 10, tzinfo=UTC)
    with pytest.raises(ValueError, match="explicit timezone"):
        Signal(
            instrument=instruments["AAPL"],
            strength=SignalStrength.NEUTRAL,
            timestamp=datetime(2026, 8, 19, 12),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("symbol", 123),
        ("volume", 1.5),
        ("volume", True),
        ("volume", -1),
        ("bid", "101"),
    ],
)
def test_websocket_rejects_malformed_market_data(field: str, value: object) -> None:
    adapter = WebSocketFeedAdapter("wss://example.invalid", ["AAPL"], RecordingEventBus())
    tick_data: dict[str, Any] = {
        "symbol": "AAPL",
        "bid": "99.99",
        "ask": "100.01",
        "last": "100",
        "volume": 10,
        "timestamp": "2026-08-19T12:00:00Z",
    }
    tick_data[field] = value

    assert adapter._parse_tick(tick_data) is None


@pytest.mark.asyncio
async def test_websocket_clean_close_waits_before_reconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = FakeConnectFactory()
    monkeypatch.setattr(websockets, "connect", factory)
    adapter = WebSocketFeedAdapter(
        "wss://example.invalid",
        ["AAPL"],
        RecordingEventBus(),
        reconnect_delay=60,
    )

    connection_task = asyncio.create_task(adapter.connect())
    for _ in range(5):
        await asyncio.sleep(0)

    assert factory.calls == 1
    await adapter.disconnect()
    await asyncio.wait_for(connection_task, timeout=0.5)


@pytest.mark.asyncio
async def test_websocket_ignores_unsubscribed_symbols(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    messages = [
        json.dumps(
            {
                "symbol": "MSFT",
                "bid": "199.99",
                "ask": "200.01",
                "timestamp": "2026-08-19T10:00:00Z",
            }
        ),
        json.dumps(
            {
                "symbol": "AAPL",
                "bid": "99.99",
                "ask": "100.01",
                "timestamp": "2026-08-19T10:00:01Z",
            }
        ),
    ]
    factory = FakeConnectFactory(messages)
    monkeypatch.setattr(websockets, "connect", factory)
    bus = RecordingEventBus()
    adapter = WebSocketFeedAdapter(
        "wss://example.invalid",
        ["AAPL"],
        bus,
        reconnect_delay=60,
    )

    with caplog.at_level(logging.WARNING):
        connection_task = asyncio.create_task(adapter.connect())
        for _ in range(5):
            await asyncio.sleep(0)
        await adapter.disconnect()
        await asyncio.wait_for(connection_task, timeout=0.5)

    assert [event.payload["symbol"] for event in bus.events] == ["AAPL"]
    assert "unsubscribed symbol MSFT" in caplog.text


def test_ohlc_sorts_separates_symbols_and_aligns_long_buckets() -> None:
    ticks = [
        make_tick("AAPL", 103, datetime(2026, 8, 20, 0, 0, 15, tzinfo=UTC)),
        make_tick("MSFT", 200, datetime(2026, 8, 19, 23, 59, 40, tzinfo=UTC)),
        make_tick("AAPL", 101, datetime(2026, 8, 19, 23, 59, 30, tzinfo=UTC)),
        make_tick("AAPL", 102, datetime(2026, 8, 19, 23, 59, 50, tzinfo=UTC)),
    ]

    bars = ticks_to_ohlc(ticks, interval_seconds=120)

    assert [(bar["symbol"], bar["open"], bar["close"]) for bar in bars] == [
        ("AAPL", 101.0, 102.0),
        ("MSFT", 200.0, 200.0),
        ("AAPL", 103.0, 103.0),
    ]
    assert bars[0]["timestamp"] == datetime(2026, 8, 19, 23, 58, tzinfo=UTC)
    assert bars[2]["timestamp"] == datetime(2026, 8, 20, 0, 0, tzinfo=UTC)


def test_ohlc_rejects_naive_timestamps_and_normalizes_offsets() -> None:
    naive_tick = object.__new__(Tick)
    naive_tick.symbol = "AAPL"
    naive_tick.bid = Decimal("99.99")
    naive_tick.ask = Decimal("100.01")
    naive_tick.last = Decimal("100")
    naive_tick.volume = 100
    naive_tick.timestamp = datetime(2026, 8, 19, 10)
    with pytest.raises(ValueError, match="explicit timezone"):
        ticks_to_ohlc([naive_tick])

    offset = timezone(timedelta(hours=2))
    bars = ticks_to_ohlc(
        [make_tick("AAPL", 100, datetime(2026, 8, 19, 12, tzinfo=offset))],
    )
    assert bars[0]["timestamp"] == datetime(2026, 8, 19, 10, tzinfo=UTC)


def test_transform_edge_cases_are_defined() -> None:
    assert compute_returns([]).size == 0
    assert compute_returns([100.0]).size == 0
    assert compute_volatility(np.array([])) == 0.0
    assert compute_volatility(np.array([0.01])) == 0.0
    assert normalise_prices([]).size == 0
    np.testing.assert_array_equal(normalise_prices([5.0], "zscore"), [0.0])
    np.testing.assert_array_equal(rolling_std([1.0, 2.0], 1), [0.0, 0.0])
    assert rolling_mean([], 2).size == 0
    assert exponential_moving_average([], 2).size == 0

    with pytest.raises(ValueError, match="strictly positive"):
        compute_returns([100.0, 0.0])
    with pytest.raises(ValueError, match="strictly positive"):
        normalise_prices([100.0, -1.0], "returns")
    with pytest.raises(ValueError, match="positive integer"):
        rolling_mean([1.0], 0)
    with pytest.raises(ValueError, match="positive integer"):
        exponential_moving_average([1.0], -1)
    with pytest.raises(ValueError, match="positive integer"):
        ticks_to_ohlc([], interval_seconds=0)


def test_registry_discovers_only_concrete_strategies_predictably() -> None:
    expected = [
        "BollingerMeanReversion",
        "EMACrossover",
        "MomentumBreakout",
        "StatisticalArbitrage",
    ]
    assert StrategyMeta.list_strategies() == expected
    assert StrategyMeta.get("MomentumBreakout") is MomentumBreakout
    with pytest.raises(KeyError, match="Available"):
        StrategyMeta.get("missing")


def test_order_factory_infers_type_and_rejects_unknown_symbols(
    instruments: dict[str, Instrument],
) -> None:
    strategy = MomentumBreakout([instruments["AAPL"]])

    market_order = strategy.create_order("aapl", Side.BUY, 10)
    assert market_order.symbol == "AAPL"
    assert market_order.order_type == OrderType.MARKET
    assert market_order.price is None

    limit_order = strategy.create_order("AAPL", Side.SELL, 5, price=101.5)
    assert limit_order.order_type == OrderType.LIMIT
    assert limit_order.price == Decimal("101.5")

    explicit_market = strategy.create_order(
        "AAPL",
        Side.BUY,
        1,
        order_type=OrderType.MARKET,
    )
    assert explicit_market.order_type == OrderType.MARKET

    with pytest.raises(ValueError, match="not configured"):
        strategy.create_order("MSFT", Side.BUY, 1)
    with pytest.raises(ValueError, match="not configured"):
        strategy.on_tick(
            make_tick(
                "MSFT",
                100,
                datetime(2026, 8, 19, tzinfo=UTC),
            )
        )


def test_integer_strategy_parameters_are_strict(
    instruments: dict[str, Instrument],
) -> None:
    with pytest.raises(ValueError, match="lookback must be an integer"):
        MomentumBreakout([instruments["AAPL"]], {"lookback": True})
    with pytest.raises(ValueError, match="fast_span must be an integer"):
        EMACrossover([instruments["AAPL"]], {"fast_span": 2.5})
    with pytest.raises(ValueError, match="window must be an integer"):
        BollingerMeanReversion([instruments["AAPL"]], {"window": 20.0})
    with pytest.raises(ValueError, match="lookback must be an integer"):
        StatisticalArbitrage(
            [instruments["AAPL"], instruments["MSFT"]],
            {"lookback": False},
        )


def test_momentum_and_ema_signals_can_trigger(
    instruments: dict[str, Instrument],
) -> None:
    start = datetime(2026, 8, 19, tzinfo=UTC)
    momentum = MomentumBreakout(
        [instruments["AAPL"]],
        {"lookback": 3, "min_ticks": 4, "atr_multiplier": 1.0},
    )
    for index, price in enumerate([100.0, 101.0, 100.5, 110.0]):
        momentum.on_tick(make_tick("AAPL", price, start.replace(second=index)))

    momentum_signals = momentum.generate_signals()
    assert len(momentum_signals) == 1
    assert momentum_signals[0].strength in {SignalStrength.BUY, SignalStrength.STRONG_BUY}
    assert momentum_signals[0].metadata["channel_upper"] == 101.0

    ema = EMACrossover(
        [instruments["AAPL"]],
        {"fast_span": 2, "slow_span": 3},
    )
    for index, price in enumerate([100.0, 100.0, 100.0, 110.0]):
        ema.on_tick(make_tick("AAPL", price, start.replace(second=index)))

    ema_signals = ema.generate_signals()
    assert len(ema_signals) == 1
    assert ema_signals[0].strength == SignalStrength.BUY


def test_mean_reversion_and_pair_signals_can_trigger(
    instruments: dict[str, Instrument],
) -> None:
    start = datetime(2026, 8, 19, tzinfo=UTC)
    bollinger = BollingerMeanReversion(
        [instruments["AAPL"]],
        {"window": 3, "min_ticks": 4, "num_std": 2.0},
    )
    for index, price in enumerate([99.0, 100.0, 101.0, 104.0]):
        bollinger.on_tick(make_tick("AAPL", price, start.replace(second=index)))

    bollinger_signals = bollinger.generate_signals()
    assert len(bollinger_signals) == 1
    assert bollinger_signals[0].strength == SignalStrength.SELL

    pairs = StatisticalArbitrage(
        [instruments["AAPL"], instruments["MSFT"]],
        {
            "pair": ("AAPL", "MSFT"),
            "lookback": 3,
            "entry_z": 1.5,
            "exit_z": 0.25,
        },
    )
    for index, (price_a, price_b) in enumerate(
        [(100.0, 100.0), (102.0, 100.0), (101.0, 100.0), (120.0, 100.0)]
    ):
        timestamp = start.replace(second=index)
        pairs.on_tick(make_tick("AAPL", price_a, timestamp))
        pairs.on_tick(make_tick("MSFT", price_b, timestamp))

    pair_signals = pairs.generate_signals()
    assert [signal.strength for signal in pair_signals] == [
        SignalStrength.SELL,
        SignalStrength.BUY,
    ]

    for signal in bollinger_signals + pair_signals:
        assert 0.0 <= signal.confidence <= 1.0
        json.dumps(signal.metadata, allow_nan=False)

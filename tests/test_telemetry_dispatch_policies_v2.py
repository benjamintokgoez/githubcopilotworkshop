"""Focused tests for deterministic telemetry, transforms, storage, and dispatch policies."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
import websockets
from sqlalchemy.exc import IntegrityError

from mittelwerk.core.events import DispatchEventType, DomainEvent, EventBus
from mittelwerk.core.models import (
    DispatchSide,
    DispatchWindow,
    Equipment,
    EquipmentCategory,
    TelemetryReading,
    WorkOrderMode,
)
from mittelwerk.dispatch_policies.base import (
    DispatchPolicyMeta,
    Recommendation,
    RecommendationUrgency,
)
from mittelwerk.dispatch_policies.telemetry_deviation import (
    CrossAssetTelemetryImbalance,
    TelemetryBandDeviation,
)
from mittelwerk.dispatch_policies.threshold import CapacityBreach, TelemetryTrendCrossover
from mittelwerk.telemetry.feed import TelemetryFeed, WebSocketFeedAdapter
from mittelwerk.telemetry.store import (
    MAX_QUERY_LIMIT,
    MAX_SEARCH_QUERY_LENGTH,
    WORK_ORDER_ID_COLUMN_LENGTH,
    AssignmentRecord,
    TelemetryStore,
)
from mittelwerk.telemetry.transform import (
    compute_average,
    compute_deltas,
    compute_variability,
    compute_weighted_average,
    exponential_moving_average,
    normalise_readings,
    readings_to_intervals,
    rolling_mean,
    rolling_std,
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


@pytest.fixture
def store() -> Iterator[TelemetryStore]:
    store = TelemetryStore("sqlite://")
    try:
        yield store
    finally:
        store.close()


@pytest.fixture
def equipment() -> dict[str, Equipment]:
    return {
        "CNC-01": make_equipment("CNC-01", "Fräszentrum 1", EquipmentCategory.CNC_MACHINE),
        "PRESS-04": make_equipment(
            "PRESS-04", "Hydraulikpresse 4", EquipmentCategory.HYDRAULIC_PRESS
        ),
        "ROBOT-07": make_equipment("ROBOT-07", "Roboterzelle 7", EquipmentCategory.ROBOTIC_ARM),
    }


def make_equipment(
    asset_id: str,
    name: str,
    equipment_type: EquipmentCategory,
) -> Equipment:
    return Equipment(
        asset_id=asset_id,
        name=name,
        equipment_type=equipment_type,
        service_interval_days=30,
        hourly_service_rate="125.50",
        rate_increment="0.50",
        hour_lot_size="0.25",
        currency="EUR",
        site_code="MW-BER-1",
    )


def make_reading(
    asset_id: str,
    value: float,
    timestamp: datetime,
    *,
    sample_count: int = 100,
    spread: float = 0.2,
) -> TelemetryReading:
    return TelemetryReading(
        asset_id=asset_id,
        min_reading=Decimal(str(value - spread / 2.0)),
        max_reading=Decimal(str(value + spread / 2.0)),
        last_reading=Decimal(str(value)),
        sample_count=sample_count,
        timestamp=timestamp,
    )


@pytest.mark.asyncio
async def test_feed_start_generation_stop_and_events() -> None:
    bus = RecordingEventBus()
    feed = TelemetryFeed(bus, ["CNC-01"], tick_interval=60.0, seed=7)

    await feed.start()
    stream = feed.generate_readings()
    reading = await anext(stream)

    assert feed.is_running
    assert reading.timestamp.tzinfo is not None
    assert reading.timestamp.utcoffset() == UTC.utcoffset(reading.timestamp)
    assert feed.get_latest_reading("CNC-01") is reading
    assert bus.events[0].event_type == DispatchEventType.TELEMETRY_READING
    assert bus.events[0].payload["timestamp"].endswith("+00:00")

    pending_reading = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    await feed.stop()

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(pending_reading, timeout=0.5)
    assert not feed.is_running


@pytest.mark.asyncio
async def test_feed_readings_are_deterministic_with_seed() -> None:
    first = TelemetryFeed(RecordingEventBus(), ["UNKNOWN", "CNC-01"], tick_interval=0, seed=11)
    second = TelemetryFeed(RecordingEventBus(), ["UNKNOWN", "CNC-01"], tick_interval=0, seed=11)
    await first.start()
    await second.start()

    first_stream = first.generate_readings()
    second_stream = second.generate_readings()
    first_readings = [await anext(first_stream), await anext(first_stream)]
    second_readings = [await anext(second_stream), await anext(second_stream)]

    assert [
        (
            reading.asset_id,
            reading.min_reading,
            reading.max_reading,
            reading.last_reading,
            reading.sample_count,
        )
        for reading in first_readings
    ] == [
        (
            reading.asset_id,
            reading.min_reading,
            reading.max_reading,
            reading.last_reading,
            reading.sample_count,
        )
        for reading in second_readings
    ]
    await first.stop()
    await second.stop()


def test_external_timestamps_reject_naive_and_normalize_offsets(
    equipment: dict[str, Equipment],
) -> None:
    adapter = WebSocketFeedAdapter("wss://example.invalid", ["CNC-01"], RecordingEventBus())
    reading_data: dict[str, Any] = {
        "asset_id": "CNC-01",
        "min_reading": "99.99",
        "max_reading": "100.01",
        "last_reading": "100",
        "sample_count": 10,
        "timestamp": "2026-08-19T12:00:00+02:00",
    }

    reading = adapter._parse_reading(reading_data)
    assert reading is not None
    assert reading.timestamp == datetime(2026, 8, 19, 10, tzinfo=UTC)

    reading_data["timestamp"] = "2026-08-19T12:00:00"
    assert adapter._parse_reading(reading_data) is None

    aware_recommendation = Recommendation(
        asset=equipment["CNC-01"],
        urgency=RecommendationUrgency.ROUTINE,
        timestamp=datetime(2026, 8, 19, 12, tzinfo=timezone(timedelta(hours=2))),
    )
    assert aware_recommendation.timestamp == datetime(2026, 8, 19, 10, tzinfo=UTC)
    with pytest.raises(ValueError, match="explicit timezone"):
        Recommendation(
            asset=equipment["CNC-01"],
            urgency=RecommendationUrgency.ROUTINE,
            timestamp=datetime(2026, 8, 19, 12),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("asset_id", 123),
        ("sample_count", 1.5),
        ("sample_count", True),
        ("sample_count", -1),
        ("min_reading", None),
    ],
)
def test_websocket_rejects_malformed_telemetry(field: str, value: object) -> None:
    adapter = WebSocketFeedAdapter("wss://example.invalid", ["CNC-01"], RecordingEventBus())
    reading_data: dict[str, Any] = {
        "asset_id": "CNC-01",
        "min_reading": "99.99",
        "max_reading": "100.01",
        "last_reading": "100",
        "sample_count": 10,
        "timestamp": "2026-08-19T12:00:00Z",
    }
    reading_data[field] = value

    assert adapter._parse_reading(reading_data) is None


@pytest.mark.asyncio
async def test_websocket_clean_close_waits_before_reconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = FakeConnectFactory()
    monkeypatch.setattr(websockets, "connect", factory)
    adapter = WebSocketFeedAdapter(
        "wss://example.invalid",
        ["CNC-01"],
        RecordingEventBus(),
        reconnect_delay=60,
    )

    connection_task = asyncio.create_task(adapter.connect())
    for _ in range(5):
        await asyncio.sleep(0)

    assert factory.calls == 1
    assert json.loads(factory.sockets[0].sent[0]) == {
        "action": "subscribe",
        "asset_ids": ["CNC-01"],
    }
    await adapter.disconnect()
    await asyncio.wait_for(connection_task, timeout=0.5)


@pytest.mark.asyncio
async def test_websocket_ignores_unsubscribed_assets(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    messages = [
        json.dumps(
            {
                "asset_id": "PRESS-04",
                "min_reading": "199.99",
                "max_reading": "200.01",
                "timestamp": "2026-08-19T10:00:00Z",
            }
        ),
        json.dumps(
            {
                "asset_id": "CNC-01",
                "min_reading": "99.99",
                "max_reading": "100.01",
                "timestamp": "2026-08-19T10:00:01Z",
            }
        ),
    ]
    factory = FakeConnectFactory(messages)
    monkeypatch.setattr(websockets, "connect", factory)
    bus = RecordingEventBus()
    adapter = WebSocketFeedAdapter(
        "wss://example.invalid",
        ["CNC-01"],
        bus,
        reconnect_delay=60,
    )

    with caplog.at_level(logging.WARNING):
        connection_task = asyncio.create_task(adapter.connect())
        for _ in range(5):
            await asyncio.sleep(0)
        await adapter.disconnect()
        await asyncio.wait_for(connection_task, timeout=0.5)

    assert [event.payload["asset_id"] for event in bus.events] == ["CNC-01"]
    assert "unsubscribed asset_id PRESS-04" in caplog.text


def test_interval_aggregation_sorts_separates_assets_and_aligns_long_buckets() -> None:
    readings = [
        make_reading("CNC-01", 103, datetime(2026, 8, 20, 0, 0, 15, tzinfo=UTC)),
        make_reading("PRESS-04", 200, datetime(2026, 8, 19, 23, 59, 40, tzinfo=UTC)),
        make_reading("CNC-01", 101, datetime(2026, 8, 19, 23, 59, 30, tzinfo=UTC)),
        make_reading("CNC-01", 102, datetime(2026, 8, 19, 23, 59, 50, tzinfo=UTC)),
    ]

    bars = readings_to_intervals(readings, interval_seconds=120)

    assert [(bar["asset_id"], bar["open_reading"], bar["close_reading"]) for bar in bars] == [
        ("CNC-01", 101.0, 102.0),
        ("PRESS-04", 200.0, 200.0),
        ("CNC-01", 103.0, 103.0),
    ]
    assert bars[0]["timestamp"] == datetime(2026, 8, 19, 23, 58, tzinfo=UTC)
    assert bars[2]["timestamp"] == datetime(2026, 8, 20, 0, 0, tzinfo=UTC)


def test_interval_aggregation_rejects_naive_timestamps_and_normalizes_offsets() -> None:
    naive_reading = object.__new__(TelemetryReading)
    naive_reading.asset_id = "CNC-01"
    naive_reading.min_reading = Decimal("99.9")
    naive_reading.max_reading = Decimal("100.1")
    naive_reading.last_reading = Decimal("100")
    naive_reading.sample_count = 100
    naive_reading.timestamp = datetime(2026, 8, 19, 10)
    with pytest.raises(ValueError, match="explicit timezone"):
        readings_to_intervals([naive_reading])

    offset = timezone(timedelta(hours=2))
    bars = readings_to_intervals(
        [make_reading("CNC-01", 100, datetime(2026, 8, 19, 12, tzinfo=offset))],
    )
    assert bars[0]["timestamp"] == datetime(2026, 8, 19, 10, tzinfo=UTC)


def test_transform_edge_cases_are_defined() -> None:
    assert compute_deltas([]).size == 0
    assert compute_deltas([100.0]).size == 0
    assert compute_variability(np.array([])) == 0.0
    assert compute_variability(np.array([0.01])) == 0.0
    assert normalise_readings([]).size == 0
    np.testing.assert_array_equal(normalise_readings([5.0], "zscore"), [0.0])
    np.testing.assert_array_equal(rolling_std([1.0, 2.0], 1), [0.0, 0.0])
    assert rolling_mean([], 2).size == 0
    assert exponential_moving_average([], 2).size == 0

    with pytest.raises(ValueError, match="strictly positive"):
        compute_deltas([100.0, 0.0])
    with pytest.raises(ValueError, match="strictly positive"):
        normalise_readings([100.0, -1.0], "deltas")
    with pytest.raises(ValueError, match="positive integer"):
        rolling_mean([1.0], 0)
    with pytest.raises(ValueError, match="positive integer"):
        exponential_moving_average([1.0], -1)
    with pytest.raises(ValueError, match="positive integer"):
        readings_to_intervals([], interval_seconds=0)


def test_weighted_average_average_and_variability_are_computed() -> None:
    start = datetime(2026, 8, 19, tzinfo=UTC)
    readings = [
        make_reading("CNC-01", 100.0, start, sample_count=10),
        make_reading("CNC-01", 110.0, start.replace(second=1), sample_count=30),
    ]

    assert compute_weighted_average(readings) == Decimal("107.500000")
    assert compute_average(readings) == Decimal("105.000000")
    np.testing.assert_allclose(compute_deltas([100.0, 110.0, 121.0], log_deltas=False), [0.1, 0.1])
    assert compute_variability([0.1, -0.1], annualise=False) == pytest.approx(0.1414213562)


def test_registry_discovers_only_concrete_policies_predictably() -> None:
    expected = [
        "CapacityBreach",
        "CrossAssetTelemetryImbalance",
        "TelemetryBandDeviation",
        "TelemetryTrendCrossover",
    ]
    assert DispatchPolicyMeta.list_policies() == expected
    assert DispatchPolicyMeta.get("CapacityBreach") is CapacityBreach
    with pytest.raises(KeyError, match="Available"):
        DispatchPolicyMeta.get("missing")


def test_recommendation_validation_and_actionability(
    equipment: dict[str, Equipment],
) -> None:
    recommendation = Recommendation(
        asset=equipment["CNC-01"],
        urgency=RecommendationUrgency.ELEVATED,
        confidence=0.75,
        metadata={"note": "synthetic"},
    )
    assert recommendation.is_actionable is True

    routine = Recommendation(
        asset=equipment["CNC-01"],
        urgency=RecommendationUrgency.ROUTINE,
        confidence=1.0,
    )
    assert routine.is_actionable is False

    with pytest.raises(ValueError, match="between 0 and 1"):
        Recommendation(
            asset=equipment["CNC-01"],
            urgency=RecommendationUrgency.ELEVATED,
            confidence=1.5,
        )
    with pytest.raises(ValueError, match="JSON-compatible"):
        Recommendation(
            asset=equipment["CNC-01"],
            urgency=RecommendationUrgency.ELEVATED,
            metadata={"bad": object()},
        )


def test_work_order_factory_infers_mode_and_rejects_unknown_assets(
    equipment: dict[str, Equipment],
) -> None:
    policy = CapacityBreach([equipment["CNC-01"]])

    any_rate = policy.create_work_order("cnc-01", DispatchSide.REQUEST, 4.0)
    assert any_rate.asset_id == "CNC-01"
    assert any_rate.mode == WorkOrderMode.ANY_RATE
    assert any_rate.max_hourly_rate is None

    capped = policy.create_work_order(
        "CNC-01",
        DispatchSide.OFFER,
        2.0,
        max_hourly_rate=140.0,
        dispatch_window=DispatchWindow.IMMEDIATE,
    )
    assert capped.mode == WorkOrderMode.RATE_CAPPED
    assert capped.max_hourly_rate == Decimal("140.0")
    assert capped.dispatch_window == DispatchWindow.IMMEDIATE

    with pytest.raises(ValueError, match="not configured"):
        policy.create_work_order("PRESS-04", DispatchSide.REQUEST, 1.0)
    with pytest.raises(ValueError, match="not configured"):
        policy.on_reading(make_reading("PRESS-04", 100.0, datetime(2026, 8, 19, tzinfo=UTC)))


def test_assignment_hook_and_buffer_eviction(equipment: dict[str, Equipment]) -> None:
    policy = CapacityBreach([equipment["CNC-01"]])
    start = datetime(2026, 8, 19, tzinfo=UTC)
    for index, value in enumerate([100.0, 101.0, 102.0]):
        reading = make_reading("CNC-01", value, start.replace(second=index))
        policy._buffer_reading(reading, max_buffer=2)

    buffered = [float(reading.last_reading) for reading in policy._reading_buffer["CNC-01"]]
    assert buffered == [101.0, 102.0]
    work_order = policy.create_work_order("CNC-01", DispatchSide.REQUEST, 2.0)
    policy.on_assignment(work_order, assignment_rate=150.0, assignment_hours=2.0)
    assert policy._workload_exposure["CNC-01"] == pytest.approx(300.0)


def test_integer_policy_parameters_are_strict(equipment: dict[str, Equipment]) -> None:
    with pytest.raises(ValueError, match="lookback must be an integer"):
        CapacityBreach([equipment["CNC-01"]], {"lookback": True})
    with pytest.raises(ValueError, match="fast_span must be an integer"):
        TelemetryTrendCrossover([equipment["CNC-01"]], {"fast_span": 2.5})
    with pytest.raises(ValueError, match="window must be an integer"):
        TelemetryBandDeviation([equipment["CNC-01"]], {"window": 20.0})
    with pytest.raises(ValueError, match="lookback must be an integer"):
        CrossAssetTelemetryImbalance(
            [equipment["CNC-01"], equipment["PRESS-04"]],
            {"lookback": False},
        )


def test_threshold_and_trend_recommendations_can_trigger(
    equipment: dict[str, Equipment],
) -> None:
    start = datetime(2026, 8, 19, tzinfo=UTC)
    breach = CapacityBreach(
        [equipment["CNC-01"]],
        {"lookback": 3, "min_ticks": 4, "deviation_multiplier": 1.0},
    )
    for index, value in enumerate([100.0, 101.0, 100.5, 110.0]):
        breach.on_reading(make_reading("CNC-01", value, start.replace(second=index)))

    breach_recommendations = breach.generate_recommendations()
    assert len(breach_recommendations) == 1
    assert breach_recommendations[0].urgency in {
        RecommendationUrgency.ELEVATED,
        RecommendationUrgency.URGENT,
    }
    assert breach_recommendations[0].metadata["channel_upper"] == 101.0

    crossover = TelemetryTrendCrossover(
        [equipment["CNC-01"]],
        {"fast_span": 2, "slow_span": 3},
    )
    for index, value in enumerate([100.0, 100.0, 100.0, 110.0]):
        crossover.on_reading(make_reading("CNC-01", value, start.replace(second=index)))

    crossover_recommendations = crossover.generate_recommendations()
    assert len(crossover_recommendations) == 1
    assert crossover_recommendations[0].urgency == RecommendationUrgency.ELEVATED


def test_telemetry_deviation_and_cross_asset_recommendations_can_trigger(
    equipment: dict[str, Equipment],
) -> None:
    start = datetime(2026, 8, 19, tzinfo=UTC)
    reversion = TelemetryBandDeviation(
        [equipment["CNC-01"]],
        {"window": 3, "min_ticks": 4, "band_width": 2.0},
    )
    for index, value in enumerate([99.0, 100.0, 101.0, 104.0]):
        reversion.on_reading(make_reading("CNC-01", value, start.replace(second=index)))

    reversion_recommendations = reversion.generate_recommendations()
    assert len(reversion_recommendations) == 1
    assert reversion_recommendations[0].urgency == RecommendationUrgency.DEFER

    pairs = CrossAssetTelemetryImbalance(
        [equipment["CNC-01"], equipment["PRESS-04"]],
        {
            "pair": ("CNC-01", "PRESS-04"),
            "lookback": 3,
            "entry_z": 1.5,
            "exit_z": 0.25,
        },
    )
    for index, (value_a, value_b) in enumerate(
        [(100.0, 100.0), (102.0, 100.0), (101.0, 100.0), (120.0, 100.0)]
    ):
        timestamp = start.replace(second=index)
        pairs.on_reading(make_reading("CNC-01", value_a, timestamp))
        pairs.on_reading(make_reading("PRESS-04", value_b, timestamp))

    pair_recommendations = pairs.generate_recommendations()
    assert [recommendation.urgency for recommendation in pair_recommendations] == [
        RecommendationUrgency.ELEVATED,
        RecommendationUrgency.DEFER,
    ]

    for recommendation in reversion_recommendations + pair_recommendations:
        assert 0.0 <= recommendation.confidence <= 1.0
        json.dumps(recommendation.metadata, allow_nan=False)


def test_cross_asset_exit_recommendations_reset_state(
    equipment: dict[str, Equipment],
) -> None:
    start = datetime(2026, 8, 19, tzinfo=UTC)
    pairs = CrossAssetTelemetryImbalance(
        [equipment["CNC-01"], equipment["PRESS-04"]],
        {
            "pair": ("CNC-01", "PRESS-04"),
            "lookback": 3,
            "entry_z": 1.0,
            "exit_z": 0.3,
        },
    )
    for index, (value_a, value_b) in enumerate(
        [(100.0, 100.0), (102.0, 100.0), (101.0, 100.0), (120.0, 100.0)]
    ):
        timestamp = start.replace(second=index)
        pairs.on_reading(make_reading("CNC-01", value_a, timestamp))
        pairs.on_reading(make_reading("PRESS-04", value_b, timestamp))
    pairs.generate_recommendations()

    for index, (value_a, value_b) in enumerate(
        [(104.0, 100.0), (103.8, 100.0), (104.2, 100.0), (104.0, 100.0)],
        start=4,
    ):
        timestamp = start.replace(second=index)
        pairs.on_reading(make_reading("CNC-01", value_a, timestamp))
        pairs.on_reading(make_reading("PRESS-04", value_b, timestamp))

    exit_recommendations = pairs.generate_recommendations()
    assert [recommendation.urgency for recommendation in exit_recommendations] == [
        RecommendationUrgency.ROUTINE,
        RecommendationUrgency.ROUTINE,
    ]
    assert all(
        recommendation.metadata["action"] == "imbalance_resolved"
        for recommendation in exit_recommendations
    )


@pytest.mark.parametrize(
    "value",
    ["0.1", "0.30000000000000004", "185.55", "0.00000001", "123456789.123456789"],
)
def test_decimal_values_round_trip_exactly(store: TelemetryStore, value: str) -> None:
    amount = Decimal(value)
    store.insert_reading("CNC-01", amount, amount, amount, 1, _ts())
    row = store.get_readings("CNC-01")[0]
    assert row.min_reading == amount
    assert str(row.min_reading) == str(amount)
    assert row.min_reading.as_tuple() == amount.as_tuple()
    assert row.max_reading == amount
    assert row.last_reading == amount


def test_binary_floats_are_rejected_for_decimal_columns(store: TelemetryStore) -> None:
    with pytest.raises(TypeError):
        store.insert_reading("CNC-01", 0.1, Decimal("1"), Decimal("1"), 1, _ts())
    with pytest.raises(TypeError):
        store.insert_assignment(
            "assign-float",
            "CNC-01",
            "req-1",
            "prov-1",
            1.5,
            Decimal("1"),
            "buyer",
            "seller",
            _ts(),
        )


def test_interval_round_trip(store: TelemetryStore) -> None:
    store.insert_interval("CNC-01", "1m", "185.10", "186.00", "184.99", "185.55", 1_000, _ts())
    bar = store.get_intervals("CNC-01", "1m")[0]
    assert (bar.open_reading, bar.high_reading, bar.low_reading, bar.close_reading) == (
        Decimal("185.10"),
        Decimal("186.00"),
        Decimal("184.99"),
        Decimal("185.55"),
    )
    assert bar.sample_count == 1_000
    assert store.get_intervals("CNC-01", "5m") == []


def test_naive_datetimes_are_rejected(store: TelemetryStore) -> None:
    naive = datetime(2026, 3, 1, 12, 0)
    with pytest.raises(ValueError):
        store.insert_reading("CNC-01", Decimal("1"), Decimal("1"), Decimal("1"), 1, naive)
    store.insert_reading("CNC-01", Decimal("1"), Decimal("1"), Decimal("1"), 1, _ts())
    with pytest.raises(ValueError):
        store.get_readings("CNC-01", start=naive)
    with pytest.raises(ValueError):
        store.get_readings("CNC-01", end=naive)


def test_offsets_are_normalised_to_utc_and_returned_aware(store: TelemetryStore) -> None:
    berlin_summer = timezone(timedelta(hours=2))
    stamp = datetime(2026, 7, 1, 14, 30, tzinfo=berlin_summer)
    store.insert_reading("CNC-01", Decimal("1"), Decimal("2"), Decimal("1.5"), 5, stamp)

    row = store.get_readings("CNC-01")[0]
    assert row.timestamp.tzinfo is not None
    assert row.timestamp.utcoffset() == timedelta(0)
    assert row.timestamp == datetime(2026, 7, 1, 12, 30, tzinfo=UTC)


def test_range_boundaries_are_inclusive_and_latest_reading_is_newest(store: TelemetryStore) -> None:
    stamps = [_ts(hour=hour) for hour in (10, 11, 12, 13)]
    for index, stamp in enumerate(stamps):
        store.insert_reading("CNC-01", Decimal("1"), Decimal("2"), Decimal("1.5"), index, stamp)

    inclusive = store.get_readings("CNC-01", start=stamps[1], end=stamps[2])
    assert [row.timestamp for row in inclusive] == [stamps[2], stamps[1]]

    everything = store.get_readings("CNC-01")
    assert [row.timestamp for row in everything] == sorted(stamps, reverse=True)
    assert store.get_readings("CNC-01", limit=2) == everything[:2]
    assert store.latest_reading("CNC-01") == everything[0]


def test_query_limits_are_validated_and_capped(store: TelemetryStore) -> None:
    store.insert_reading("CNC-01", Decimal("1"), Decimal("2"), Decimal("1.5"), 1, _ts())
    assert store.get_readings("CNC-01", limit=MAX_QUERY_LIMIT * 10) == store.get_readings("CNC-01")
    with pytest.raises(ValueError):
        store.get_readings("CNC-01", limit=0)
    with pytest.raises(TypeError):
        store.get_readings("CNC-01", limit=True)
    with pytest.raises(ValueError):
        store.get_readings("   ")


def test_assignment_ids_are_unique_and_integrity_errors_surface(
    store: TelemetryStore,
) -> None:
    store.insert_assignment(
        "assign-1",
        "CNC-01",
        "req-1",
        "prov-1",
        "185.55",
        "10",
        "alpha",
        "beta",
        _ts(),
    )
    with pytest.raises(IntegrityError):
        store.insert_assignment(
            "assign-1",
            "CNC-01",
            "req-2",
            "prov-2",
            "185.55",
            "10",
            "alpha",
            "beta",
            _ts(),
        )
    assert store.count_assignments("CNC-01") == 1
    assignment = store.get_assignments("CNC-01")[0]
    assert assignment.hourly_rate == Decimal("185.55")
    assert assignment.hours == Decimal("10")


def _assignment_payload(assignment_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "assignment_id": assignment_id,
        "asset_id": "CNC-01",
        "requester_work_order_id": "req-1",
        "provider_work_order_id": "prov-1",
        "hourly_rate": Decimal("150.55"),
        "hours": Decimal("0.25"),
        "requester_organization_id": "alpha",
        "provider_organization_id": "beta",
        "timestamp": _ts(),
    }
    payload.update(overrides)
    return payload


def test_insert_assignments_batch_round_trips_exactly(store: TelemetryStore) -> None:
    berlin_summer = timezone(timedelta(hours=2))
    written = store.insert_assignments(
        [
            _assignment_payload("batch-1"),
            _assignment_payload(
                "batch-2",
                hourly_rate=Decimal("0.10"),
                hours=Decimal("2"),
                timestamp=datetime(2026, 3, 1, 14, 30, tzinfo=berlin_summer),
            ),
        ]
    )
    assert written == 2
    assert store.insert_assignments([]) == 0

    rows = {row.assignment_id: row for row in store.get_assignments("CNC-01")}
    assert rows["batch-1"].hourly_rate == Decimal("150.55")
    assert rows["batch-1"].hours == Decimal("0.25")
    assert str(rows["batch-2"].hourly_rate) == "0.10"
    assert rows["batch-2"].timestamp == datetime(2026, 3, 1, 12, 30, tzinfo=UTC)
    assert rows["batch-2"].timestamp.utcoffset() == timedelta(0)


def test_insert_assignments_batch_is_atomic(store: TelemetryStore) -> None:
    store.insert_assignments([_assignment_payload("existing-1")])

    with pytest.raises(IntegrityError):
        store.insert_assignments(
            [_assignment_payload("fresh-1"), _assignment_payload("existing-1")]
        )
    assert store.count_assignments() == 1

    with pytest.raises(ValueError):
        store.insert_assignments([_assignment_payload("fresh-2"), _assignment_payload("  ")])
    assert store.count_assignments() == 1

    with pytest.raises(ValueError):
        store.insert_assignments([_assignment_payload("fresh-3", requester_organization_id="")])
    with pytest.raises(TypeError):
        store.insert_assignments([_assignment_payload("fresh-4", hourly_rate=1.5)])
    assert store.count_assignments() == 1
    assert store.insert_assignments([_assignment_payload("fresh-5")]) == 1


def test_assignment_work_order_id_columns_match_the_api_contract(store: TelemetryStore) -> None:
    assert WORK_ORDER_ID_COLUMN_LENGTH == 64
    columns = AssignmentRecord.__table__.c
    assert columns.requester_work_order_id.type.length == WORK_ORDER_ID_COLUMN_LENGTH
    assert columns.provider_work_order_id.type.length == WORK_ORDER_ID_COLUMN_LENGTH

    long_requester = "r" * WORK_ORDER_ID_COLUMN_LENGTH
    long_provider = "p" * WORK_ORDER_ID_COLUMN_LENGTH
    store.insert_assignments(
        [
            _assignment_payload(
                "long-ids",
                requester_work_order_id=long_requester,
                provider_work_order_id=long_provider,
            )
        ]
    )
    row = store.get_assignments("CNC-01")[0]
    assert row.requester_work_order_id == long_requester
    assert row.provider_work_order_id == long_provider


def _seed_equipment(store: TelemetryStore) -> None:
    store.upsert_equipments(
        [
            {
                "asset_id": "CNC-01",
                "name": "Fräszentrum 1",
                "equipment_type": "CNC_MACHINE",
                "currency": "EUR",
                "site_code": "MW-BER-1",
                "hourly_service_rate": "125.50",
                "rate_increment": "0.50",
                "hour_lot_size": "0.25",
            },
            {
                "asset_id": "PRESS-04",
                "name": "100% Presswerk 4",
                "equipment_type": "HYDRAULIC_PRESS",
                "currency": "EUR",
                "site_code": "MW-MUC-2",
                "hourly_service_rate": "140.00",
                "rate_increment": "1.00",
                "hour_lot_size": "0.50",
            },
            {
                "asset_id": "ROBOT-07",
                "name": "Roboterzelle 7",
                "equipment_type": "ROBOTIC_ARM",
                "currency": "EUR",
                "site_code": "MW-HAM-3",
                "hourly_service_rate": "110.00",
                "rate_increment": "0.50",
                "hour_lot_size": "0.25",
            },
        ]
    )


def test_upsert_equipment_updates_rows_and_as_dict(store: TelemetryStore) -> None:
    _seed_equipment(store)
    assert store.count_equipment() == 3
    store.upsert_equipment(
        {
            "asset_id": "CNC-01",
            "name": "Fräszentrum 1 (renamed)",
            "equipment_type": "CNC_MACHINE",
            "currency": "EUR",
            "site_code": "MW-BER-1",
            "hourly_service_rate": "130.00",
            "rate_increment": "0.50",
            "hour_lot_size": "0.25",
        }
    )
    assert store.count_equipment() == 3
    cnc = store.get_equipment("cnc-01")
    assert cnc is not None
    assert cnc.name == "Fräszentrum 1 (renamed)"
    assert cnc.hourly_service_rate == Decimal("130.00")
    assert cnc.as_dict()["hourly_service_rate"] == "130.00"


@pytest.mark.parametrize(
    "payload",
    [
        "' OR 1=1 --",
        "'; DROP TABLE equipment; --",
        '" OR ""="',
        "CNC' UNION SELECT * FROM equipment --",
    ],
)
def test_sql_injection_payloads_are_inert(store: TelemetryStore, payload: str) -> None:
    _seed_equipment(store)
    assert store.search_equipment(payload) == []
    assert store.count_equipment() == 3


def test_like_wildcards_are_escaped_and_matched_literally(store: TelemetryStore) -> None:
    _seed_equipment(store)
    assert [row.asset_id for row in store.search_equipment("%")] == ["PRESS-04"]
    assert store.search_equipment("_") == []
    assert [row.asset_id for row in store.search_equipment("100%")] == ["PRESS-04"]
    assert [row.asset_id for row in store.search_equipment("robot")] == ["ROBOT-07"]
    assert [row.asset_id for row in store.search_equipment("zentrum")] == ["CNC-01"]


def test_search_bounds_are_enforced(store: TelemetryStore) -> None:
    _seed_equipment(store)
    assert len(store.search_equipment("a", limit=1)) <= 1
    with pytest.raises(ValueError):
        store.search_equipment("   ")
    with pytest.raises(ValueError):
        store.search_equipment("x" * (MAX_SEARCH_QUERY_LENGTH + 1))
    with pytest.raises(ValueError):
        store.search_equipment("cnc", limit=0)
    with pytest.raises(TypeError):
        store.search_equipment(123)  # type: ignore[arg-type]


def test_close_disposes_engine_and_blocks_further_use() -> None:
    store = TelemetryStore("sqlite://")
    store.insert_reading("CNC-01", Decimal("1"), Decimal("2"), Decimal("1.5"), 1, _ts())
    assert store.count_readings("CNC-01") == 1

    store.close()
    assert store.is_closed is True
    store.close()
    with pytest.raises(RuntimeError):
        store.count_readings("CNC-01")
    with pytest.raises(RuntimeError):
        store.get_readings("CNC-01")


def test_store_context_manager_closes() -> None:
    with TelemetryStore("sqlite://") as store:
        assert store.count_readings() == 0
    assert store.is_closed is True


def test_failed_operation_rolls_back(store: TelemetryStore) -> None:
    store.insert_assignment(
        "assign-rollback",
        "CNC-01",
        "req",
        "prov",
        "1.00",
        "1",
        "alpha",
        "beta",
        _ts(),
    )
    with pytest.raises(IntegrityError):
        store.insert_assignment(
            "assign-rollback",
            "CNC-01",
            "req",
            "prov",
            "1.00",
            "1",
            "alpha",
            "beta",
            _ts(),
        )
    store.insert_assignment(
        "assign-ok",
        "CNC-01",
        "req",
        "prov",
        "1.00",
        "1",
        "alpha",
        "beta",
        _ts(),
    )
    assert store.count_assignments() == 2


def test_batch_insert_is_atomic_and_counted(store: TelemetryStore) -> None:
    readings: list[dict[str, object]] = [
        {
            "asset_id": "CNC-01",
            "min_reading": Decimal("1.01"),
            "max_reading": Decimal("1.02"),
            "last_reading": Decimal("1.015"),
            "sample_count": 10,
            "timestamp": _ts(hour=hour),
        }
        for hour in (9, 10, 11)
    ]
    assert store.insert_readings(readings) == 3
    assert store.insert_readings([]) == 0
    assert store.count_readings("CNC-01") == 3

    readings[1]["timestamp"] = datetime(2026, 3, 1, 10, 0)
    with pytest.raises(ValueError):
        store.insert_readings(readings)
    assert store.count_readings("CNC-01") == 3


def _ts(hour: int = 12, minute: int = 0) -> datetime:
    return datetime(2026, 3, 1, hour, minute, tzinfo=UTC)

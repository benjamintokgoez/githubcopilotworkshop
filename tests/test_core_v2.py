"""Focused tests for the MittelWerk core runtime (Pydantic v2).

Covers FIFO rate-time priority, maker assignment pricing, depth after partial
assignments, IMMEDIATE/COMPLETE dispatch windows, cancellation, pre-dispatch
check rejection, equipment/rate/hour-lot boundary validation, event
delivery/replay, requester/provider workload cost accounting, aware-UTC
timestamp enforcement, honest SHIFT/SCHEDULED_END rejection, work order
lifecycle boundaries (duplicate ids / non-NEW), and EventBus
configuration/subscriber-id hardening.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from mittelwerk.core.engine import DispatchEngine, DispatchResult, DuplicateWorkOrderError
from mittelwerk.core.events import DispatchEventType, DomainEvent, EventBus, EventLog
from mittelwerk.core.models import (
    DispatchSide,
    DispatchWindow,
    Equipment,
    EquipmentCategory,
    OperationalRiskMetrics,
    OrganizationSnapshot,
    ServiceAssignment,
    TelemetryReading,
    Workload,
    WorkOrder,
    WorkOrderMode,
    WorkOrderStatus,
)

D = Decimal


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _equipment() -> dict[str, Equipment]:
    return {
        "CNC-01": Equipment(
            asset_id="CNC-01",
            name="CNC Mill Line 1",
            equipment_type=EquipmentCategory.CNC_MACHINE,
            service_interval_days=30,
            hourly_service_rate="85.00",
            rate_increment="0.01",
            hour_lot_size="1",
        ),
        "ROBOT-07": Equipment(
            asset_id="ROBOT-07",
            name="Robotic Welding Arm 7",
            equipment_type=EquipmentCategory.ROBOTIC_ARM,
            service_interval_days=21,
            hourly_service_rate="110.00",
            rate_increment="0.01",
            hour_lot_size="0.001",
        ),
    }


def _engine(pre_dispatch_check=None) -> DispatchEngine:
    return DispatchEngine(
        event_bus=EventBus(),
        equipment=_equipment(),
        pre_dispatch_check=pre_dispatch_check,
    )


def _work_order(
    side: DispatchSide,
    requested_hours,
    max_hourly_rate=None,
    *,
    asset_id: str = "CNC-01",
    mode: WorkOrderMode = WorkOrderMode.RATE_CAPPED,
    dispatch_window: DispatchWindow = DispatchWindow.OPEN,
    organization_id: str = "c1",
    escalation_rate=None,
) -> WorkOrder:
    return WorkOrder(
        organization_id=organization_id,
        asset_id=asset_id,
        side=side,
        mode=mode,
        requested_hours=D(str(requested_hours)),
        max_hourly_rate=None if max_hourly_rate is None else D(str(max_hourly_rate)),
        escalation_rate=None if escalation_rate is None else D(str(escalation_rate)),
        dispatch_window=dispatch_window,
    )


def _events_for(eng: DispatchEngine, work_order_id: str) -> list[DomainEvent]:
    """Return all events correlated to ``work_order_id``, in publication order."""
    return [e for e in eng._event_bus.replay() if e.correlation_id == work_order_id]


# ---------------------------------------------------------------------------
# FIFO rate-time priority
# ---------------------------------------------------------------------------


async def test_fifo_rate_time_priority() -> None:
    eng = _engine()
    maker_a = _work_order(DispatchSide.OFFER, 5, 100, organization_id="A")
    maker_b = _work_order(DispatchSide.OFFER, 5, 100, organization_id="B")
    await eng.submit_work_order(maker_a)
    await eng.submit_work_order(maker_b)

    taker = _work_order(DispatchSide.REQUEST, 6, 100, organization_id="T")
    result = await eng.submit_work_order(taker)

    assert isinstance(result, DispatchResult)
    # First resting work order (A) must be consumed before B (time priority).
    assert result.assignments[0].provider_work_order_id == maker_a.work_order_id
    assert result.assignments[0].hours == D("5")
    assert result.assignments[1].provider_work_order_id == maker_b.work_order_id
    assert result.assignments[1].hours == D("1")
    assert taker.status is WorkOrderStatus.ASSIGNED
    # B has 4 left resting.
    queue = eng.get_queue("CNC-01")
    assert queue is not None
    assert queue.best_offer_rate == D("100")
    assert queue.offer_levels()[0].total_hours == D("4")


async def test_rate_priority_best_level_first() -> None:
    eng = _engine()
    await eng.submit_work_order(_work_order(DispatchSide.OFFER, 5, 101, organization_id="A"))
    await eng.submit_work_order(_work_order(DispatchSide.OFFER, 5, 100, organization_id="B"))
    taker = _work_order(DispatchSide.REQUEST, 5, 101, organization_id="T")
    result = await eng.submit_work_order(taker)
    # Best (lowest) offer 100 fills first.
    assert result.assignments[0].hourly_rate == D("100")


# ---------------------------------------------------------------------------
# Maker (resting) assignment rate
# ---------------------------------------------------------------------------


async def test_assignment_at_resting_maker_rate() -> None:
    eng = _engine()
    await eng.submit_work_order(_work_order(DispatchSide.OFFER, 5, 101, organization_id="M"))
    taker = _work_order(DispatchSide.REQUEST, 5, 105, organization_id="T")  # crosses aggressively
    result = await eng.submit_work_order(taker)
    assert len(result.assignments) == 1
    assert result.assignments[0].hourly_rate == D("101")  # maker's rate, not 105
    assert taker.average_service_rate == D("101")


async def test_any_rate_work_order_assigns_at_maker_rate_and_never_rests() -> None:
    eng = _engine()
    await eng.submit_work_order(_work_order(DispatchSide.OFFER, 4, 102, organization_id="M"))
    taker = _work_order(DispatchSide.REQUEST, 10, mode=WorkOrderMode.ANY_RATE, organization_id="T")
    result = await eng.submit_work_order(taker)
    assert result.assignments[0].hourly_rate == D("102")
    assert taker.assigned_hours == D("4")
    # Residual must be cancelled, never rested.
    queue = eng.get_queue("CNC-01")
    assert queue is not None
    assert queue.request_depth == 0
    # A partially assigned ANY_RATE order whose residual is cancelled ends terminal.
    assert taker.status is WorkOrderStatus.CANCELLED
    assert taker.status.is_terminal


# ---------------------------------------------------------------------------
# Depth after partial assignment
# ---------------------------------------------------------------------------


async def test_depth_accurate_after_partial_assignment() -> None:
    eng = _engine()
    await eng.submit_work_order(_work_order(DispatchSide.OFFER, 10, 100, organization_id="M"))
    await eng.submit_work_order(_work_order(DispatchSide.REQUEST, 3, 100, organization_id="T"))
    queue = eng.get_queue("CNC-01")
    assert queue is not None
    level = queue.offer_levels()[0]
    assert level.total_hours == D("7")
    assert level.work_order_count == 1
    snap = queue.depth_snapshot()
    assert snap["offers"][0]["hours"] == "7"


# ---------------------------------------------------------------------------
# Dispatch window: IMMEDIATE / COMPLETE
# ---------------------------------------------------------------------------


async def test_immediate_cancels_residual() -> None:
    eng = _engine()
    await eng.submit_work_order(_work_order(DispatchSide.OFFER, 3, 100, organization_id="M"))
    taker = _work_order(
        DispatchSide.REQUEST, 10, 100, dispatch_window=DispatchWindow.IMMEDIATE, organization_id="T"
    )
    result = await eng.submit_work_order(taker)
    assert taker.assigned_hours == D("3")
    # Residual cancelled -> terminal CANCELLED, not left nonterminal off-queue.
    assert taker.status is WorkOrderStatus.CANCELLED
    assert taker.status.is_terminal
    queue = eng.get_queue("CNC-01")
    assert queue is not None
    assert queue.request_depth == 0  # residual not rested
    assert len(result.assignments) == 1
    # The partial-assignment event must precede the cancellation event.
    kinds = [
        e.event_type
        for e in _events_for(eng, taker.work_order_id)
        if e.event_type
        in (DispatchEventType.WORK_ORDER_PARTIALLY_ASSIGNED, DispatchEventType.WORK_ORDER_CANCELLED)
    ]
    assert kinds == [
        DispatchEventType.WORK_ORDER_PARTIALLY_ASSIGNED,
        DispatchEventType.WORK_ORDER_CANCELLED,
    ]


async def test_immediate_no_capacity_is_cancelled() -> None:
    eng = _engine()
    taker = _work_order(
        DispatchSide.REQUEST, 5, 100, dispatch_window=DispatchWindow.IMMEDIATE, organization_id="T"
    )
    result = await eng.submit_work_order(taker)
    assert result.assignments == []
    assert taker.status is WorkOrderStatus.CANCELLED
    queue = eng.get_queue("CNC-01")
    assert queue is not None
    assert queue.request_depth == 0


async def test_complete_stood_down_when_not_fully_assignable() -> None:
    eng = _engine()
    await eng.submit_work_order(_work_order(DispatchSide.OFFER, 3, 100, organization_id="M"))
    taker = _work_order(
        DispatchSide.REQUEST, 10, 100, dispatch_window=DispatchWindow.COMPLETE, organization_id="T"
    )
    result = await eng.submit_work_order(taker)
    assert result.assignments == []
    # An unassignable COMPLETE order is accepted then stood down, not rejected.
    assert taker.status is WorkOrderStatus.CANCELLED
    kinds = [e.event_type for e in _events_for(eng, taker.work_order_id)]
    assert kinds == [
        DispatchEventType.WORK_ORDER_SUBMITTED,
        DispatchEventType.WORK_ORDER_ACCEPTED,
        DispatchEventType.WORK_ORDER_CANCELLED,
    ]
    cancel_evt = _events_for(eng, taker.work_order_id)[-1]
    assert "fully assigned" in cancel_evt.payload["reason"]
    # Resting capacity untouched.
    queue = eng.get_queue("CNC-01")
    assert queue is not None
    assert queue.offer_levels()[0].total_hours == D("3")


async def test_complete_assigns_when_fully_available() -> None:
    eng = _engine()
    await eng.submit_work_order(_work_order(DispatchSide.OFFER, 6, 100, organization_id="M1"))
    await eng.submit_work_order(_work_order(DispatchSide.OFFER, 6, 100, organization_id="M2"))
    taker = _work_order(
        DispatchSide.REQUEST, 10, 100, dispatch_window=DispatchWindow.COMPLETE, organization_id="T"
    )
    result = await eng.submit_work_order(taker)
    assert taker.status is WorkOrderStatus.ASSIGNED
    assert taker.assigned_hours == D("10")
    assert sum(a.hours for a in result.assignments) == D("10")


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


async def test_cancel_resting_work_order() -> None:
    eng = _engine()
    resting = _work_order(DispatchSide.REQUEST, 5, 99, organization_id="M")
    await eng.submit_work_order(resting)
    cancelled = await eng.cancel_work_order(resting.work_order_id)  # asset_id omitted
    assert cancelled is not None
    assert cancelled.work_order_id == resting.work_order_id
    assert cancelled.status is WorkOrderStatus.CANCELLED
    queue = eng.get_queue("CNC-01")
    assert queue is not None
    assert queue.total_work_orders == 0
    # Cancelling again returns None (no stale index).
    assert await eng.cancel_work_order(resting.work_order_id) is None


async def test_cancel_with_asset_id_hint() -> None:
    eng = _engine()
    resting = _work_order(DispatchSide.OFFER, 5, 101, organization_id="M")
    await eng.submit_work_order(resting)
    cancelled = await eng.cancel_work_order(resting.work_order_id, asset_id="CNC-01")
    assert cancelled is not None
    assert await eng.cancel_work_order("does-not-exist", asset_id="CNC-01") is None


# ---------------------------------------------------------------------------
# Pre-dispatch check rejection
# ---------------------------------------------------------------------------


class _RejectAllPolicy:
    def can_dispatch(self, work_order: WorkOrder, workload: Workload | None) -> tuple[bool, str]:
        return False, "blocked by pre-dispatch check"


async def test_pre_dispatch_check_rejection() -> None:
    eng = _engine(pre_dispatch_check=_RejectAllPolicy())
    taker = _work_order(DispatchSide.REQUEST, 5, 100, organization_id="T")
    result = await eng.submit_work_order(taker)
    assert result.assignments == []
    assert result.rejection_reason == "blocked by pre-dispatch check"
    assert taker.status is WorkOrderStatus.REJECTED
    rejected = eng._event_bus.replay(event_types={DispatchEventType.WORK_ORDER_REJECTED})
    assert rejected and rejected[-1].payload["reason"] == "blocked by pre-dispatch check"


# ---------------------------------------------------------------------------
# Boundary validation: equipment / rate / hours-lot / unsupported mode
# ---------------------------------------------------------------------------


async def test_reject_unknown_asset() -> None:
    eng = _engine()
    order = _work_order(DispatchSide.REQUEST, 1, 100, asset_id="ZZZZ", organization_id="T")
    result = await eng.submit_work_order(order)
    assert order.status is WorkOrderStatus.REJECTED
    assert result.assignments == []


async def test_reject_invalid_rate() -> None:
    eng = _engine()
    order = _work_order(
        DispatchSide.REQUEST, 1, "150.005", organization_id="T"
    )  # not a multiple of 0.01
    await eng.submit_work_order(order)
    assert order.status is WorkOrderStatus.REJECTED


async def test_reject_invalid_hours_lot() -> None:
    eng = _engine()
    order = _work_order(
        DispatchSide.REQUEST, "0.0005", 100, asset_id="ROBOT-07", organization_id="T"
    )
    await eng.submit_work_order(order)
    assert order.status is WorkOrderStatus.REJECTED


async def test_valid_fractional_hours_accepted() -> None:
    eng = _engine()
    order = _work_order(
        DispatchSide.REQUEST, "0.002", 100, asset_id="ROBOT-07", organization_id="T"
    )
    await eng.submit_work_order(order)
    assert order.status is WorkOrderStatus.ACCEPTED  # resting, no crossing capacity


def test_equipment_currency_is_normalized_and_rejects_non_codes() -> None:
    equipment = Equipment(
        asset_id="GEN-09",
        name="Backup Generator Unit 9",
        equipment_type=EquipmentCategory.GENERATOR,
        service_interval_days=180,
        hourly_service_rate="95.00",
        currency=" eur ",
    )
    assert equipment.currency == "EUR"

    with pytest.raises(ValueError, match="three-letter ASCII"):
        Equipment(
            asset_id="GEN-09",
            name="Backup Generator Unit 9",
            equipment_type=EquipmentCategory.GENERATOR,
            service_interval_days=180,
            hourly_service_rate="95.00",
            currency="€€€",
        )


async def test_reject_bare_escalation_work_order() -> None:
    eng = _engine()
    order = _work_order(
        DispatchSide.REQUEST,
        1,
        mode=WorkOrderMode.ESCALATION,
        escalation_rate=100,
        organization_id="T",
    )
    result = await eng.submit_work_order(order)
    assert order.status is WorkOrderStatus.REJECTED
    assert result.assignments == []


# ---------------------------------------------------------------------------
# Event delivery (callback subscribed after start) + replay
# ---------------------------------------------------------------------------


async def test_callback_delivery_after_start() -> None:
    bus = EventBus()
    eng = DispatchEngine(event_bus=bus, equipment=_equipment())
    received: list[DomainEvent] = []

    async def handler(event: DomainEvent) -> None:
        received.append(event)

    await bus.start()
    bus.subscribe(
        {DispatchEventType.WORK_ORDER_ACCEPTED, DispatchEventType.ASSIGNMENT_EXECUTED}, handler
    )

    await eng.submit_work_order(_work_order(DispatchSide.OFFER, 5, 100, organization_id="M"))
    await eng.submit_work_order(_work_order(DispatchSide.REQUEST, 5, 100, organization_id="T"))
    await bus.stop()  # drains queued events before returning

    types = {e.event_type for e in received}
    assert DispatchEventType.WORK_ORDER_ACCEPTED in types
    assert DispatchEventType.ASSIGNMENT_EXECUTED in types


async def test_engine_bus_replay() -> None:
    eng = _engine()
    await eng.submit_work_order(_work_order(DispatchSide.OFFER, 5, 100, organization_id="M"))
    await eng.submit_work_order(_work_order(DispatchSide.REQUEST, 5, 100, organization_id="T"))
    accepted = eng._event_bus.replay(event_types={DispatchEventType.WORK_ORDER_ACCEPTED})
    assigned = eng._event_bus.replay(event_types={DispatchEventType.WORK_ORDER_ASSIGNED})
    assert len(accepted) == 2
    # Both the incoming taker and the fully-consumed resting maker are assigned.
    assert len(assigned) == 2


def test_event_log_bounded_replay() -> None:
    log = EventLog(max_size=3)
    seqs = [log.append(DomainEvent(event_type=DispatchEventType.SYSTEM_STATUS)) for _ in range(5)]
    assert seqs == [0, 1, 2, 3, 4]
    assert log.size == 3
    assert log.base_sequence == 2
    # Replaying from 0 clamps to the oldest retained event (seq 2).
    assert len(log.replay(0)) == 3
    # Replaying from a later sequence returns only newer events.
    assert len(log.replay(4)) == 1


# ---------------------------------------------------------------------------
# Workload accounting: requester / provider / crossing
# ---------------------------------------------------------------------------


def test_requester_workload_realized_and_unrealized_cost() -> None:
    wl = Workload(organization_id="c", asset_id="CNC-01")
    wl.apply_assignment(DispatchSide.REQUEST, D("10"), D("100"))
    assert wl.net_hours == D("10")
    assert wl.average_service_rate == D("100")
    realised = wl.apply_assignment(DispatchSide.OFFER, D("4"), D("110"))
    assert realised == D("40")
    assert wl.realized_cost == D("40")
    assert wl.net_hours == D("6")
    assert wl.average_service_rate == D("100")
    wl.reprice(D("110"))
    assert wl.unrealized_cost == D("60")  # (110-100)*6


def test_provider_workload_realized_cost() -> None:
    wl = Workload(organization_id="c", asset_id="CNC-01")
    wl.apply_assignment(DispatchSide.OFFER, D("10"), D("100"))
    assert wl.net_hours == D("-10")
    realised = wl.apply_assignment(DispatchSide.REQUEST, D("4"), D("90"))
    assert realised == D("40")  # covered 4 @ 90 vs avg 100
    assert wl.net_hours == D("-6")
    assert wl.average_service_rate == D("100")
    wl.reprice(D("90"))
    assert wl.unrealized_cost == D("60")  # (90-100)*-6


def test_workload_average_rate_on_increase() -> None:
    wl = Workload(organization_id="c", asset_id="CNC-01")
    wl.apply_assignment(DispatchSide.REQUEST, D("10"), D("100"))
    wl.apply_assignment(DispatchSide.REQUEST, D("10"), D("120"))
    assert wl.net_hours == D("20")
    assert wl.average_service_rate == D("110")


def test_workload_crossing_through_zero() -> None:
    wl = Workload(organization_id="c", asset_id="CNC-01")
    wl.apply_assignment(DispatchSide.REQUEST, D("5"), D("100"))
    realised = wl.apply_assignment(DispatchSide.OFFER, D("8"), D("110"))
    assert realised == D("50")  # closed 5 @ +10
    assert wl.net_hours == D("-3")  # flipped to net provider
    assert wl.average_service_rate == D("110")  # remainder opens at assignment rate


async def test_engine_updates_both_sides_workloads() -> None:
    eng = _engine()
    await eng.submit_work_order(_work_order(DispatchSide.OFFER, 5, 100, organization_id="provider"))
    await eng.submit_work_order(
        _work_order(DispatchSide.REQUEST, 5, 100, organization_id="requester")
    )
    requester = eng.workload_manager.get_workload("requester", "CNC-01")
    provider = eng.workload_manager.get_workload("provider", "CNC-01")
    assert requester.net_hours == D("5")
    assert provider.net_hours == D("-5")
    assert eng.workload_manager.get_workloads("requester")["CNC-01"].net_hours == D("5")


# ---------------------------------------------------------------------------
# Resting (maker) work order finalization
# ---------------------------------------------------------------------------


async def test_resting_work_order_partial_assignment_status_and_event() -> None:
    eng = _engine()
    maker = _work_order(DispatchSide.OFFER, 10, 100, organization_id="M")
    await eng.submit_work_order(maker)
    await eng.submit_work_order(_work_order(DispatchSide.REQUEST, 4, 100, organization_id="T"))

    # Resting work order state updated in place.
    assert maker.status is WorkOrderStatus.PARTIALLY_ASSIGNED
    assert maker.assigned_hours == D("4")
    assert maker.updated_at is not None
    # Exactly one partial-assignment lifecycle event for the resting work order.
    maker_events = [
        e.event_type
        for e in _events_for(eng, maker.work_order_id)
        if e.event_type
        in (DispatchEventType.WORK_ORDER_PARTIALLY_ASSIGNED, DispatchEventType.WORK_ORDER_ASSIGNED)
    ]
    assert maker_events == [DispatchEventType.WORK_ORDER_PARTIALLY_ASSIGNED]


async def test_resting_work_order_full_assignment_status_and_event() -> None:
    eng = _engine()
    maker = _work_order(DispatchSide.OFFER, 5, 100, organization_id="M")
    await eng.submit_work_order(maker)
    await eng.submit_work_order(_work_order(DispatchSide.REQUEST, 5, 100, organization_id="T"))

    assert maker.status is WorkOrderStatus.ASSIGNED
    assert maker.updated_at is not None
    maker_assignment_events = [
        e.event_type
        for e in _events_for(eng, maker.work_order_id)
        if e.event_type
        in (DispatchEventType.WORK_ORDER_PARTIALLY_ASSIGNED, DispatchEventType.WORK_ORDER_ASSIGNED)
    ]
    # Consumed in a single assignment -> exactly one WORK_ORDER_ASSIGNED, no partial.
    assert maker_assignment_events == [DispatchEventType.WORK_ORDER_ASSIGNED]


async def test_pre_dispatch_check_receives_none_workload_and_creates_none() -> None:
    seen: list[Workload | None] = []

    class _Recorder:
        def can_dispatch(self, work_order, workload):
            seen.append(workload)
            return False, "no"

    eng = _engine(pre_dispatch_check=_Recorder())
    await eng.submit_work_order(_work_order(DispatchSide.REQUEST, 5, 100, organization_id="fresh"))
    # The check saw None (no pre-existing workload) and none was stored.
    assert seen == [None]
    assert eng.workload_manager.peek_workload("fresh", "CNC-01") is None
    assert eng.workload_manager.all_workloads() == []


# ---------------------------------------------------------------------------
# Aware-UTC timestamp enforcement
# ---------------------------------------------------------------------------

_PLUS2 = timezone(timedelta(hours=2))


def test_defaults_are_aware_utc() -> None:
    order = _work_order(DispatchSide.REQUEST, 1, 100)
    assert order.created_at.tzinfo == UTC
    assignment = ServiceAssignment(
        asset_id="CNC-01",
        requester_work_order_id="r",
        provider_work_order_id="p",
        hourly_rate=D("100"),
        hours=D("1"),
        requester_organization_id="r",
        provider_organization_id="p",
        initiating_side=DispatchSide.REQUEST,
    )
    assert assignment.timestamp.tzinfo == UTC
    assert TelemetryReading("CNC-01", D("1"), D("2"), D("1.5"), 10).timestamp.tzinfo == UTC
    assert DomainEvent().timestamp.tzinfo == UTC


def test_work_order_normalizes_aware_offset_to_utc() -> None:
    naive_wall = datetime(2026, 1, 1, 12, 0, 0)
    order = WorkOrder(
        organization_id="c",
        asset_id="CNC-01",
        side=DispatchSide.REQUEST,
        mode=WorkOrderMode.RATE_CAPPED,
        requested_hours=D("1"),
        max_hourly_rate=D("100"),
        created_at=naive_wall.replace(tzinfo=_PLUS2),
    )
    assert order.created_at.tzinfo == UTC
    assert order.created_at == datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)


def test_work_order_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        WorkOrder(
            organization_id="c",
            asset_id="CNC-01",
            side=DispatchSide.REQUEST,
            mode=WorkOrderMode.RATE_CAPPED,
            requested_hours=D("1"),
            max_hourly_rate=D("100"),
            created_at=datetime(2026, 1, 1, 12, 0, 0),  # naive
        )


def test_assignment_and_workload_reject_naive_and_normalize() -> None:
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=_PLUS2)
    assignment = ServiceAssignment(
        asset_id="CNC-01",
        requester_work_order_id="r",
        provider_work_order_id="p",
        hourly_rate=D("100"),
        hours=D("1"),
        requester_organization_id="r",
        provider_organization_id="p",
        initiating_side=DispatchSide.REQUEST,
        timestamp=ts,
    )
    assert assignment.timestamp == datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        Workload(organization_id="c", asset_id="CNC-01", last_updated=datetime(2026, 1, 1))
    snap = OrganizationSnapshot(organization_id="c", timestamp=ts)
    assert snap.timestamp.tzinfo == UTC
    metrics = OperationalRiskMetrics(computed_at=ts)
    assert metrics.computed_at.tzinfo == UTC


def test_reading_and_event_reject_naive() -> None:
    with pytest.raises(ValueError):
        TelemetryReading("CNC-01", D("1"), D("2"), D("1.5"), 10, timestamp=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        DomainEvent(timestamp=datetime(2026, 1, 1))
    # Aware offset is normalized to UTC.
    ev = DomainEvent(timestamp=datetime(2026, 1, 1, 12, tzinfo=_PLUS2))
    assert ev.timestamp == datetime(2026, 1, 1, 10, tzinfo=UTC)


@pytest.mark.parametrize(
    ("min_reading", "max_reading", "last_reading", "sample_count", "message"),
    [
        ("2", "1", "1.5", 10, "min_reading must not exceed max_reading"),
        ("0", "1", "0.5", 10, "finite and positive"),
        ("1", "2", "1.5", -1, "non-negative integer"),
        ("1", "2", "1.5", True, "non-negative integer"),
    ],
)
def test_reading_rejects_invalid_telemetry_data(
    min_reading: str,
    max_reading: str,
    last_reading: str,
    sample_count: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        TelemetryReading("CNC-01", D(min_reading), D(max_reading), D(last_reading), sample_count)


# ---------------------------------------------------------------------------
# Honest SHIFT / SCHEDULED_END rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("window", [DispatchWindow.SHIFT, DispatchWindow.SCHEDULED_END])
async def test_shift_and_scheduled_end_rejected(window: DispatchWindow) -> None:
    eng = _engine()
    order = _work_order(DispatchSide.REQUEST, 1, 100, dispatch_window=window, organization_id="T")
    result = await eng.submit_work_order(order)
    assert order.status is WorkOrderStatus.REJECTED
    assert result.assignments == []
    reason = _events_for(eng, order.work_order_id)[-1].payload["reason"]
    assert "shift" in reason or "expiry" in reason
    # Nothing rested.
    queue = eng.get_queue("CNC-01")
    assert queue is None or queue.total_work_orders == 0


# ---------------------------------------------------------------------------
# Lifecycle boundaries: updated_at, non-NEW, duplicate work order id
# ---------------------------------------------------------------------------


async def test_updated_at_set_on_accept_and_reject() -> None:
    eng = _engine()
    resting = _work_order(DispatchSide.REQUEST, 1, 99, organization_id="T")
    await eng.submit_work_order(resting)
    assert resting.status is WorkOrderStatus.ACCEPTED
    assert resting.updated_at is not None
    assert resting.updated_at.tzinfo == UTC

    bad = _work_order(DispatchSide.REQUEST, 1, 100, asset_id="ZZZZ", organization_id="T")
    await eng.submit_work_order(bad)
    assert bad.status is WorkOrderStatus.REJECTED
    assert bad.updated_at is not None


async def test_non_new_work_order_rejected() -> None:
    eng = _engine()
    order = _work_order(DispatchSide.REQUEST, 1, 100, organization_id="T")
    order.status = WorkOrderStatus.ACCEPTED  # pretend it was already processed
    result = await eng.submit_work_order(order)
    assert order.status is WorkOrderStatus.REJECTED
    assert result.assignments == []
    assert "only NEW" in _events_for(eng, order.work_order_id)[-1].payload["reason"]


async def test_duplicate_same_object_resubmission_raises_and_preserves_original() -> None:
    eng = _engine()
    resting = _work_order(DispatchSide.REQUEST, 5, 99, organization_id="T")
    await eng.submit_work_order(resting)
    assert resting.status is WorkOrderStatus.ACCEPTED

    with pytest.raises(DuplicateWorkOrderError) as excinfo:
        await eng.submit_work_order(resting)  # same object, already resting
    assert excinfo.value.work_order_id == resting.work_order_id
    # Original is untouched: still ACCEPTED, unassigned, still on the queue.
    assert resting.status is WorkOrderStatus.ACCEPTED
    assert resting.assigned_hours == D("0")
    queue = eng.get_queue("CNC-01")
    assert queue is not None
    assert queue.total_work_orders == 1


async def test_duplicate_distinct_object_same_id_raises() -> None:
    eng = _engine()
    first = _work_order(DispatchSide.REQUEST, 5, 99, organization_id="T")
    await eng.submit_work_order(first)
    clone = WorkOrder(
        work_order_id=first.work_order_id,
        organization_id="T",
        asset_id="CNC-01",
        side=DispatchSide.OFFER,
        mode=WorkOrderMode.RATE_CAPPED,
        requested_hours=D("5"),
        max_hourly_rate=D("101"),
    )
    with pytest.raises(DuplicateWorkOrderError):
        await eng.submit_work_order(clone)
    # The distinct clone is not mutated by the engine.
    assert clone.status is WorkOrderStatus.NEW
    assert first.status is WorkOrderStatus.ACCEPTED


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

    await bus.publish(DomainEvent(event_type=DispatchEventType.SYSTEM_STATUS))
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
    first = WorkOrder(
        work_order_id=oid,
        organization_id="T",
        asset_id="CNC-01",
        side=DispatchSide.REQUEST,
        mode=WorkOrderMode.RATE_CAPPED,
        requested_hours=D("5"),
        max_hourly_rate=D("99"),
    )
    # A distinct object carrying the same id, submitted concurrently.
    second = WorkOrder(
        work_order_id=oid,
        organization_id="T",
        asset_id="CNC-01",
        side=DispatchSide.REQUEST,
        mode=WorkOrderMode.RATE_CAPPED,
        requested_hours=D("3"),
        max_hourly_rate=D("98"),
    )
    results = await asyncio.gather(
        eng.submit_work_order(first),
        eng.submit_work_order(second),
        return_exceptions=True,
    )
    dupes = [r for r in results if isinstance(r, DuplicateWorkOrderError)]
    oks = [r for r in results if isinstance(r, DispatchResult)]
    assert len(dupes) == 1
    assert len(oks) == 1
    assert dupes[0].work_order_id == oid

    winner = oks[0].work_order
    assert winner.status is WorkOrderStatus.ACCEPTED
    # Exactly one work order rested — no duplicate queue entry from the loser.
    queue = eng.get_queue("CNC-01")
    assert queue is not None
    assert queue.total_work_orders == 1

    # The loser emitted no lifecycle events: exactly one SUBMITTED/ACCEPTED
    # exists for the id, both belonging to the winner.
    events = _events_for(eng, oid)
    submitted = [e for e in events if e.event_type is DispatchEventType.WORK_ORDER_SUBMITTED]
    accepted = [e for e in events if e.event_type is DispatchEventType.WORK_ORDER_ACCEPTED]
    assert len(submitted) == 1
    assert len(accepted) == 1


async def test_id_from_rejected_submission_is_not_reusable() -> None:
    eng = _engine()
    oid = "reuse-1"
    rejected = WorkOrder(
        work_order_id=oid,
        organization_id="T",
        asset_id="ZZZZ",  # unknown asset -> boundary rejection
        side=DispatchSide.REQUEST,
        mode=WorkOrderMode.RATE_CAPPED,
        requested_hours=D("1"),
        max_hourly_rate=D("100"),
    )
    result = await eng.submit_work_order(rejected)
    assert rejected.status is WorkOrderStatus.REJECTED
    assert result.assignments == []

    # The id is known permanently even though the submission was rejected.
    reuse = WorkOrder(
        work_order_id=oid,
        organization_id="T",
        asset_id="CNC-01",
        side=DispatchSide.REQUEST,
        mode=WorkOrderMode.RATE_CAPPED,
        requested_hours=D("1"),
        max_hourly_rate=D("100"),
    )
    with pytest.raises(DuplicateWorkOrderError):
        await eng.submit_work_order(reuse)
    # The reuse attempt was not processed at all.
    assert reuse.status is WorkOrderStatus.NEW


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))

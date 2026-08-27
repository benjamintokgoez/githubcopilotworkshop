"""FIFO rate-time priority dispatch engine for the MittelWerk operations
simulation.

Supports ``RATE_CAPPED`` and ``ANY_RATE`` work orders with ``OPEN`` / ``IMMEDIATE``
/ ``COMPLETE`` dispatch-window semantics. Assignments always occur at the
resting (maker) work order's rate.

Work order modes and dispatch windows that would require subsystems the core
does not provide are rejected explicitly rather than behaving dishonestly:

* ``ESCALATION`` and ``ESCALATION_CAPPED`` need a trigger-escalation engine
  (none exists) and are rejected.
* ``SHIFT`` and ``SCHEDULED_END`` need a shift clock / expiry processor (none
  exists); without one they would rest forever, so they are rejected too.
  ``OPEN`` / ``IMMEDIATE`` / ``COMPLETE`` are fully supported.

All lifecycle transitions are published as :class:`DomainEvent` instances via
the :class:`EventBus`, enabling downstream consumers (analytics, workload
manager, dispatch policies) to react asynchronously.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import (
    Protocol,
    runtime_checkable,
)

from mittelwerk.core.events import DispatchEventType, DomainEvent, EventBus
from mittelwerk.core.models import (
    DispatchSide,
    DispatchWindow,
    Equipment,
    ServiceAssignment,
    Workload,
    WorkOrder,
    WorkOrderMode,
    WorkOrderStatus,
    utcnow,
)
from mittelwerk.core.queue import DispatchQueue

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DuplicateWorkOrderError(Exception):
    """Raised when a ``work_order_id`` already known to the engine is submitted
    again. An id becomes known the moment a submission is attempted and stays
    known permanently — including ids whose submission was later rejected or
    stood down — so ids are never reusable on the same engine. Any prior work
    order carrying that id is left untouched. API layers should map this to an
    HTTP 409 Conflict."""

    def __init__(self, work_order_id: str) -> None:
        self.work_order_id = work_order_id
        super().__init__(f"Work order {work_order_id!r} has already been submitted")


# ---------------------------------------------------------------------------
# Pre-dispatch check protocol (structural subtyping)
# ---------------------------------------------------------------------------


@runtime_checkable
class PreDispatchCheck(Protocol):
    """Structural protocol for pre-dispatch validators. Any object
    implementing ``can_dispatch`` is accepted without explicit inheritance."""

    def can_dispatch(
        self, work_order: WorkOrder, workload: Workload | None
    ) -> tuple[bool, str]: ...


# ---------------------------------------------------------------------------
# Submission result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DispatchResult:
    """Result of :meth:`DispatchEngine.submit_work_order`."""

    work_order: WorkOrder
    assignments: list[ServiceAssignment] = field(default_factory=list)
    rejection_reason: str | None = None

    @property
    def accepted(self) -> bool:
        return self.work_order.status is not WorkOrderStatus.REJECTED

    @property
    def assigned_hours(self) -> Decimal:
        return self.work_order.assigned_hours


# ---------------------------------------------------------------------------
# Workload manager — tracks per-organization workloads
# ---------------------------------------------------------------------------


class WorkloadManager:
    """In-memory workload tracker keyed by ``(organization_id, asset_id)``."""

    def __init__(self) -> None:
        self._workloads: dict[tuple[str, str], Workload] = {}

    def get_workload(self, organization_id: str, asset_id: str) -> Workload:
        key = (organization_id, asset_id)
        wl = self._workloads.get(key)
        if wl is None:
            wl = Workload(organization_id=organization_id, asset_id=asset_id)
            self._workloads[key] = wl
        return wl

    def peek_workload(self, organization_id: str, asset_id: str) -> Workload | None:
        """Return an existing workload or ``None`` without creating one."""
        return self._workloads.get((organization_id, asset_id))

    def apply_assignment(
        self,
        organization_id: str,
        asset_id: str,
        side: DispatchSide,
        hours: Decimal,
        rate: Decimal,
    ) -> Workload:
        wl = self.get_workload(organization_id, asset_id)
        wl.apply_assignment(side, hours, rate)
        return wl

    def all_workloads(self) -> list[Workload]:
        return list(self._workloads.values())

    def organization_workloads(self, organization_id: str) -> list[Workload]:
        return [w for w in self._workloads.values() if w.organization_id == organization_id]

    def get_workloads(self, organization_id: str) -> dict[str, Workload]:
        """Return ``{asset_id: Workload}`` for a single organization."""
        return {asset: w for (org, asset), w in self._workloads.items() if org == organization_id}

    def reprice_asset(self, asset_id: str, mark_rate: Decimal) -> None:
        for (_, asset), wl in self._workloads.items():
            if asset == asset_id and wl.net_hours != 0:
                wl.reprice(mark_rate)


# ---------------------------------------------------------------------------
# Dispatch Engine
# ---------------------------------------------------------------------------


class DispatchEngine:
    """FIFO rate-time priority dispatch engine.

    For each incoming work order the engine:

    0. Rejects duplicate ``work_order_id`` submissions (raising
       :class:`DuplicateWorkOrderError`) and any non-``NEW`` work order.
    1. Validates the work order against equipment reference data (known asset,
       rate increment, hour lot size) and rejects unsupported modes
       (``ESCALATION``/``ESCALATION_CAPPED``) and dispatch windows
       (``SHIFT``/``SCHEDULED_END``).
    2. Runs the optional pre-dispatch check with the existing workload or None.
    3. Matches against the opposite side of the queue at the resting rate.
    4. Handles the residual per dispatch window: ``OPEN`` rate-capped orders
       rest, ``IMMEDIATE``/``ANY_RATE`` residuals stand down (terminal), and
       ``COMPLETE`` never partially assigns.
    5. Publishes accepted / rejected / partial / assigned / cancelled events
       for both the incoming work order and every resting work order it
       touches.
    """

    def __init__(
        self,
        event_bus: EventBus,
        equipment: Mapping[str, Equipment] | None = None,
        pre_dispatch_check: PreDispatchCheck | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._equipment: dict[str, Equipment] = dict(equipment) if equipment else {}
        self._pre_dispatch_check = pre_dispatch_check
        self._queues: dict[str, DispatchQueue] = {}
        self._workload_manager = WorkloadManager()
        self._assignment_log: list[ServiceAssignment] = []
        self._work_order_count = 0
        self._known_work_order_ids: set[str] = set()

    # -- Queue management -------------------------------------------------

    def get_or_create_queue(self, asset_id: str) -> DispatchQueue:
        queue = self._queues.get(asset_id)
        if queue is None:
            queue = DispatchQueue(asset_id)
            self._queues[asset_id] = queue
        return queue

    def get_queue(self, asset_id: str) -> DispatchQueue | None:
        return self._queues.get(asset_id)

    @property
    def queues(self) -> dict[str, DispatchQueue]:
        return dict(self._queues)

    @property
    def equipment(self) -> dict[str, Equipment]:
        return dict(self._equipment)

    @property
    def workload_manager(self) -> WorkloadManager:
        return self._workload_manager

    @property
    def assignment_log(self) -> list[ServiceAssignment]:
        return list(self._assignment_log)

    @property
    def work_order_count(self) -> int:
        return self._work_order_count

    def all_workloads(self) -> list[Workload]:
        return self._workload_manager.all_workloads()

    def organization_workloads(self, organization_id: str) -> list[Workload]:
        return self._workload_manager.organization_workloads(organization_id)

    # -- Boundary validation --------------------------------------------

    def _validate_boundary(self, work_order: WorkOrder) -> tuple[bool, str]:
        """Validate a work order against reference data and supported modes."""
        if work_order.mode in (WorkOrderMode.ESCALATION, WorkOrderMode.ESCALATION_CAPPED):
            return (
                False,
                f"{work_order.mode.value} work orders are not supported: no "
                "escalation-trigger engine is configured",
            )

        if work_order.dispatch_window in (DispatchWindow.SHIFT, DispatchWindow.SCHEDULED_END):
            return (
                False,
                f"{work_order.dispatch_window.value} dispatch window is not supported: no "
                "shift-clock / expiry subsystem is configured",
            )

        if self._equipment:
            equipment = self._equipment.get(work_order.asset_id)
            if equipment is None:
                return False, f"Unknown asset: {work_order.asset_id}"
            if not equipment.is_valid_hours(work_order.requested_hours):
                return (
                    False,
                    f"Hours {work_order.requested_hours} is not a multiple of hour lot size "
                    f"{equipment.hour_lot_size}",
                )
            if work_order.max_hourly_rate is not None and not equipment.is_valid_rate(
                work_order.max_hourly_rate
            ):
                return (
                    False,
                    f"Rate {work_order.max_hourly_rate} is not a multiple of rate increment "
                    f"{equipment.rate_increment}",
                )
        return True, ""

    # -- Work order submission ------------------------------------------------

    async def submit_work_order(self, work_order: WorkOrder) -> DispatchResult:
        # Duplicate-id guard first: never mutate or re-emit for a work order id
        # the engine already knows (this includes same-object resubmission of a
        # resting work order).  Raised cleanly so the API can map it to HTTP 409.
        #
        # The id is reserved *synchronously* here — before the first await —
        # so two concurrent submissions of the same id cannot both pass the
        # guard.  The reservation is permanent: every attempted submission id
        # (including ones that go on to be rejected or stood down) is known
        # thereafter and can never be reused on this engine.
        if work_order.work_order_id in self._known_work_order_ids:
            raise DuplicateWorkOrderError(work_order.work_order_id)
        self._known_work_order_ids.add(work_order.work_order_id)

        self._work_order_count += 1
        await self._publish_work_order_event(DispatchEventType.WORK_ORDER_SUBMITTED, work_order)

        # Only fresh (NEW) work orders may enter the engine.
        if work_order.status is not WorkOrderStatus.NEW:
            return await self._reject(
                work_order,
                f"cannot submit work order in status {work_order.status.value}; only NEW "
                "work orders may be submitted",
            )

        ok, reason = self._validate_boundary(work_order)
        if not ok:
            return await self._reject(work_order, reason)

        queue = self.get_or_create_queue(work_order.asset_id)

        # Pre-dispatch check — pass the existing workload (or None); never
        # create a zero workload just to run the check.
        if self._pre_dispatch_check is not None:
            wl = self._workload_manager.peek_workload(
                work_order.organization_id, work_order.asset_id
            )
            allowed, check_reason = self._pre_dispatch_check.can_dispatch(work_order, wl)
            if not allowed:
                if not isinstance(check_reason, str):
                    raise TypeError("pre-dispatch check reason must be a string")
                return await self._reject(
                    work_order, check_reason.strip() or "Pre-dispatch check failed"
                )

        # The work order is now admitted to the engine.
        work_order.status = WorkOrderStatus.ACCEPTED
        work_order.updated_at = utcnow()
        await self._publish_work_order_event(DispatchEventType.WORK_ORDER_ACCEPTED, work_order)

        # COMPLETE is an accepted work order that is stood down (cancelled)
        # without any assignment if it cannot be fully assigned; capacity
        # stays untouched.
        if work_order.dispatch_window is DispatchWindow.COMPLETE and not self._can_assign_fully(
            work_order, queue
        ):
            work_order.status = WorkOrderStatus.CANCELLED
            work_order.updated_at = utcnow()
            await self._publish_work_order_event(
                DispatchEventType.WORK_ORDER_CANCELLED,
                work_order,
                {"reason": "COMPLETE work order could not be fully assigned"},
            )
            return DispatchResult(work_order=work_order, assignments=[])

        assignments_with_resting = self._match(work_order, queue)
        assignments = [assignment for assignment, _ in assignments_with_resting]
        for assignment, resting in assignments_with_resting:
            self._assignment_log.append(assignment)
            await self._publish_assignment_event(assignment, work_order)
            # Every resting work order touched by the match is finalised too.
            await self._publish_resting_assignment(resting)

        if assignments:
            last_rate = assignments[-1].hourly_rate
            self._workload_manager.reprice_asset(work_order.asset_id, last_rate)

        await self._finalise(work_order, queue, assignments)
        return DispatchResult(work_order=work_order, assignments=assignments)

    async def _finalise(
        self, work_order: WorkOrder, queue: DispatchQueue, assignments: list[ServiceAssignment]
    ) -> None:
        if work_order.is_fully_assigned:
            work_order.status = WorkOrderStatus.ASSIGNED
            work_order.updated_at = utcnow()
            await self._publish_work_order_event(DispatchEventType.WORK_ORDER_ASSIGNED, work_order)
            return

        # There is residual hours — first surface any partial assignment.
        if assignments:
            work_order.status = WorkOrderStatus.PARTIALLY_ASSIGNED
            work_order.updated_at = utcnow()
            await self._publish_work_order_event(
                DispatchEventType.WORK_ORDER_PARTIALLY_ASSIGNED, work_order
            )

        # Only OPEN rate-capped residuals rest; SHIFT/SCHEDULED_END are
        # rejected at the boundary because there is no shift/expiry subsystem
        # to retire them.
        rest_allowed = (
            work_order.mode is WorkOrderMode.RATE_CAPPED
            and work_order.dispatch_window is DispatchWindow.OPEN
        )
        if rest_allowed:
            # Residual joins the queue and stays active (PARTIALLY_ASSIGNED or,
            # if nothing assigned, the already-published ACCEPTED state).
            queue.add_work_order(work_order)
            return

        # ANY_RATE / IMMEDIATE (and any COMPLETE residual) stand down the
        # remainder — no immediate-rate work order ever rests. The work order
        # always ends in a terminal CANCELLED state, even when it was
        # partially assigned first.
        work_order.status = WorkOrderStatus.CANCELLED
        work_order.updated_at = utcnow()
        reason = (
            "IMMEDIATE residual stood down"
            if work_order.dispatch_window is DispatchWindow.IMMEDIATE
            else "ANY_RATE work order residual stood down (no capacity)"
        )
        await self._publish_work_order_event(
            DispatchEventType.WORK_ORDER_CANCELLED, work_order, {"reason": reason}
        )

    async def _reject(self, work_order: WorkOrder, reason: str) -> DispatchResult:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("rejection reason must be a non-empty string")
        reason = reason.strip()
        work_order.status = WorkOrderStatus.REJECTED
        work_order.updated_at = utcnow()
        await self._publish_work_order_event(
            DispatchEventType.WORK_ORDER_REJECTED, work_order, {"reason": reason}
        )
        logger.info("Rejected work order %s: %s", work_order.work_order_id, reason)
        return DispatchResult(work_order=work_order, assignments=[], rejection_reason=reason)

    # -- Matching logic --------------------------------------------------

    def _match(
        self, incoming: WorkOrder, queue: DispatchQueue
    ) -> list[tuple[ServiceAssignment, WorkOrder]]:
        """Match ``incoming`` and return ``(assignment, resting_work_order)``
        pairs so the caller can finalise each touched resting work order
        exactly once."""
        assignments: list[tuple[ServiceAssignment, WorkOrder]] = []

        while incoming.remaining_hours > 0:
            if incoming.side is DispatchSide.REQUEST:
                resting = queue.peek_best_offer_order()
            else:
                resting = queue.peek_best_request_order()
            if resting is None:
                break
            resting_rate = resting.max_hourly_rate
            if resting_rate is None:
                raise RuntimeError(
                    "dispatch queue invariant violated: resting work order has no rate"
                )

            # Rate-capped work orders only cross when the rate is acceptable.
            if incoming.mode is WorkOrderMode.RATE_CAPPED:
                incoming_rate = incoming.max_hourly_rate
                if incoming_rate is None:
                    raise RuntimeError(
                        "work order invariant violated: rate-capped order has no rate"
                    )
                if incoming.side is DispatchSide.REQUEST and incoming_rate < resting_rate:
                    break
                if incoming.side is DispatchSide.OFFER and incoming_rate > resting_rate:
                    break

            assign_hours = min(incoming.remaining_hours, resting.remaining_hours)
            assignment = self._execute_assignment(incoming, resting, assign_hours, resting_rate)
            assignments.append((assignment, resting))

            if resting.is_fully_assigned:
                if incoming.side is DispatchSide.REQUEST:
                    queue.pop_best_offer()
                else:
                    queue.pop_best_request()

        return assignments

    def _execute_assignment(
        self,
        incoming: WorkOrder,
        resting: WorkOrder,
        hours: Decimal,
        rate: Decimal,
    ) -> ServiceAssignment:
        now = utcnow()

        incoming.average_service_rate = self._compute_avg_rate(
            incoming.average_service_rate, incoming.assigned_hours, rate, hours
        )
        incoming.assigned_hours += hours
        incoming.updated_at = now

        resting.average_service_rate = self._compute_avg_rate(
            resting.average_service_rate, resting.assigned_hours, rate, hours
        )
        resting.assigned_hours += hours
        resting.updated_at = now
        resting.status = (
            WorkOrderStatus.ASSIGNED
            if resting.is_fully_assigned
            else WorkOrderStatus.PARTIALLY_ASSIGNED
        )

        if incoming.side is DispatchSide.REQUEST:
            requester, provider = incoming, resting
        else:
            requester, provider = resting, incoming

        assignment = ServiceAssignment(
            asset_id=incoming.asset_id,
            requester_work_order_id=requester.work_order_id,
            provider_work_order_id=provider.work_order_id,
            hourly_rate=rate,
            hours=hours,
            requester_organization_id=requester.organization_id,
            provider_organization_id=provider.organization_id,
            initiating_side=incoming.side,
            timestamp=now,
        )

        self._workload_manager.apply_assignment(
            requester.organization_id, incoming.asset_id, DispatchSide.REQUEST, hours, rate
        )
        self._workload_manager.apply_assignment(
            provider.organization_id, incoming.asset_id, DispatchSide.OFFER, hours, rate
        )

        logger.info(
            "Assignment: %s %s hours=%s @ %s | requester=%s provider=%s",
            incoming.asset_id,
            incoming.side.value,
            hours,
            rate,
            requester.organization_id,
            provider.organization_id,
        )
        return assignment

    @staticmethod
    def _compute_avg_rate(
        prev_avg: Decimal | None,
        prev_hours: Decimal,
        new_rate: Decimal,
        new_hours: Decimal,
    ) -> Decimal:
        if prev_avg is None or prev_hours == 0:
            return new_rate
        total_cost = prev_avg * prev_hours + new_rate * new_hours
        return total_cost / (prev_hours + new_hours)

    def _can_assign_fully(self, work_order: WorkOrder, queue: DispatchQueue) -> bool:
        """Return True if ``work_order`` can be fully assigned against current
        capacity without consuming it (used for COMPLETE pre-checks)."""
        needed = work_order.remaining_hours
        available = Decimal("0")
        is_rate_capped = work_order.mode is WorkOrderMode.RATE_CAPPED
        if work_order.side is DispatchSide.REQUEST:
            for level in queue.offer_levels(depth=1_000_000):
                if (
                    is_rate_capped
                    and work_order.max_hourly_rate is not None
                    and level.rate > work_order.max_hourly_rate
                ):
                    break
                available += level.total_hours
                if available >= needed:
                    return True
        else:
            for level in queue.request_levels(depth=1_000_000):
                if (
                    is_rate_capped
                    and work_order.max_hourly_rate is not None
                    and level.rate < work_order.max_hourly_rate
                ):
                    break
                available += level.total_hours
                if available >= needed:
                    return True
        return available >= needed

    # -- Cancel -----------------------------------------------------------

    async def cancel_work_order(
        self, work_order_id: str, asset_id: str | None = None
    ) -> WorkOrder | None:
        queues: list[DispatchQueue]
        if asset_id is not None:
            queue = self._queues.get(asset_id)
            queues = [queue] if queue is not None else []
        else:
            queues = list(self._queues.values())

        for queue in queues:
            work_order = queue.cancel_work_order(work_order_id)
            if work_order is not None:
                work_order.status = WorkOrderStatus.CANCELLED
                work_order.updated_at = utcnow()
                await self._publish_work_order_event(
                    DispatchEventType.WORK_ORDER_CANCELLED,
                    work_order,
                    {"reason": "Client requested"},
                )
                return work_order
        return None

    # -- Event publishing -------------------------------------------------

    async def _publish_work_order_event(
        self,
        event_type: DispatchEventType,
        work_order: WorkOrder,
        extra: dict[str, object] | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "work_order_id": work_order.work_order_id,
            "organization_id": work_order.organization_id,
            "asset_id": work_order.asset_id,
            "side": work_order.side.value,
            "mode": work_order.mode.value,
            "requested_hours": str(work_order.requested_hours),
            "assigned_hours": str(work_order.assigned_hours),
            "status": work_order.status.value,
        }
        if extra:
            payload.update(extra)
        await self._event_bus.publish(
            DomainEvent(
                event_type=event_type,
                source="dispatch_engine",
                correlation_id=work_order.work_order_id,
                payload=payload,
            )
        )

    async def _publish_resting_assignment(self, resting: WorkOrder) -> None:
        """Publish the lifecycle event for a resting work order touched by a
        match — exactly once per assignment, mirroring the status set in
        :meth:`_execute_assignment`."""
        event_type = (
            DispatchEventType.WORK_ORDER_ASSIGNED
            if resting.is_fully_assigned
            else DispatchEventType.WORK_ORDER_PARTIALLY_ASSIGNED
        )
        await self._publish_work_order_event(event_type, resting)

    async def _publish_assignment_event(
        self, assignment: ServiceAssignment, work_order: WorkOrder
    ) -> None:
        await self._event_bus.publish(
            DomainEvent(
                event_type=DispatchEventType.ASSIGNMENT_EXECUTED,
                source="dispatch_engine",
                correlation_id=work_order.work_order_id,
                payload={
                    "assignment_id": assignment.assignment_id,
                    "asset_id": assignment.asset_id,
                    "hourly_rate": str(assignment.hourly_rate),
                    "hours": str(assignment.hours),
                    "requester_work_order_id": assignment.requester_work_order_id,
                    "provider_work_order_id": assignment.provider_work_order_id,
                    "initiating_side": assignment.initiating_side.value,
                },
            )
        )
        await self._event_bus.publish(
            DomainEvent(
                event_type=DispatchEventType.WORKLOAD_UPDATED,
                source="dispatch_engine",
                correlation_id=work_order.work_order_id,
                payload={
                    "asset_id": assignment.asset_id,
                    "requester_organization_id": assignment.requester_organization_id,
                    "provider_organization_id": assignment.provider_organization_id,
                    "hourly_rate": str(assignment.hourly_rate),
                    "hours": str(assignment.hours),
                },
            )
        )


__all__ = [
    "DuplicateWorkOrderError",
    "PreDispatchCheck",
    "DispatchResult",
    "WorkloadManager",
    "DispatchEngine",
]

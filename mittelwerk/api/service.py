"""Application services shared by the REST routes.

Everything here lives on the FastAPI ``app.state`` of a single application
instance — there are no module-level singletons, so two applications created
in the same process are fully isolated.

The service layer owns the API-local bookkeeping that the core deliberately
does not: which work orders were submitted through the API by which
organization, and a per-organization cost trajectory used by the dashboard
chart. Work orders are kept as live references, so status transitions made by
the engine are visible immediately.

It is also the integration point for persistence: every service assignment
produced by a successful submission is written to the configured
:class:`~mittelwerk.telemetry.store.TelemetryStore` off the event loop.
Dispatch happens in memory and cannot be rolled back, so this boundary is
explicitly non-atomic — a persistence failure raises
:class:`AssignmentPersistenceError` *after* execution and the API reports
exactly that.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from mittelwerk.analytics.operations import OperationsAnalytics
from mittelwerk.core.engine import DispatchEngine, DispatchResult
from mittelwerk.core.events import EventBus
from mittelwerk.core.models import Equipment, ServiceAssignment, Workload, WorkOrder, utcnow
from mittelwerk.telemetry.store import TelemetryStore

logger = logging.getLogger(__name__)

#: Default display currency for the DACH audience. The platform performs no FX
#: conversion — the label states the reporting unit, nothing more.
DEFAULT_DISPLAY_CURRENCY = "EUR"
#: Bound on the retained per-organization cost trajectory.
COST_HISTORY_LIMIT = 500
#: Dispatch-queue depth included in the dashboard payload.
DASHBOARD_QUEUE_DEPTH = 10


class AssignmentPersistenceError(RuntimeError):
    """Raised when executed assignments could not be written to the store.

    The execution itself stands: the in-memory engine is authoritative and the
    work order keeps whatever status the dispatch produced. The error carries
    only reconciliation identifiers — never store internals or credentials,
    which stay in the server log with the original exception attached as
    ``__cause__``.
    """

    def __init__(self, work_order: WorkOrder, assignments: Iterable[ServiceAssignment]) -> None:
        self.work_order_id = work_order.work_order_id
        self.work_order_status = work_order.status.value
        self.assigned_hours = str(work_order.assigned_hours)
        self.assignment_ids = [assignment.assignment_id for assignment in assignments]
        super().__init__(
            f"Work order {work_order.work_order_id!r} executed but "
            f"{len(self.assignment_ids)} assignment(s) could not be persisted"
        )


@dataclass(frozen=True)
class DispatchSubmissionResult:
    """Engine submission plus its directly reported rejection reason."""

    submission: DispatchResult
    rejection_reason: str | None = None

    @property
    def work_order(self) -> WorkOrder:
        return self.submission.work_order

    @property
    def assignments(self) -> list[ServiceAssignment]:
        return list(self.submission.assignments)

    @property
    def accepted(self) -> bool:
        return self.submission.accepted


@dataclass
class _OrganizationBook:
    """Per-organization API bookkeeping."""

    work_orders: dict[str, WorkOrder] = field(default_factory=dict)
    cost_history: deque[tuple[datetime, Decimal]] = field(
        default_factory=lambda: deque(maxlen=COST_HISTORY_LIMIT)
    )
    analytics: OperationsAnalytics | None = None


class DispatchService:
    """Organization-scoped view over the shared dispatch engine."""

    def __init__(
        self,
        engine: DispatchEngine,
        event_bus: EventBus,
        *,
        display_currency: str = DEFAULT_DISPLAY_CURRENCY,
        hours_volatility: float | None = None,
        store: TelemetryStore | None = None,
    ) -> None:
        if (
            not isinstance(display_currency, str)
            or len(display_currency.strip()) != 3
            or not display_currency.strip().isascii()
            or not display_currency.strip().isalpha()
        ):
            raise ValueError("display_currency must be a 3-letter ASCII currency code")
        if hours_volatility is not None:
            if isinstance(hours_volatility, bool) or not isinstance(hours_volatility, (int, float)):
                raise TypeError("hours_volatility must be a number or None")
            if hours_volatility <= 0:
                raise ValueError("hours_volatility must be positive")
        self._engine = engine
        self._event_bus = event_bus
        self._display_currency = display_currency.strip().upper()
        self._hours_volatility = float(hours_volatility) if hours_volatility else None
        self._store = store
        self._equipment_currencies = {
            asset_id: equipment.currency for asset_id, equipment in self._engine.equipment.items()
        }
        self._books: dict[str, _OrganizationBook] = {}

    # -- Accessors --------------------------------------------------------

    @property
    def engine(self) -> DispatchEngine:
        return self._engine

    @property
    def display_currency(self) -> str:
        return self._display_currency

    @property
    def store(self) -> TelemetryStore | None:
        """The configured store, or ``None`` when persistence is disabled."""
        return self._store

    def _book(self, organization_id: str) -> _OrganizationBook:
        book = self._books.get(organization_id)
        if book is None:
            book = _OrganizationBook()
            self._books[organization_id] = book
        return book

    def analytics_for(self, organization_id: str) -> OperationsAnalytics:
        """Return the organization's analytics view, bound to that
        organization's workloads.

        Binding a ``workload_provider`` per organization keeps counterparties
        from netting each other out in a shared analytics view.
        """
        book = self._book(organization_id)
        if book.analytics is None:

            def provider() -> list[Workload]:
                return self._engine.organization_workloads(organization_id)

            book.analytics = OperationsAnalytics(
                organization_id=organization_id,
                workload_provider=provider,
            )
        return book.analytics

    def work_orders_for(self, organization_id: str) -> list[WorkOrder]:
        """Return the organization's API-submitted work orders, newest last."""
        work_orders = list(self._book(organization_id).work_orders.values())
        return sorted(work_orders, key=lambda wo: (wo.created_at, wo.work_order_id))

    def get_work_order(self, organization_id: str, work_order_id: str) -> WorkOrder | None:
        return self._book(organization_id).work_orders.get(work_order_id)

    def active_work_order_count(self, organization_id: str) -> int:
        return sum(1 for wo in self._book(organization_id).work_orders.values() if wo.is_active)

    def workloads_for(self, organization_id: str) -> list[Workload]:
        return self._engine.organization_workloads(organization_id)

    def currency_for_asset(self, asset_id: str) -> str:
        """Return the configured equipment currency for ``asset_id``."""
        try:
            return self._equipment_currencies[asset_id]
        except KeyError as exc:
            raise RuntimeError(
                f"Workload asset {asset_id!r} has no configured equipment currency"
            ) from exc

    # -- Work order flow -------------------------------------------------------

    async def submit_work_order(
        self, organization_id: str, work_order: WorkOrder
    ) -> DispatchSubmissionResult:
        """Submit ``work_order`` to the engine and register it for this
        organization.

        :class:`~mittelwerk.core.engine.DuplicateWorkOrderError` propagates
        untouched so the route can answer 409 without either work order being
        mutated.

        Executed assignments are persisted after the dispatch. A persistence
        failure raises :class:`AssignmentPersistenceError`; the work order
        stays registered with its real, executed status because the dispatch
        cannot be undone.
        """
        if work_order.organization_id != organization_id:
            raise ValueError("work_order organization_id must match the authenticated organization")
        submission = await self._engine.submit_work_order(work_order)
        self._book(organization_id).work_orders[work_order.work_order_id] = work_order
        self._record_cost(submission.assignments)
        await self._persist_assignments(work_order, submission.assignments)
        return DispatchSubmissionResult(
            submission=submission,
            rejection_reason=submission.rejection_reason,
        )

    # -- Persistence -------------------------------------------------------

    async def _persist_assignments(
        self, work_order: WorkOrder, assignments: Iterable[ServiceAssignment]
    ) -> None:
        """Write executed assignments to the store without blocking the event loop.

        ``store is None`` is the one benign case: persistence is intentionally
        off (see ``create_app(enable_store=False)``) and that is reported at
        startup rather than hidden here. A *configured* store that is closed is
        not benign — the deployment expects persistence and is not getting it
        — so it raises the same :class:`AssignmentPersistenceError` as a write
        failure.
        """
        executed = list(assignments)
        if not executed:
            return
        store = self._store
        if store is None:
            return
        if store.is_closed:
            logger.error(
                "Cannot persist %d executed assignment(s) for work order %s: the "
                "configured telemetry store is closed",
                len(executed),
                work_order.work_order_id,
            )
            raise AssignmentPersistenceError(work_order, executed)

        payloads = [
            {
                "assignment_id": assignment.assignment_id,
                "asset_id": assignment.asset_id,
                "requester_work_order_id": assignment.requester_work_order_id,
                "provider_work_order_id": assignment.provider_work_order_id,
                "hourly_rate": assignment.hourly_rate,
                "hours": assignment.hours,
                "requester_organization_id": assignment.requester_organization_id,
                "provider_organization_id": assignment.provider_organization_id,
                "timestamp": assignment.timestamp,
            }
            for assignment in executed
        ]
        try:
            await asyncio.to_thread(store.insert_assignments, payloads)
        except Exception as exc:  # translated, logged, and re-raised — never hidden
            logger.exception(
                "Persisting %d executed assignment(s) for work order %s failed",
                len(executed),
                work_order.work_order_id,
            )
            raise AssignmentPersistenceError(work_order, executed) from exc

    async def cancel_work_order(self, organization_id: str, work_order_id: str) -> WorkOrder | None:
        """Cancel a resting work order owned by ``organization_id``.

        Returns ``None`` when the work order is not resting (already
        terminal). Ownership is checked by the caller through
        :meth:`get_work_order`.
        """
        owned = self.get_work_order(organization_id, work_order_id)
        if owned is None:
            raise KeyError(work_order_id)
        return await self._engine.cancel_work_order(work_order_id, owned.asset_id)

    # -- Cost trajectory ----------------------------------------------------

    def _record_cost(self, assignments: Iterable[ServiceAssignment]) -> None:
        """Append one cost observation per organization touched by
        ``assignments``.

        The series is event-driven and therefore deterministic for a given
        work order flow: no assignments means no points.
        """
        assignment_list = list(assignments)
        if not assignment_list:
            return
        stamp = assignment_list[-1].timestamp
        organizations = {a.requester_organization_id for a in assignment_list}
        organizations.update(a.provider_organization_id for a in assignment_list)
        for organization_id in sorted(organizations):
            total = sum(
                (w.total_cost for w in self._engine.organization_workloads(organization_id)),
                Decimal("0"),
            )
            self._book(organization_id).cost_history.append((stamp, total))

    def cost_history(self, organization_id: str) -> list[dict[str, str]]:
        return [
            {"timestamp": stamp.isoformat(), "value": str(value)}
            for stamp, value in self._book(organization_id).cost_history
        ]

    # -- Dashboard ---------------------------------------------------------

    def risk_payload(self, organization_id: str) -> dict[str, Any]:
        """Operational risk figures for the organization.

        ``backlog_risk_95`` / ``backlog_risk_99`` are ``None`` unless an hours
        volatility assumption is configured — the platform does not invent
        one.
        """
        analytics = self.analytics_for(organization_id)
        metrics = analytics.operational_metrics(hours_volatility=self._hours_volatility)
        has_risk = self._hours_volatility is not None
        return {
            "backlog_risk_95": str(metrics.backlog_hours_at_risk_95) if has_risk else None,
            "backlog_risk_99": str(metrics.backlog_hours_at_risk_99) if has_risk else None,
            "utilization_rate": str(metrics.utilization_rate),
            "sla_compliance_rate": str(metrics.sla_compliance_rate),
            "average_lead_time_hours": str(metrics.average_lead_time_hours),
            "service_level_ratio": analytics.service_level_ratio(),
            "max_backlog_overrun": analytics.max_backlog_overrun(),
            "gross_committed_hours": str(analytics.gross_committed_hours),
            "computed_at": metrics.computed_at.isoformat(),
        }

    def workload_payload(self, organization_id: str) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for workload in sorted(self.workloads_for(organization_id), key=lambda w: w.asset_id):
            last_rate = workload.last_rate
            payload.append(
                {
                    "asset_id": workload.asset_id,
                    "currency": self.currency_for_asset(workload.asset_id),
                    "net_hours": str(workload.net_hours),
                    "average_service_rate": str(workload.average_service_rate),
                    "last_rate": None if last_rate is None else str(last_rate),
                    "exposure_value": str(workload.exposure_value()),
                    "realized_cost": str(workload.realized_cost),
                    "unrealized_cost": str(workload.unrealized_cost),
                    "total_cost": str(workload.total_cost),
                }
            )
        return payload

    def dispatch_queue_payload(
        self, depth: int = DASHBOARD_QUEUE_DEPTH
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """Public dispatch-queue depth per asset; empty queues are included honestly."""
        return {
            asset_id: queue.depth_snapshot(levels=depth)
            for asset_id, queue in sorted(self._engine.queues.items())
        }

    def dashboard_payload(self, organization_id: str) -> dict[str, Any]:
        """Assemble the dashboard contract for one authenticated organization."""
        analytics = self.analytics_for(organization_id)
        workloads = self.workload_payload(organization_id)
        risk = self.risk_payload(organization_id)
        snapshot = analytics.snapshot()
        return {
            "as_of": utcnow(),
            "currency": self._display_currency,
            "kpis": {
                "exposure_value": str(analytics.total_exposure_value),
                "realized_cost": str(snapshot.total_realized_cost),
                "unrealized_cost": str(snapshot.total_unrealized_cost),
                "backlog_risk_95": risk["backlog_risk_95"],
                "active_work_orders": self.active_work_order_count(organization_id),
            },
            "workloads": workloads,
            "cost_history": self.cost_history(organization_id),
            "risk": risk,
            "dispatch_queues": self.dispatch_queue_payload(),
        }


def search_equipment_in_memory(
    equipment: Mapping[str, Equipment], query: str, limit: int
) -> list[dict[str, str]]:
    """Case-insensitive substring search over in-memory reference data.

    Used when no database is configured. The term is compared with plain
    string containment, so SQL metacharacters carry no meaning at all.
    """
    term = query.strip().casefold()
    matches = [
        item
        for item in equipment.values()
        if term in item.asset_id.casefold() or term in item.name.casefold()
    ]
    matches.sort(key=lambda item: item.asset_id)
    return [
        {
            "asset_id": item.asset_id,
            "name": item.name,
            "equipment_type": item.equipment_type.value,
            "currency": item.currency,
            "site_code": item.site_code,
            "hourly_service_rate": str(item.hourly_service_rate),
            "rate_increment": str(item.rate_increment),
            "hour_lot_size": str(item.hour_lot_size),
        }
        for item in matches[:limit]
    ]


__all__ = [
    "DEFAULT_DISPLAY_CURRENCY",
    "COST_HISTORY_LIMIT",
    "DASHBOARD_QUEUE_DEPTH",
    "AssignmentPersistenceError",
    "DispatchSubmissionResult",
    "DispatchService",
    "search_equipment_in_memory",
]

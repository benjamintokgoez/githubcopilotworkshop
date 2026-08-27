"""REST endpoints for the MittelWerk educational field-service operations
simulation.

Contract summary (prefix ``/api/v1``, header ``X-API-Key``):

=================================== ============ ===========================
Endpoint                            Permission   Notes
=================================== ============ ===========================
``GET  /health``                    public       liveness, aware-UTC
                                                 timestamp; ``degraded`` when
                                                 a configured telemetry feed
                                                 has stopped
``POST /work-orders``               ``dispatch`` JSON body, identity from key
``GET  /work-orders``                ``read``     only the caller's own work orders
``GET  /work-orders/{id}``           ``read``     404 when not owned
``DELETE /work-orders/{id}``         ``dispatch`` 404 when not owned, 409 when
                                                 the work order is no longer resting
``GET  /workloads``                  ``read``     caller-scoped
``GET  /organization/snapshot``      ``read``     caller-scoped
``GET  /organization/risk``          ``read``     caller-scoped
``GET  /equipment/search``           ``read``     bounded, parameterised
``GET  /dispatch-policies``          ``read``     registered policy names
``GET  /metrics``                    ``read``     process metrics snapshot
``GET  /dashboard``                  ``read``     dashboard payload contract
=================================== ============ ===========================

Error contract for ``POST /work-orders``:

* ``422`` — the body failed schema validation. This includes a
  client-supplied ``work_order_id`` outside the URL-path-segment-safe
  character set (``[A-Za-z0-9._:-]``, at most 64 characters); such a request
  never reaches the dispatch engine, so no id is reserved.
* ``400`` with ``detail.error == "invalid_work_order"`` — the body is
  schema-valid but violates a domain invariant (for example a RATE_CAPPED
  work order without a rate).
* ``400`` with ``detail.error == "work_order_rejected"`` — the dispatch
  engine rejected the work order (unknown asset, rate/hours-lot violation,
  unsupported ESCALATION mode or SHIFT/SCHEDULED_END dispatch window, failed
  pre-dispatch check). ``detail.reason`` carries the engine's own wording.
* ``409`` with ``detail.error == "duplicate_work_order_id"`` — the id was
  already submitted. Neither the original nor the duplicate request is
  mutated.
* ``500`` with ``detail.error == "assignment_persistence_failed"`` — the work
  order executed but its assignments could not be written to the store.
  Execution is not rolled back (the engine is in-memory and authoritative);
  the response names the affected work order and assignment ids so an
  operator can reconcile, and contains no store internals.

``GET /equipment/search`` trims ``q`` at the boundary and answers ``422`` for
blank or whitespace-only input, identically with and without a store.

``GET /health`` stays ``200`` in every state: ``status`` is ``healthy`` or
``degraded`` and ``feed`` is ``off``/``running``/``stopped``. Failure
*reasons* are logged, never returned, because the endpoint is unauthenticated.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from pydantic import AfterValidator, ValidationError

from mittelwerk.api.dependencies import (
    AppServices,
    DispatchPrincipalDep,
    ReadPrincipalDep,
    ServicesDep,
)
from mittelwerk.api.schemas import (
    WORK_ORDER_ID_MAX_LENGTH,
    WORK_ORDER_ID_PATTERN,
    CancellationResponse,
    DashboardResponse,
    DispatchPolicyListResponse,
    EquipmentSearchResponse,
    HealthResponse,
    WorkloadListResponse,
    WorkOrderListResponse,
    WorkOrderRequest,
    WorkOrderSubmissionResponse,
)
from mittelwerk.api.service import AssignmentPersistenceError, search_equipment_in_memory
from mittelwerk.core.engine import DuplicateWorkOrderError
from mittelwerk.core.models import utcnow
from mittelwerk.dispatch_policies.base import DispatchPolicyMeta
from mittelwerk.utils.metrics import REGISTRY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["dispatch"])

#: Upper bound on equipment search results returned in a single response.
MAX_SEARCH_RESULTS = 100
#: Upper bound on the length of an equipment search term.
MAX_SEARCH_QUERY_LENGTH = 64

#: Liveness values reported by ``GET /health``.
STATUS_HEALTHY = "healthy"
STATUS_DEGRADED = "degraded"
#: Telemetry feed states reported by ``GET /health``. They describe *what*
#: the feed is doing, never *why* it stopped.
FEED_STATE_OFF = "off"
FEED_STATE_RUNNING = "running"
FEED_STATE_STOPPED = "stopped"


def _normalise_search_term(value: str) -> str:
    """Trim a search term at the HTTP boundary and reject blank input.

    Normalising here (rather than in each backend) keeps the store-backed and
    in-memory search paths behaving identically: whitespace-only input is a
    client error, not a 500 or an unbounded "match everything" listing.
    """
    term = value.strip()
    if not term:
        raise ValueError("query must contain at least one non-whitespace character")
    return term


#: Bounded path/query parameter types shared by the routes below.
WorkOrderIdPath = Annotated[
    str,
    Path(min_length=1, max_length=WORK_ORDER_ID_MAX_LENGTH, pattern=WORK_ORDER_ID_PATTERN),
]
SearchQuery = Annotated[
    str,
    Query(
        min_length=1,
        max_length=MAX_SEARCH_QUERY_LENGTH,
        description="Asset id or name fragment",
    ),
    AfterValidator(_normalise_search_term),
]
SearchLimit = Annotated[int, Query(ge=1, le=MAX_SEARCH_RESULTS)]


# ---------------------------------------------------------------------------
# Health (public)
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
async def health_check(
    request: Request,
    services: ServicesDep,
) -> HealthResponse:
    """Public liveness probe. No authentication, no organization data.

    Reports ``degraded`` when a configured telemetry feed is no longer
    pumping: its task failed, was cancelled, or finished early. Marks stop
    updating in that state, so claiming ``healthy`` would let the dashboard
    show a connected system with frozen readings. An application configured
    without a feed is fully healthy — nothing is missing.
    """
    feed_state = _feed_state(services, getattr(request.app.state, "feed_task", None))
    return HealthResponse(
        status=STATUS_HEALTHY if feed_state != FEED_STATE_STOPPED else STATUS_DEGRADED,
        version=services.version,
        timestamp=utcnow(),
        mode="simulation",
        feed=feed_state,
    )


def _feed_state(services: AppServices, feed_task: asyncio.Task[Any] | None) -> str:
    """Classify the telemetry feed without inspecting failure details."""
    if services.feed is None:
        return FEED_STATE_OFF
    if feed_task is None or feed_task.done():
        return FEED_STATE_STOPPED
    return FEED_STATE_RUNNING


# ---------------------------------------------------------------------------
# Work orders
# ---------------------------------------------------------------------------


@router.post(
    "/work-orders",
    response_model=WorkOrderSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_work_order(
    payload: WorkOrderRequest,
    principal: DispatchPrincipalDep,
    services: ServicesDep,
) -> WorkOrderSubmissionResponse:
    """Submit a work order for the authenticated organization."""
    try:
        work_order = payload.to_work_order(principal.organization_id)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_work_order",
                "reason": _first_validation_message(exc),
            },
        ) from exc

    try:
        result = await services.dispatch.submit_work_order(principal.organization_id, work_order)
    except DuplicateWorkOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "duplicate_work_order_id", "work_order_id": exc.work_order_id},
        ) from exc
    except AssignmentPersistenceError as exc:
        # The engine already executed: never pretend otherwise. The response
        # states what happened and how to reconcile, and carries no store
        # internals (URLs, SQL, credentials) — those stay in the server log.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "assignment_persistence_failed",
                "work_order_id": exc.work_order_id,
                "status": exc.work_order_status,
                "assigned_hours": exc.assigned_hours,
                "assignment_ids": exc.assignment_ids,
                "message": (
                    "The work order executed and the in-memory engine state is "
                    "authoritative, but the resulting assignments could not be "
                    "persisted. Reconcile from the engine assignment log; do not "
                    "resubmit this work order."
                ),
            },
        ) from exc

    if not result.accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "work_order_rejected",
                "work_order_id": result.work_order.work_order_id,
                "status": result.work_order.status.value,
                "reason": result.rejection_reason,
            },
        )

    return WorkOrderSubmissionResponse(
        accepted=result.accepted,
        work_order_id=result.work_order.work_order_id,
        status=result.work_order.status,
        assigned_hours=result.work_order.assigned_hours,
        work_order=result.work_order.model_dump(mode="json"),
        assignments=[assignment.model_dump(mode="json") for assignment in result.assignments],
    )


@router.get("/work-orders", response_model=WorkOrderListResponse)
async def list_work_orders(
    principal: ReadPrincipalDep,
    services: ServicesDep,
) -> WorkOrderListResponse:
    """List the caller's own API-submitted work orders with live engine status."""
    work_orders = services.dispatch.work_orders_for(principal.organization_id)
    return WorkOrderListResponse(
        work_orders=[wo.model_dump(mode="json") for wo in work_orders],
        count=len(work_orders),
    )


@router.get("/work-orders/{work_order_id}", response_model=dict)
async def get_work_order(
    work_order_id: WorkOrderIdPath,
    principal: ReadPrincipalDep,
    services: ServicesDep,
) -> dict[str, Any]:
    """Return one of the caller's work orders. Other organizations' ids look unknown."""
    work_order = services.dispatch.get_work_order(principal.organization_id, work_order_id)
    if work_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    return work_order.model_dump(mode="json")


@router.delete("/work-orders/{work_order_id}", response_model=CancellationResponse)
async def cancel_work_order(
    work_order_id: WorkOrderIdPath,
    principal: DispatchPrincipalDep,
    services: ServicesDep,
) -> CancellationResponse:
    """Cancel a resting work order owned by the caller."""
    try:
        cancelled = await services.dispatch.cancel_work_order(
            principal.organization_id, work_order_id
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found"
        ) from exc

    if cancelled is None:
        known = services.dispatch.get_work_order(principal.organization_id, work_order_id)
        current_status = known.status.value if known is not None else "UNKNOWN"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "work_order_not_resting",
                "work_order_id": work_order_id,
                "status": current_status,
            },
        )

    return CancellationResponse(
        work_order_id=cancelled.work_order_id,
        status=cancelled.status,
        work_order=cancelled.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# Workloads / organization
# ---------------------------------------------------------------------------


@router.get("/workloads", response_model=WorkloadListResponse)
async def get_workloads(
    principal: ReadPrincipalDep,
    services: ServicesDep,
) -> WorkloadListResponse:
    """Return the caller's workloads — never another organization's."""
    workloads = sorted(
        services.dispatch.workloads_for(principal.organization_id), key=lambda w: w.asset_id
    )
    return WorkloadListResponse(
        organization_id=principal.organization_id,
        workloads=[
            {
                **workload.model_dump(mode="json"),
                "currency": services.dispatch.currency_for_asset(workload.asset_id),
            }
            for workload in workloads
        ],
        count=len(workloads),
    )


@router.get("/organization/snapshot", response_model=dict)
async def organization_snapshot(
    principal: ReadPrincipalDep,
    services: ServicesDep,
) -> dict[str, Any]:
    """Organization snapshot built from the caller's engine workloads."""
    analytics = services.dispatch.analytics_for(principal.organization_id)
    return analytics.snapshot().model_dump(mode="json")


@router.get("/organization/risk", response_model=dict)
async def organization_risk(
    principal: ReadPrincipalDep,
    services: ServicesDep,
) -> dict[str, Any]:
    """Operational risk metrics for the caller.

    ``backlog_risk_95``/``backlog_risk_99`` are ``null`` unless an hours
    volatility assumption is configured — the simulator does not invent one.
    """
    return services.dispatch.risk_payload(principal.organization_id)


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------


@router.get("/equipment/search", response_model=EquipmentSearchResponse)
async def search_equipment(
    q: SearchQuery,
    principal: ReadPrincipalDep,
    services: ServicesDep,
    limit: SearchLimit = 20,
) -> EquipmentSearchResponse:
    """Bounded equipment search.

    Backed by parameterised ORM predicates when a store is configured, and by
    an equivalent in-memory scan otherwise. SQL metacharacters are inert in
    both paths.
    """
    if services.store is not None and not services.store.is_closed:
        rows = services.store.search_equipment(q, limit=limit)
        results = [row.as_dict() for row in rows]
    else:
        results = search_equipment_in_memory(services.equipment, q, limit)
    return EquipmentSearchResponse(query=q, results=results, count=len(results))


# ---------------------------------------------------------------------------
# Dispatch policies / metrics
# ---------------------------------------------------------------------------


@router.get("/dispatch-policies", response_model=DispatchPolicyListResponse)
async def list_dispatch_policies(
    principal: ReadPrincipalDep,
) -> DispatchPolicyListResponse:
    """List registered dispatch policy names from the policy metaclass registry."""
    return DispatchPolicyListResponse(policies=sorted(DispatchPolicyMeta.list_policies()))


@router.get("/metrics", response_model=dict)
async def get_metrics(
    principal: ReadPrincipalDep,
) -> dict[str, Any]:
    """Process-level metrics snapshot (counters, gauges, histograms)."""
    return REGISTRY.snapshot()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    principal: ReadPrincipalDep,
    services: ServicesDep,
) -> DashboardResponse:
    """Aggregate payload for the static dashboard.

    Always returns ``as_of`` (aware UTC), ``currency``, ``kpis``,
    ``workloads``, ``cost_history``, ``risk``, and ``dispatch_queues``. Empty
    collections are a valid, honest state. The currency is a display label
    only: no FX conversion is performed on mixed-currency books.
    """
    return DashboardResponse(**services.dispatch.dashboard_payload(principal.organization_id))


def _first_validation_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "invalid work order"
    first = errors[0]
    location = ".".join(str(part) for part in first.get("loc", ())) or "work_order"
    return f"{location}: {first.get('msg', 'invalid value')}"


__all__ = [
    "router",
    "MAX_SEARCH_RESULTS",
    "MAX_SEARCH_QUERY_LENGTH",
    "STATUS_HEALTHY",
    "STATUS_DEGRADED",
    "FEED_STATE_OFF",
    "FEED_STATE_RUNNING",
    "FEED_STATE_STOPPED",
]

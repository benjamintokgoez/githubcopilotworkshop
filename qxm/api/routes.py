"""REST endpoints for the QuantCore educational trading simulator.

Contract summary (prefix ``/api/v1``, header ``X-API-Key``):

============================== ============ =================================
Endpoint                       Permission   Notes
============================== ============ =================================
``GET  /health``               public       liveness, aware-UTC timestamp;
                                            ``degraded`` when a configured
                                            market data feed has stopped
``POST /orders``               ``trade``    JSON body, identity from the key
``GET  /orders``               ``read``     only the caller's own orders
``GET  /orders/{order_id}``    ``read``     404 when not owned by the caller
``DELETE /orders/{order_id}``  ``trade``    404 when not owned, 409 when
                                            the order is no longer resting
``GET  /positions``            ``read``     caller-scoped
``GET  /portfolio/snapshot``   ``read``     caller-scoped
``GET  /portfolio/risk``       ``read``     caller-scoped
``GET  /instruments/search``   ``read``     bounded, parameterised
``GET  /strategies``           ``read``     registered strategy names
``GET  /metrics``              ``read``     process metrics snapshot
``GET  /dashboard``            ``read``     dashboard payload contract
============================== ============ =================================

Error contract for ``POST /orders``:

* ``422`` — the body failed schema validation.  This includes a client-supplied
  ``order_id`` outside the URL-path-segment-safe character set
  (``[A-Za-z0-9._:-]``, at most 64 characters); such a request never reaches
  the matching engine, so no id is reserved.
* ``400`` with ``detail.error == "invalid_order"`` — the body is schema-valid
  but violates a domain invariant (for example a LIMIT order without a price).
* ``400`` with ``detail.error == "order_rejected"`` — the matching engine
  rejected the order (unknown instrument, tick/lot violation, unsupported
  STOP order type or DAY/GTD time-in-force, failed pre-trade risk check).
  ``detail.reason`` carries the engine's own wording.
* ``409`` with ``detail.error == "duplicate_order_id"`` — the id was already
  submitted.  Neither the original nor the duplicate request is mutated.
* ``500`` with ``detail.error == "trade_persistence_failed"`` — the order
  executed but its trades could not be written to the store.  Execution is not
  rolled back (the engine is in-memory and authoritative); the response names
  the affected order and trade ids so an operator can reconcile, and contains
  no store internals.

``GET /instruments/search`` trims ``q`` at the boundary and answers ``422`` for
blank or whitespace-only input, identically with and without a store.

``GET /health`` stays ``200`` in every state: ``status`` is ``healthy`` or
``degraded`` and ``feed`` is ``off``/``running``/``stopped``.  Failure *reasons*
are logged, never returned, because the endpoint is unauthenticated.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from pydantic import AfterValidator, ValidationError

from qxm.api.dependencies import (
    AppServices,
    ReadPrincipalDep,
    ServicesDep,
    TradePrincipalDep,
)
from qxm.api.schemas import (
    ORDER_ID_MAX_LENGTH,
    ORDER_ID_PATTERN,
    CancelResponse,
    DashboardResponse,
    HealthResponse,
    InstrumentSearchResponse,
    OrderListResponse,
    OrderRequest,
    OrderSubmissionResponse,
    PositionListResponse,
    StrategyListResponse,
)
from qxm.api.service import TradePersistenceError, search_instruments_in_memory
from qxm.core.engine import DuplicateOrderError
from qxm.core.models import utcnow
from qxm.strategy.base import StrategyMeta
from qxm.utils.metrics import REGISTRY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["trading"])

#: Upper bound on instrument search results returned in a single response.
MAX_SEARCH_RESULTS = 100
#: Upper bound on the length of an instrument search term.
MAX_SEARCH_QUERY_LENGTH = 64

#: Liveness values reported by ``GET /health``.
STATUS_HEALTHY = "healthy"
STATUS_DEGRADED = "degraded"
#: Market data feed states reported by ``GET /health``.  They describe *what*
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
OrderIdPath = Annotated[
    str,
    Path(min_length=1, max_length=ORDER_ID_MAX_LENGTH, pattern=ORDER_ID_PATTERN),
]
SearchQuery = Annotated[
    str,
    Query(
        min_length=1,
        max_length=MAX_SEARCH_QUERY_LENGTH,
        description="Symbol or name fragment",
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
    """Public liveness probe.  No authentication, no client data.

    Reports ``degraded`` when a configured market data feed is no longer
    pumping: its task failed, was cancelled, or finished early.  Marks stop
    updating in that state, so claiming ``healthy`` would let the dashboard show
    a connected system with frozen prices.  An application configured without a
    feed is fully healthy — nothing is missing.
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
    """Classify the market data feed without inspecting failure details."""
    if services.feed is None:
        return FEED_STATE_OFF
    if feed_task is None or feed_task.done():
        return FEED_STATE_STOPPED
    return FEED_STATE_RUNNING


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


@router.post(
    "/orders",
    response_model=OrderSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_order(
    payload: OrderRequest,
    principal: TradePrincipalDep,
    services: ServicesDep,
) -> OrderSubmissionResponse:
    """Submit an order for the authenticated client."""
    try:
        order = payload.to_order(principal.client_id)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_order",
                "reason": _first_validation_message(exc),
            },
        ) from exc

    try:
        result = await services.trading.submit_order(principal.client_id, order)
    except DuplicateOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "duplicate_order_id", "order_id": exc.order_id},
        ) from exc
    except TradePersistenceError as exc:
        # The engine already executed: never pretend otherwise.  The response
        # states what happened and how to reconcile, and carries no store
        # internals (URLs, SQL, credentials) — those stay in the server log.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "trade_persistence_failed",
                "order_id": exc.order_id,
                "status": exc.order_status,
                "filled_quantity": exc.filled_quantity,
                "trade_ids": exc.trade_ids,
                "message": (
                    "The order executed and the in-memory engine state is "
                    "authoritative, but the resulting trades could not be "
                    "persisted. Reconcile from the engine trade log; do not "
                    "resubmit this order."
                ),
            },
        ) from exc

    if not result.accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "order_rejected",
                "order_id": result.order.order_id,
                "status": result.order.status.value,
                "reason": result.rejection_reason,
            },
        )

    return OrderSubmissionResponse(
        accepted=result.accepted,
        order_id=result.order.order_id,
        status=result.order.status,
        filled_quantity=result.order.filled_quantity,
        order=result.order.model_dump(mode="json"),
        trades=[trade.model_dump(mode="json") for trade in result.trades],
    )


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    principal: ReadPrincipalDep,
    services: ServicesDep,
) -> OrderListResponse:
    """List the caller's own API-submitted orders with live engine status."""
    orders = services.trading.orders_for(principal.client_id)
    return OrderListResponse(
        orders=[order.model_dump(mode="json") for order in orders],
        count=len(orders),
    )


@router.get("/orders/{order_id}", response_model=dict)
async def get_order(
    order_id: OrderIdPath,
    principal: ReadPrincipalDep,
    services: ServicesDep,
) -> dict[str, Any]:
    """Return one of the caller's orders.  Other clients' ids look unknown."""
    order = services.trading.get_order(principal.client_id, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order.model_dump(mode="json")


@router.delete("/orders/{order_id}", response_model=CancelResponse)
async def cancel_order(
    order_id: OrderIdPath,
    principal: TradePrincipalDep,
    services: ServicesDep,
) -> CancelResponse:
    """Cancel a resting order owned by the caller."""
    try:
        cancelled = await services.trading.cancel_order(principal.client_id, order_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        ) from exc

    if cancelled is None:
        known = services.trading.get_order(principal.client_id, order_id)
        current_status = known.status.value if known is not None else "UNKNOWN"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "order_not_resting",
                "order_id": order_id,
                "status": current_status,
            },
        )

    return CancelResponse(
        order_id=cancelled.order_id,
        status=cancelled.status,
        order=cancelled.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# Positions / portfolio
# ---------------------------------------------------------------------------


@router.get("/positions", response_model=PositionListResponse)
async def get_positions(
    principal: ReadPrincipalDep,
    services: ServicesDep,
) -> PositionListResponse:
    """Return the caller's positions — never another client's."""
    positions = sorted(services.trading.positions_for(principal.client_id), key=lambda p: p.symbol)
    return PositionListResponse(
        client_id=principal.client_id,
        positions=[
            {
                **position.model_dump(mode="json"),
                "currency": services.trading.currency_for_symbol(position.symbol),
            }
            for position in positions
        ],
        count=len(positions),
    )


@router.get("/portfolio/snapshot", response_model=dict)
async def portfolio_snapshot(
    principal: ReadPrincipalDep,
    services: ServicesDep,
) -> dict[str, Any]:
    """Portfolio snapshot built from the caller's engine positions."""
    portfolio = services.trading.portfolio_for(principal.client_id)
    return portfolio.snapshot().model_dump(mode="json")


@router.get("/portfolio/risk", response_model=dict)
async def portfolio_risk(
    principal: ReadPrincipalDep,
    services: ServicesDep,
) -> dict[str, Any]:
    """Risk metrics for the caller.

    ``var_95``/``var_99`` are ``null`` unless a daily volatility assumption is
    configured — the simulator does not invent one.
    """
    return services.trading.risk_payload(principal.client_id)


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------


@router.get("/instruments/search", response_model=InstrumentSearchResponse)
async def search_instruments(
    q: SearchQuery,
    principal: ReadPrincipalDep,
    services: ServicesDep,
    limit: SearchLimit = 20,
) -> InstrumentSearchResponse:
    """Bounded instrument search.

    Backed by parameterised ORM predicates when a store is configured, and by an
    equivalent in-memory scan otherwise.  SQL metacharacters are inert in both
    paths.
    """
    if services.store is not None and not services.store.is_closed:
        rows = services.store.search_instruments(q, limit=limit)
        results = [row.as_dict() for row in rows]
    else:
        results = search_instruments_in_memory(services.instruments, q, limit)
    return InstrumentSearchResponse(query=q, results=results, count=len(results))


# ---------------------------------------------------------------------------
# Strategies / metrics
# ---------------------------------------------------------------------------


@router.get("/strategies", response_model=StrategyListResponse)
async def list_strategies(
    principal: ReadPrincipalDep,
) -> StrategyListResponse:
    """List registered strategy names from the strategy metaclass registry."""
    return StrategyListResponse(strategies=sorted(StrategyMeta.list_strategies()))


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

    Always returns ``as_of`` (aware UTC), ``currency``, ``kpis``, ``positions``,
    ``pnl_history``, ``risk``, and ``order_books``.  Empty collections are a
    valid, honest state.  The currency is a display label only: no FX
    conversion is performed on mixed-currency books.
    """
    return DashboardResponse(**services.trading.dashboard_payload(principal.client_id))


def _first_validation_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "invalid order"
    first = errors[0]
    location = ".".join(str(part) for part in first.get("loc", ())) or "order"
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

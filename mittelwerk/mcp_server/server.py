"""MCP v2 server for MittelWerk's local field-service operations simulation.

Default read-only; mutation tools require explicit opt-in with a bound
organization identity. No I/O on import. It is a fictional, synthetic
simulation — never real equipment, never a live network.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, NoReturn, Protocol, cast

from mcp import MCPError
from mcp.server import MCPServer
from mcp.types import INVALID_PARAMS, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from mittelwerk import __version__
from mittelwerk.analytics.backlog_risk import BacklogRiskEngine
from mittelwerk.core.engine import DispatchEngine, DispatchResult, DuplicateWorkOrderError
from mittelwerk.core.events import EventBus
from mittelwerk.core.models import (
    DispatchSide,
    DispatchWindow,
    Equipment,
    EquipmentCategory,
    ServiceAssignment,
    WorkOrder,
    WorkOrderMode,
    WorkOrderStatus,
    utcnow,
)
from mittelwerk.core.queue import RateLevel

DEFAULT_EQUIPMENT_PATH = Path(__file__).resolve().parents[2] / "equipment.json"
MAX_EQUIPMENT_RESULTS = 50
MAX_QUEUE_DEPTH = 20
MAX_BACKLOG_OBSERVATIONS = 256
MAX_REQUESTED_HOURS = Decimal("10000")
MAX_SERIALIZED_ASSIGNMENTS = 100
MAX_ORGANIZATION_ID_LENGTH = 64
MAX_REJECTION_REASON_LENGTH = 256
REJECTION_DETAIL_UNAVAILABLE = (
    "Local simulation engine rejected the work order; detailed reason unavailable"
)
_ORGANIZATION_ID_PATTERN = re.compile(
    rf"[A-Za-z0-9][A-Za-z0-9._:@/-]{{0,{MAX_ORGANIZATION_ID_LENGTH - 1}}}"
)

AssetIdInput = Annotated[
    str,
    Field(
        min_length=1,
        max_length=32,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/\-]*$",
        description="Local simulated asset identifier.",
    ),
]
WorkOrderIdInput = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:\-]*$",
        description="Client-supplied or server-generated simulated work order identifier.",
    ),
]
RequestedHoursInput = Annotated[
    Decimal,
    Field(
        gt=0,
        le=MAX_REQUESTED_HOURS,
        max_digits=24,
        decimal_places=8,
        allow_inf_nan=False,
        description=(
            "Positive simulated requested hours up to 10,000; strings preserve decimal precision."
        ),
    ),
]
HourlyRateInput = Annotated[
    Decimal,
    Field(
        gt=0,
        le=Decimal("1000000000000"),
        max_digits=24,
        decimal_places=8,
        allow_inf_nan=False,
        description="Positive simulated hourly rate; strings preserve decimal precision.",
    ),
]
BacklogHoursInput = Annotated[
    Decimal,
    Field(
        ge=0,
        le=Decimal("1000000000000000"),
        max_digits=24,
        decimal_places=8,
        allow_inf_nan=False,
    ),
]
HoursVolatilityInput = Annotated[
    Decimal,
    Field(ge=0, le=Decimal("10"), max_digits=12, decimal_places=10, allow_inf_nan=False),
]
ConfidenceInput = Annotated[
    Decimal,
    Field(gt=0, lt=1, max_digits=12, decimal_places=10, allow_inf_nan=False),
]
BacklogObservation = Annotated[
    Decimal,
    Field(
        ge=Decimal("-1000000000000000"),
        le=Decimal("1000000000000000"),
        max_digits=24,
        decimal_places=8,
        allow_inf_nan=False,
    ),
]
BacklogHistoryInput = Annotated[
    list[BacklogObservation],
    Field(min_length=1, max_length=MAX_BACKLOG_OBSERVATIONS),
]


class SupportedWorkOrderMode(StrEnum):
    """Work order modes backed by the current simulation engine."""

    RATE_CAPPED = "RATE_CAPPED"
    ANY_RATE = "ANY_RATE"


class SupportedDispatchWindow(StrEnum):
    """Dispatch-window values backed by the current simulation engine."""

    OPEN = "OPEN"
    IMMEDIATE = "IMMEDIATE"
    COMPLETE = "COMPLETE"


class BacklogRiskCalculator(Protocol):
    """Structural contract for an injected operational-risk calculator."""

    def compute(
        self,
        open_backlog_hours: float,
        hours_volatility: float | None = None,
        backlog_history: Sequence[float] | None = None,
        confidence: float | None = None,
        horizon_days: int | None = None,
    ) -> dict[str, float]:
        """Compute requested backlog-risk magnitudes."""


class _ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    environment: Literal["SIMULATION"] = "SIMULATION"


class EquipmentSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_id: str
    name: str
    equipment_type: EquipmentCategory
    hourly_service_rate: Decimal
    rate_increment: Decimal
    hour_lot_size: Decimal
    currency: str
    site_code: str


class EquipmentListResult(_ToolResult):
    total: int
    offset: int
    limit: int
    returned: int
    equipment: list[EquipmentSummary]


class QueueLevelResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    rate: Decimal
    hours: Decimal
    work_orders: int


class DispatchQueueSnapshotResult(_ToolResult):
    asset_id: str
    as_of: datetime
    requested_depth: int
    best_request_rate: Decimal | None
    best_offer_rate: Decimal | None
    rate_spread: Decimal | None
    representative_rate: Decimal | None
    requests: list[QueueLevelResult]
    offers: list[QueueLevelResult]


class OperationalRiskResult(_ToolResult):
    as_of: datetime
    confidence: Decimal
    horizon_days: int
    backlog_observations: int
    parametric_backlog_risk: Decimal | None
    historical_backlog_risk: Decimal | None
    conditional_backlog_risk: Decimal | None


class AssignmentResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    assignment_id: str
    requester_work_order_id: str
    provider_work_order_id: str
    hourly_rate: Decimal
    hours: Decimal
    initiating_side: DispatchSide
    timestamp: datetime


class WorkOrderResult(_ToolResult):
    work_order_id: str
    asset_id: str
    side: DispatchSide
    mode: WorkOrderMode
    dispatch_window: DispatchWindow
    status: WorkOrderStatus
    accepted: bool
    requested_hours: Decimal
    assigned_hours: Decimal
    remaining_hours: Decimal
    max_hourly_rate: Decimal | None
    average_service_rate: Decimal | None
    created_at: datetime
    updated_at: datetime | None
    rejection_reason: Annotated[str | None, Field(max_length=MAX_REJECTION_REASON_LENGTH)]
    assignment_count: Annotated[int, Field(ge=0)]
    returned_assignment_count: Annotated[int, Field(ge=0, le=MAX_SERIALIZED_ASSIGNMENTS)]
    assignments_truncated: bool
    assignments: Annotated[list[AssignmentResult], Field(max_length=MAX_SERIALIZED_ASSIGNMENTS)]


class WorkOrderCancellationResult(_ToolResult):
    work_order_id: str
    asset_id: str
    status: WorkOrderStatus
    updated_at: datetime


def _invalid_params(message: str) -> NoReturn:
    raise MCPError(code=INVALID_PARAMS, message=message)


def _copy_equipment(equipment: Mapping[str, Equipment]) -> dict[str, Equipment]:
    if not equipment:
        raise ValueError("At least one simulated equipment record is required")

    copied: dict[str, Equipment] = {}
    for key, item in equipment.items():
        canonical_asset_id = key.strip().upper()
        if canonical_asset_id != item.asset_id:
            raise ValueError(
                f"Equipment mapping key {key!r} does not match asset_id {item.asset_id!r}"
            )
        if canonical_asset_id in copied:
            raise ValueError(f"Duplicate simulated equipment asset_id: {canonical_asset_id}")
        copied[canonical_asset_id] = item
    return copied


def _equipment_summary(equipment: Equipment) -> EquipmentSummary:
    return EquipmentSummary(
        asset_id=equipment.asset_id,
        name=equipment.name,
        equipment_type=equipment.equipment_type,
        hourly_service_rate=equipment.hourly_service_rate,
        rate_increment=equipment.rate_increment,
        hour_lot_size=equipment.hour_lot_size,
        currency=equipment.currency,
        site_code=equipment.site_code,
    )


def _queue_level_result(level: RateLevel) -> QueueLevelResult:
    return QueueLevelResult(
        rate=level.rate,
        hours=level.total_hours,
        work_orders=level.work_order_count,
    )


def _assignment_result(assignment: ServiceAssignment) -> AssignmentResult:
    return AssignmentResult(
        assignment_id=assignment.assignment_id,
        requester_work_order_id=assignment.requester_work_order_id,
        provider_work_order_id=assignment.provider_work_order_id,
        hourly_rate=assignment.hourly_rate,
        hours=assignment.hours,
        initiating_side=assignment.initiating_side,
        timestamp=assignment.timestamp,
    )


def _work_order_result(submission: DispatchResult) -> WorkOrderResult:
    work_order = submission.work_order
    assignment_count = len(submission.assignments)
    retained_assignments = submission.assignments[:MAX_SERIALIZED_ASSIGNMENTS]
    return WorkOrderResult(
        work_order_id=work_order.work_order_id,
        asset_id=work_order.asset_id,
        side=work_order.side,
        mode=work_order.mode,
        dispatch_window=work_order.dispatch_window,
        status=work_order.status,
        accepted=submission.accepted,
        requested_hours=work_order.requested_hours,
        assigned_hours=work_order.assigned_hours,
        remaining_hours=work_order.remaining_hours,
        max_hourly_rate=work_order.max_hourly_rate,
        average_service_rate=work_order.average_service_rate,
        created_at=work_order.created_at,
        updated_at=work_order.updated_at,
        rejection_reason=_bounded_rejection_reason(submission),
        assignment_count=assignment_count,
        returned_assignment_count=len(retained_assignments),
        assignments_truncated=assignment_count > len(retained_assignments),
        assignments=[_assignment_result(assignment) for assignment in retained_assignments],
    )


def _bounded_rejection_reason(submission: DispatchResult) -> str | None:
    if submission.work_order.status is not WorkOrderStatus.REJECTED:
        return None
    reason = submission.rejection_reason or REJECTION_DETAIL_UNAVAILABLE
    if len(reason) <= MAX_REJECTION_REASON_LENGTH:
        return reason
    return f"{reason[: MAX_REJECTION_REASON_LENGTH - 3]}..."


def _loss_decimal(value: float, metric: str) -> Decimal:
    if not math.isfinite(value) or value < 0:
        raise RuntimeError(f"risk calculator returned an invalid {metric} magnitude")
    return Decimal(str(value))


def _load_equipment(path: Path) -> dict[str, Equipment]:
    if not path.is_file():
        raise FileNotFoundError(f"Equipment file not found: {path}")

    data = cast(object, json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal))
    if not isinstance(data, list):
        raise ValueError(f"Equipment file must contain a JSON array: {path}")

    equipment: dict[str, Equipment] = {}
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Equipment entry {index} must be a JSON object")
        record = Equipment.model_validate(item)
        if record.asset_id in equipment:
            raise ValueError(f"Duplicate equipment asset_id: {record.asset_id}")
        equipment[record.asset_id] = record
    if not equipment:
        raise ValueError(f"Equipment file contains no equipment: {path}")
    return equipment


def create_mcp_server(
    engine: DispatchEngine,
    equipment: Mapping[str, Equipment],
    *,
    risk_calculator: BacklogRiskCalculator | None = None,
    allow_writes: bool = False,
    organization_id: str | None = None,
) -> MCPServer[None]:
    """Create an isolated MCP server around injected local simulation state."""

    equipment_map = _copy_equipment(equipment)
    if engine.equipment != equipment_map:
        raise ValueError("DispatchEngine equipment must match the MCP equipment mapping")

    bound_organization_id: str | None = None
    if allow_writes:
        if organization_id is None or _ORGANIZATION_ID_PATTERN.fullmatch(organization_id) is None:
            raise ValueError(
                f"Write-enabled organization_id must be 1-{MAX_ORGANIZATION_ID_LENGTH} ASCII "
                "characters using letters, digits, '.', '_', ':', '@', '/', or '-'"
            )
        bound_organization_id = organization_id

    calculator = risk_calculator if risk_calculator is not None else BacklogRiskEngine()
    mcp: MCPServer[None] = MCPServer(
        name="mittelwerk-simulation",
        title="MittelWerk Simulation",
        description="Bounded tools for the local MittelWerk field-service operations simulation.",
        instructions=(
            "All equipment, dispatch queues, service assignments, and operational risk "
            "results are local simulated data. This server cannot reach a live network "
            "or real equipment."
        ),
        version=__version__,
        log_level="WARNING",
    )
    owned_open_work_order_ids: set[str] = set()

    def require_equipment(asset_id: str) -> Equipment:
        canonical = asset_id.upper()
        item = equipment_map.get(canonical)
        if item is None:
            _invalid_params(f"Unknown simulated asset: {canonical}")
        return item

    @mcp.tool(
        description=(
            "List bounded local simulated equipment reference data. "
            "No live operational or network data is used."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def list_equipment(
        limit: Annotated[int, Field(ge=1, le=MAX_EQUIPMENT_RESULTS)] = 20,
        offset: Annotated[int, Field(ge=0, le=10_000)] = 0,
    ) -> EquipmentListResult:
        ordered = [equipment_map[asset_id] for asset_id in sorted(equipment_map)]
        selected = ordered[offset : offset + limit]
        return EquipmentListResult(
            total=len(ordered),
            offset=offset,
            limit=limit,
            returned=len(selected),
            equipment=[_equipment_summary(item) for item in selected],
        )

    @mcp.tool(
        description=(
            "Return a bounded snapshot of a local simulated dispatch queue. "
            "An inactive known asset has empty request and offer arrays."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def get_dispatch_queue(
        asset_id: AssetIdInput,
        depth: Annotated[int, Field(ge=1, le=MAX_QUEUE_DEPTH)] = 5,
    ) -> DispatchQueueSnapshotResult:
        item = require_equipment(asset_id)
        queue = engine.get_queue(item.asset_id)
        if queue is None:
            return DispatchQueueSnapshotResult(
                asset_id=item.asset_id,
                as_of=utcnow(),
                requested_depth=depth,
                best_request_rate=None,
                best_offer_rate=None,
                rate_spread=None,
                representative_rate=None,
                requests=[],
                offers=[],
            )

        requests = [_queue_level_result(level) for level in queue.request_levels(depth)]
        offers = [_queue_level_result(level) for level in queue.offer_levels(depth)]
        return DispatchQueueSnapshotResult(
            asset_id=item.asset_id,
            as_of=utcnow(),
            requested_depth=depth,
            best_request_rate=queue.best_request_rate,
            best_offer_rate=queue.best_offer_rate,
            rate_spread=queue.rate_spread,
            representative_rate=queue.representative_rate,
            requests=requests,
            offers=offers,
        )

    @mcp.tool(
        description=(
            "Calculate bounded backlog-at-risk and conditional-overrun magnitudes from "
            "caller-provided simulated inputs. Provide hours_volatility, backlog_history, or both."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    def calculate_service_risk(
        open_backlog_hours: BacklogHoursInput,
        hours_volatility: HoursVolatilityInput | None = None,
        backlog_history: BacklogHistoryInput | None = None,
        confidence: ConfidenceInput = Decimal("0.95"),
        horizon_days: Annotated[int, Field(ge=1, le=365)] = 1,
    ) -> OperationalRiskResult:
        if hours_volatility is None and backlog_history is None:
            _invalid_params("Provide hours_volatility, backlog_history, or both")

        float_history = (
            [float(observation) for observation in backlog_history]
            if backlog_history is not None
            else None
        )
        calculated = calculator.compute(
            open_backlog_hours=float(open_backlog_hours),
            hours_volatility=(float(hours_volatility) if hours_volatility is not None else None),
            backlog_history=float_history,
            confidence=float(confidence),
            horizon_days=horizon_days,
        )
        parametric = (
            _loss_decimal(calculated["parametric_backlog_risk"], "parametric backlog risk")
            if hours_volatility is not None
            else None
        )
        historical = (
            _loss_decimal(calculated["historical_backlog_risk"], "historical backlog risk")
            if backlog_history is not None
            else None
        )
        conditional = (
            _loss_decimal(calculated["conditional_backlog_risk"], "conditional backlog risk")
            if backlog_history is not None
            else None
        )
        return OperationalRiskResult(
            as_of=utcnow(),
            confidence=confidence,
            horizon_days=horizon_days,
            backlog_observations=len(backlog_history) if backlog_history is not None else 0,
            parametric_backlog_risk=parametric,
            historical_backlog_risk=historical,
            conditional_backlog_risk=conditional,
        )

    if allow_writes:
        if bound_organization_id is None:
            raise RuntimeError("Write-enabled server is missing its bound organization identity")

        @mcp.tool(
            description=(
                "Submit a work order only to this server's local simulated dispatch engine. "
                "This never routes to a live system."
            ),
            annotations=ToolAnnotations(
                readOnlyHint=False,
                destructiveHint=True,
                idempotentHint=False,
                openWorldHint=False,
            ),
        )
        async def submit_work_order(
            asset_id: AssetIdInput,
            side: DispatchSide,
            requested_hours: RequestedHoursInput,
            mode: SupportedWorkOrderMode = SupportedWorkOrderMode.RATE_CAPPED,
            max_hourly_rate: HourlyRateInput | None = None,
            dispatch_window: SupportedDispatchWindow = SupportedDispatchWindow.OPEN,
            work_order_id: WorkOrderIdInput | None = None,
        ) -> WorkOrderResult:
            item = require_equipment(asset_id)
            if mode is SupportedWorkOrderMode.RATE_CAPPED and max_hourly_rate is None:
                _invalid_params("RATE_CAPPED work orders require a max_hourly_rate")
            if mode is SupportedWorkOrderMode.ANY_RATE and max_hourly_rate is not None:
                _invalid_params("ANY_RATE work orders must not include a max_hourly_rate")

            work_order_data: dict[str, object] = {
                "organization_id": bound_organization_id,
                "asset_id": item.asset_id,
                "side": side,
                "mode": WorkOrderMode(mode.value),
                "requested_hours": requested_hours,
                "max_hourly_rate": max_hourly_rate,
                "dispatch_window": DispatchWindow(dispatch_window.value),
            }
            if work_order_id is not None:
                work_order_data["work_order_id"] = work_order_id
            work_order = WorkOrder.model_validate(work_order_data)
            try:
                submission = await engine.submit_work_order(work_order)
            except DuplicateWorkOrderError as exc:
                _invalid_params(str(exc))

            if work_order.is_active:
                owned_open_work_order_ids.add(work_order.work_order_id)
            return _work_order_result(submission)

        @mcp.tool(
            description=(
                "Cancel an open work order previously submitted by this MCP server identity "
                "in the local simulation. This never contacts a live system."
            ),
            annotations=ToolAnnotations(
                readOnlyHint=False,
                destructiveHint=True,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )
        async def cancel_work_order(work_order_id: WorkOrderIdInput) -> WorkOrderCancellationResult:
            if work_order_id not in owned_open_work_order_ids:
                _invalid_params("Open simulated work order not found for this MCP organization")

            work_order = await engine.cancel_work_order(work_order_id)
            owned_open_work_order_ids.discard(work_order_id)
            if work_order is None:
                _invalid_params("Open simulated work order not found for this MCP organization")
            if work_order.updated_at is None:
                raise RuntimeError("Cancelled work order is missing its update timestamp")
            return WorkOrderCancellationResult(
                work_order_id=work_order.work_order_id,
                asset_id=work_order.asset_id,
                status=work_order.status,
                updated_at=work_order.updated_at,
            )

    return mcp


def create_default_mcp_server(*, equipment_path: Path | None = None) -> MCPServer[None]:
    """Build a fresh read-only server from local repository configuration."""

    equipment = _load_equipment(equipment_path or DEFAULT_EQUIPMENT_PATH)
    engine = DispatchEngine(event_bus=EventBus(), equipment=equipment)
    return create_mcp_server(engine=engine, equipment=equipment)


def run_server() -> None:
    """Run a fresh read-only MittelWerk MCP server over stdio."""

    create_default_mcp_server().run()


if __name__ == "__main__":
    run_server()


__all__ = [
    "BacklogRiskCalculator",
    "create_default_mcp_server",
    "create_mcp_server",
    "run_server",
]

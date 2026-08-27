"""Pydantic v2 request/response models for the MittelWerk REST surface.

Requests carry JSON bodies (not loose query strings) and use the canonical core
enumerations, so ``DispatchSide``/``WorkOrderMode``/``DispatchWindow`` are
validated by the domain model rather than re-implemented here. Hours and rates
are ``Decimal`` end-to-end — fractional lots such as ``0.25`` hours survive
intact.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mittelwerk.core.models import (
    DispatchSide,
    DispatchWindow,
    WorkOrder,
    WorkOrderMode,
    WorkOrderStatus,
)

#: Character set accepted for a client-supplied ``work_order_id``.
#:
#: Every id must survive a round trip through
#: ``/api/v1/work-orders/{work_order_id}`` unescaped, so the set is restricted
#: to URL-path-segment-safe characters. An id must additionally start and end
#: alphanumeric: that keeps single character ids usable while excluding the
#: dot-segments ``.`` and ``..``, which URL normalisation rewrites and which
#: would therefore be just as unaddressable as a segment containing ``/``.
#: UUID4 values (hex digits plus ``-``) are covered.
WORK_ORDER_ID_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9._:-]*[A-Za-z0-9])?$"
#: Maximum length of a client-supplied ``work_order_id``.
WORK_ORDER_ID_MAX_LENGTH = 64


def _coerce_decimal(value: object) -> object:
    """Coerce numeric input to ``Decimal`` via text, avoiding float artefacts."""
    if value is None or isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid numeric value")
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"{value!r} is not a valid decimal") from exc
    return value


class WorkOrderRequest(BaseModel):
    """Body of ``POST /api/v1/work-orders``.

    ``organization_id`` is intentionally absent: the identity is derived from
    the validated API key, so a caller can never dispatch as somebody else.
    ``work_order_id`` may be supplied by the client for idempotency testing; a
    repeated id is a conflict (HTTP 409).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset_id: str = Field(..., min_length=1, max_length=32)
    side: DispatchSide
    requested_hours: Decimal = Field(..., gt=0)
    mode: WorkOrderMode = WorkOrderMode.RATE_CAPPED
    max_hourly_rate: Decimal | None = Field(default=None, gt=0)
    escalation_rate: Decimal | None = Field(default=None, gt=0)
    priority: int = Field(default=3, ge=1, le=5)
    dispatch_window: DispatchWindow = DispatchWindow.OPEN
    work_order_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=WORK_ORDER_ID_MAX_LENGTH,
        pattern=WORK_ORDER_ID_PATTERN,
        description=(
            "Optional client-supplied id. Must be URL-path-segment safe: "
            "letters and digits, optionally separated by . _ : - , and it must "
            "start and end with a letter or digit."
        ),
    )

    @field_validator("requested_hours", "max_hourly_rate", "escalation_rate", mode="before")
    @classmethod
    def _decimalise(cls, value: object) -> object:
        return _coerce_decimal(value)

    def to_work_order(self, organization_id: str) -> WorkOrder:
        """Build the canonical core work order for this request.

        Domain invariants (e.g. a RATE_CAPPED order needs a rate) are enforced
        by :class:`~mittelwerk.core.models.WorkOrder`; the resulting
        ``ValidationError`` is translated to a 4xx by the route.
        """
        payload: dict[str, Any] = {
            "organization_id": organization_id,
            "asset_id": self.asset_id,
            "side": self.side,
            "mode": self.mode,
            "requested_hours": self.requested_hours,
            "max_hourly_rate": self.max_hourly_rate,
            "escalation_rate": self.escalation_rate,
            "priority": self.priority,
            "dispatch_window": self.dispatch_window,
        }
        if self.work_order_id is not None:
            payload["work_order_id"] = self.work_order_id
        return WorkOrder(**payload)


class WorkOrderSubmissionResponse(BaseModel):
    """Result of an accepted submission, including any immediate assignments."""

    accepted: bool
    work_order_id: str
    status: WorkOrderStatus
    assigned_hours: Decimal
    work_order: dict[str, Any]
    assignments: list[dict[str, Any]]


class WorkOrderListResponse(BaseModel):
    work_orders: list[dict[str, Any]]
    count: int


class CancellationResponse(BaseModel):
    work_order_id: str
    status: WorkOrderStatus
    work_order: dict[str, Any]


class WorkloadListResponse(BaseModel):
    organization_id: str
    workloads: list[dict[str, Any]]
    count: int


class EquipmentSearchResponse(BaseModel):
    query: str
    results: list[dict[str, str]]
    count: int


class DispatchPolicyListResponse(BaseModel):
    policies: list[str]


class HealthResponse(BaseModel):
    """Public liveness payload.

    ``status`` is ``healthy`` only while every configured component is doing
    its job; a configured telemetry feed that has stopped makes it
    ``degraded``. ``feed`` names that component's state
    (``off``/``running``/``stopped``) without revealing why it stopped — the
    reason belongs in the server log, not in an unauthenticated response.
    """

    status: str
    version: str
    timestamp: datetime
    mode: str
    feed: str


class DashboardResponse(BaseModel):
    """Exact payload contract consumed by ``dashboard/index.html``."""

    model_config = ConfigDict(extra="forbid")

    as_of: datetime
    currency: str
    kpis: dict[str, Any]
    workloads: list[dict[str, Any]]
    cost_history: list[dict[str, Any]]
    risk: dict[str, Any]
    dispatch_queues: dict[str, dict[str, list[dict[str, Any]]]]


__all__ = [
    "WORK_ORDER_ID_PATTERN",
    "WORK_ORDER_ID_MAX_LENGTH",
    "WorkOrderRequest",
    "WorkOrderSubmissionResponse",
    "WorkOrderListResponse",
    "CancellationResponse",
    "WorkloadListResponse",
    "EquipmentSearchResponse",
    "DispatchPolicyListResponse",
    "HealthResponse",
    "DashboardResponse",
]

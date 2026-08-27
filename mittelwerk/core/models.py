"""MittelWerk core domain models — canonical representations for equipment,
work orders, service assignments, and organization workloads used throughout
the dispatch engine, operational analytics, and API surface.

All monetary and hours values are represented as :class:`~decimal.Decimal` to
avoid IEEE-754 floating-point artefacts. Models use Pydantic v2 conventions
(``field_validator`` / ``model_validator`` / ``model_config``) and serialise
cleanly to JSON: ``Decimal`` renders as a string and ``datetime`` as
ISO-8601.

MittelWerk is a fictional, synthetic field-service operations platform used
for a training workshop. It is not connected to real equipment or
organizations.
"""

from __future__ import annotations

import enum
import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def utcnow() -> datetime:
    """Timezone-aware UTC ``now`` used for every timestamp in the core."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Reject naive datetimes and normalise any aware offset to UTC.

    The core's invariant is aware-UTC everywhere, so every externally supplied
    timestamp is funnelled through this helper.
    """
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError("datetime must be timezone-aware; naive datetimes are rejected")
    return dt.astimezone(UTC)


# Reusable aware-UTC datetime field type: parses input, rejects naive values,
# and normalises aware offsets to UTC.
AwareUTC = Annotated[datetime, AfterValidator(ensure_utc)]


_ASSET_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9._/\-]*$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def _to_decimal(value: object) -> Decimal:
    """Coerce arbitrary numeric input to :class:`Decimal` without float noise."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):  # guard: bool is an int subclass
        raise TypeError("boolean is not a valid numeric value")
    return Decimal(str(value))


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DispatchSide(enum.StrEnum):
    """Which side of the dispatch queue a work order occupies.

    ``REQUEST`` is an organization asking for service hours (it names the
    maximum hourly rate it is willing to pay). ``OFFER`` is a service
    provider publishing available capacity (it names the hourly rate it
    wants for that capacity).
    """

    REQUEST = "REQUEST"
    OFFER = "OFFER"

    @property
    def opposite(self) -> DispatchSide:
        return DispatchSide.OFFER if self is DispatchSide.REQUEST else DispatchSide.REQUEST

    @property
    def sign(self) -> int:
        """+1 for REQUEST, -1 for OFFER — signed workload delta direction."""
        return 1 if self is DispatchSide.REQUEST else -1


class WorkOrderMode(enum.StrEnum):
    """How the dispatch engine should interpret a work order's rate constraints."""

    RATE_CAPPED = "RATE_CAPPED"  # requires a max/asking hourly rate
    ANY_RATE = "ANY_RATE"  # dispatch immediately at the best available rate
    ESCALATION = "ESCALATION"  # trigger-based; requires an escalation engine
    ESCALATION_CAPPED = "ESCALATION_CAPPED"  # trigger + rate cap


class WorkOrderStatus(enum.StrEnum):
    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_ASSIGNED = "PARTIALLY_ASSIGNED"
    ASSIGNED = "ASSIGNED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

    @property
    def is_terminal(self) -> bool:
        return self in (
            WorkOrderStatus.ASSIGNED,
            WorkOrderStatus.CANCELLED,
            WorkOrderStatus.REJECTED,
            WorkOrderStatus.EXPIRED,
        )


class EquipmentCategory(enum.StrEnum):
    CNC_MACHINE = "CNC_MACHINE"
    HYDRAULIC_PRESS = "HYDRAULIC_PRESS"
    CONVEYOR_SYSTEM = "CONVEYOR_SYSTEM"
    ROBOTIC_ARM = "ROBOTIC_ARM"
    COMPRESSOR = "COMPRESSOR"
    GENERATOR = "GENERATOR"
    HVAC_UNIT = "HVAC_UNIT"
    FORKLIFT = "FORKLIFT"


class DispatchWindow(enum.StrEnum):
    OPEN = "OPEN"  # Good-till-cancelled
    SHIFT = "SHIFT"  # Good for the current shift only
    IMMEDIATE = "IMMEDIATE"  # Immediate-or-stand-down
    COMPLETE = "COMPLETE"  # Complete-or-stand-down (fill-or-kill)
    SCHEDULED_END = "SCHEDULED_END"  # Good-till-date


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------


class Equipment(BaseModel):
    """Static reference data for a piece of serviceable industrial equipment.

    ``rate_increment`` (minimum hourly-rate increment) and ``hour_lot_size``
    (minimum requested-hours increment) are decimals and may be fractional —
    quarter-hour lots such as ``0.25`` are common for field-service billing.
    """

    model_config = ConfigDict(validate_assignment=True)

    asset_id: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1)
    equipment_type: EquipmentCategory
    service_interval_days: int = Field(..., gt=0)
    hourly_service_rate: Decimal = Field(..., gt=0)
    rate_increment: Decimal = Field(default=Decimal("0.50"), gt=0)
    hour_lot_size: Decimal = Field(default=Decimal("0.25"), gt=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    site_code: str = Field(default="MW-HQ", min_length=1)

    @field_validator("asset_id", mode="before")
    @classmethod
    def _normalise_asset_id(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip().upper()
        return v

    @field_validator("asset_id")
    @classmethod
    def _check_asset_id(cls, v: str) -> str:
        if not _ASSET_ID_RE.match(v):
            raise ValueError(
                f"Invalid asset_id {v!r}: must be alphanumeric with . _ / - separators"
            )
        return v

    @field_validator("currency", mode="before")
    @classmethod
    def _upper_currency(cls, v: object) -> object:
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, v: str) -> str:
        if not _CURRENCY_RE.fullmatch(v):
            raise ValueError("currency must be a three-letter ASCII code")
        return v

    @field_validator("hourly_service_rate", "rate_increment", "hour_lot_size", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: object) -> object:
        return _to_decimal(v) if v is not None else v

    @property
    def is_escalation_capable(self) -> bool:
        """Whether this asset category typically supports trigger escalation."""
        return self.equipment_type in (
            EquipmentCategory.COMPRESSOR,
            EquipmentCategory.GENERATOR,
            EquipmentCategory.HVAC_UNIT,
        )

    def round_rate(self, rate: Decimal) -> Decimal:
        """Round ``rate`` to the nearest valid rate increment."""
        rate = _to_decimal(rate)
        steps = (rate / self.rate_increment).quantize(Decimal("1"))
        return steps * self.rate_increment

    def is_valid_rate(self, rate: Decimal) -> bool:
        rate = _to_decimal(rate)
        if rate <= 0:
            return False
        return (rate % self.rate_increment) == 0

    def is_valid_hours(self, hours: Decimal) -> bool:
        hours = _to_decimal(hours)
        if hours <= 0:
            return False
        return (hours % self.hour_lot_size) == 0


# ---------------------------------------------------------------------------
# WorkOrder
# ---------------------------------------------------------------------------


class WorkOrder(BaseModel):
    """A client work order. ``RATE_CAPPED`` / ``ESCALATION_CAPPED`` require a
    positive ``max_hourly_rate``; ``ESCALATION`` / ``ESCALATION_CAPPED``
    require a positive ``escalation_rate``. ``IMMEDIATE`` / ``COMPLETE``
    semantics are expressed through ``dispatch_window`` rather than ``mode``.
    """

    model_config = ConfigDict(validate_assignment=True)

    work_order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str = Field(..., min_length=1)
    asset_id: str = Field(..., min_length=1, max_length=32)
    side: DispatchSide
    mode: WorkOrderMode
    requested_hours: Decimal = Field(..., gt=0)
    max_hourly_rate: Decimal | None = None
    escalation_rate: Decimal | None = None
    priority: int = Field(default=3, ge=1, le=5)
    dispatch_window: DispatchWindow = DispatchWindow.OPEN
    status: WorkOrderStatus = WorkOrderStatus.NEW
    assigned_hours: Decimal = Field(default=Decimal("0"), ge=0)
    average_service_rate: Decimal | None = None
    created_at: AwareUTC = Field(default_factory=utcnow)
    updated_at: AwareUTC | None = None
    signature: str | None = None

    @field_validator("asset_id", mode="before")
    @classmethod
    def _normalise_asset_id(cls, v: object) -> object:
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator(
        "requested_hours",
        "max_hourly_rate",
        "escalation_rate",
        "assigned_hours",
        "average_service_rate",
        mode="before",
    )
    @classmethod
    def _coerce_decimal(cls, v: object) -> object:
        return _to_decimal(v) if v is not None else v

    @model_validator(mode="after")
    def _validate_work_order(self) -> WorkOrder:
        if self.mode in (WorkOrderMode.RATE_CAPPED, WorkOrderMode.ESCALATION_CAPPED):
            if self.max_hourly_rate is None or self.max_hourly_rate <= 0:
                raise ValueError(
                    f"{self.mode.value} work orders require a positive max_hourly_rate"
                )
        if self.mode in (WorkOrderMode.ESCALATION, WorkOrderMode.ESCALATION_CAPPED):
            if self.escalation_rate is None or self.escalation_rate <= 0:
                raise ValueError(
                    f"{self.mode.value} work orders require a positive escalation_rate"
                )
        if self.assigned_hours > self.requested_hours:
            raise ValueError("assigned_hours cannot exceed requested_hours")
        return self

    @property
    def remaining_hours(self) -> Decimal:
        return self.requested_hours - self.assigned_hours

    @property
    def is_fully_assigned(self) -> bool:
        return self.assigned_hours >= self.requested_hours

    @property
    def is_request(self) -> bool:
        return self.side is DispatchSide.REQUEST

    @property
    def is_active(self) -> bool:
        return not self.status.is_terminal


# ---------------------------------------------------------------------------
# ServiceAssignment
# ---------------------------------------------------------------------------


class ServiceAssignment(BaseModel):
    assignment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_id: str
    requester_work_order_id: str
    provider_work_order_id: str
    hourly_rate: Decimal = Field(..., gt=0)
    hours: Decimal = Field(..., gt=0)
    requester_organization_id: str
    provider_organization_id: str
    initiating_side: DispatchSide
    timestamp: AwareUTC = Field(default_factory=utcnow)

    @field_validator("hourly_rate", "hours", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: object) -> object:
        return _to_decimal(v) if v is not None else v

    @property
    def total_cost(self) -> Decimal:
        return self.hourly_rate * self.hours


# ---------------------------------------------------------------------------
# Workload
# ---------------------------------------------------------------------------


class Workload(BaseModel):
    """Signed net-hours workload with realised/unrealised cost accounting.

    ``net_hours`` is signed: positive means the organization is a net
    requester of service hours for this asset; negative means it is a net
    provider of committed capacity. ``average_service_rate`` is the
    volume-weighted rate of the currently open workload and is reset when the
    workload flips through zero.
    """

    model_config = ConfigDict(validate_assignment=True)

    organization_id: str
    asset_id: str
    net_hours: Decimal = Decimal("0")
    average_service_rate: Decimal = Decimal("0")
    realized_cost: Decimal = Decimal("0")
    unrealized_cost: Decimal = Decimal("0")
    last_rate: Decimal | None = None
    last_updated: AwareUTC = Field(default_factory=utcnow)

    @property
    def is_idle(self) -> bool:
        return self.net_hours == 0

    @property
    def is_net_requester(self) -> bool:
        return self.net_hours > 0

    @property
    def is_net_provider(self) -> bool:
        return self.net_hours < 0

    @property
    def total_cost(self) -> Decimal:
        return self.realized_cost + self.unrealized_cost

    def exposure_value(self, mark_rate: Decimal | None = None) -> Decimal:
        rate = mark_rate if mark_rate is not None else self.last_rate
        if rate is None:
            rate = self.average_service_rate
        return self.net_hours * _to_decimal(rate)

    def apply_assignment(self, side: DispatchSide, hours: Decimal, rate: Decimal) -> Decimal:
        """Apply an assignment and return the realised cost it generated.

        Handles opening, increasing, reducing, closing and flipping a
        workload with correct volume-weighted average rate and realised cost
        when reducing or crossing through zero.
        """
        hours = _to_decimal(hours)
        rate = _to_decimal(rate)
        if hours <= 0:
            raise ValueError("hours must be positive")

        signed_delta = hours * side.sign
        realised = Decimal("0")

        if self.net_hours == 0:
            self.net_hours = signed_delta
            self.average_service_rate = rate
        elif (self.net_hours > 0) == (signed_delta > 0):
            new_hours = self.net_hours + signed_delta
            total_cost = self.average_service_rate * abs(self.net_hours) + rate * hours
            self.net_hours = new_hours
            self.average_service_rate = total_cost / abs(new_hours)
        else:
            closing_hours = min(hours, abs(self.net_hours))
            position_sign = 1 if self.net_hours > 0 else -1
            realised = (rate - self.average_service_rate) * closing_hours * position_sign
            self.realized_cost += realised
            new_hours = self.net_hours + signed_delta
            if new_hours == 0:
                self.net_hours = Decimal("0")
                self.average_service_rate = Decimal("0")
            elif (new_hours > 0) == (self.net_hours > 0):
                self.net_hours = new_hours
            else:
                self.net_hours = new_hours
                self.average_service_rate = rate

        self.last_rate = rate
        self.last_updated = utcnow()
        self._recompute_unrealized_cost(rate)
        return realised

    def reprice(self, mark_rate: Decimal) -> Decimal:
        """Update unrealised cost against ``mark_rate`` and return it."""
        mark_rate = _to_decimal(mark_rate)
        self.last_rate = mark_rate
        self._recompute_unrealized_cost(mark_rate)
        self.last_updated = utcnow()
        return self.unrealized_cost

    def _recompute_unrealized_cost(self, mark_rate: Decimal) -> None:
        if self.net_hours == 0:
            self.unrealized_cost = Decimal("0")
        else:
            self.unrealized_cost = (mark_rate - self.average_service_rate) * self.net_hours


# ---------------------------------------------------------------------------
# Organization snapshot — aggregated view across workloads
# ---------------------------------------------------------------------------


class OrganizationSnapshot(BaseModel):
    organization_id: str
    workloads: list[Workload] = Field(default_factory=list)
    total_exposure_value: Decimal = Decimal("0")
    total_realized_cost: Decimal = Decimal("0")
    total_unrealized_cost: Decimal = Decimal("0")
    budget_balance: Decimal = Decimal("0")
    timestamp: AwareUTC = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _aggregate(self) -> OrganizationSnapshot:
        workloads: Sequence[Workload] = self.workloads
        self.total_realized_cost = sum((w.realized_cost for w in workloads), Decimal("0"))
        self.total_unrealized_cost = sum((w.unrealized_cost for w in workloads), Decimal("0"))
        self.total_exposure_value = self.budget_balance + sum(
            (w.exposure_value() for w in workloads), Decimal("0")
        )
        return self


# ---------------------------------------------------------------------------
# Telemetry reading — uses __slots__ for performance
# ---------------------------------------------------------------------------


class TelemetryReading:
    """Lightweight telemetry reading. Uses ``__slots__`` to minimise per-object
    memory overhead — critical when processing millions of readings per
    session."""

    __slots__ = (
        "asset_id",
        "min_reading",
        "max_reading",
        "last_reading",
        "sample_count",
        "timestamp",
    )

    def __init__(
        self,
        asset_id: str,
        min_reading: Decimal,
        max_reading: Decimal,
        last_reading: Decimal,
        sample_count: int,
        timestamp: datetime | None = None,
    ) -> None:
        normalized_asset_id = asset_id.strip().upper() if isinstance(asset_id, str) else ""
        if not _ASSET_ID_RE.fullmatch(normalized_asset_id):
            raise ValueError("asset_id must be a valid non-empty asset identifier")

        decimal_min = _to_decimal(min_reading)
        decimal_max = _to_decimal(max_reading)
        decimal_last = _to_decimal(last_reading)
        if any(
            not value.is_finite() or value <= 0
            for value in (decimal_min, decimal_max, decimal_last)
        ):
            raise ValueError(
                "min_reading, max_reading, and last_reading must be finite and positive"
            )
        if decimal_min > decimal_max:
            raise ValueError("min_reading must not exceed max_reading")
        if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 0:
            raise ValueError("sample_count must be a non-negative integer")

        self.asset_id = normalized_asset_id
        self.min_reading = decimal_min
        self.max_reading = decimal_max
        self.last_reading = decimal_last
        self.sample_count = sample_count
        self.timestamp = ensure_utc(timestamp) if timestamp is not None else utcnow()

    def midpoint_reading(self) -> Decimal:
        return (self.min_reading + self.max_reading) / 2

    def reading_spread(self) -> Decimal:
        return self.max_reading - self.min_reading

    def __repr__(self) -> str:
        return (
            f"TelemetryReading({self.asset_id} min={self.min_reading} max={self.max_reading} "
            f"last={self.last_reading} n={self.sample_count} @{self.timestamp})"
        )


# ---------------------------------------------------------------------------
# Operational risk metrics container
# ---------------------------------------------------------------------------


class OperationalRiskMetrics(BaseModel):
    """Aggregated operational risk metrics for an organization or asset."""

    asset_id: str | None = None
    backlog_hours_at_risk_95: Decimal = Decimal("0")
    backlog_hours_at_risk_99: Decimal = Decimal("0")
    utilization_rate: Decimal = Decimal("0")
    sla_compliance_rate: Decimal = Decimal("0")
    average_lead_time_hours: Decimal = Decimal("0")
    service_level_ratio: Decimal | None = None
    max_backlog_overrun: Decimal | None = None
    computed_at: AwareUTC = Field(default_factory=utcnow)


__all__ = [
    "utcnow",
    "ensure_utc",
    "AwareUTC",
    "DispatchSide",
    "WorkOrderMode",
    "WorkOrderStatus",
    "EquipmentCategory",
    "DispatchWindow",
    "Equipment",
    "WorkOrder",
    "ServiceAssignment",
    "Workload",
    "OrganizationSnapshot",
    "TelemetryReading",
    "OperationalRiskMetrics",
]

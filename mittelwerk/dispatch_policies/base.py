"""Dispatch policy framework with metaclass registration and lifecycle helpers."""

from __future__ import annotations

import abc
import inspect
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar

from mittelwerk.core.models import (
    DispatchSide,
    DispatchWindow,
    Equipment,
    TelemetryReading,
    WorkOrder,
    WorkOrderMode,
)

logger = logging.getLogger(__name__)


def _require_int_parameter(
    parameters: dict[str, Any],
    name: str,
    *,
    minimum: int,
) -> int:
    """Return a strict integer policy parameter at or above ``minimum``."""
    value = parameters[name]
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


class RecommendationUrgency(Enum):
    URGENT = 2
    ELEVATED = 1
    ROUTINE = 0
    DEFER = -1
    SUPPRESS = -2


@dataclass
class Recommendation:
    """A dispatch recommendation produced by a policy."""

    asset: Equipment
    urgency: RecommendationUrgency
    target_rate: float | None = None
    escalation_rate: float | None = None
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("recommendation timestamp must include an explicit timezone offset")
        self.timestamp = self.timestamp.astimezone(UTC)
        self.metadata = dict(self.metadata)
        try:
            json.dumps(self.metadata, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must contain only JSON-compatible values") from exc

    @property
    def is_actionable(self) -> bool:
        return self.urgency != RecommendationUrgency.ROUTINE and self.confidence >= 0.5


class DispatchPolicyMeta(abc.ABCMeta):
    """Metaclass that automatically registers concrete dispatch-policy subclasses."""

    _registry: dict[str, type[BasePolicy]] = {}

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> DispatchPolicyMeta:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        if bases and not inspect.isabstract(cls):
            if not issubclass(cls, BasePolicy):
                raise TypeError(f"{name} must subclass BasePolicy to use DispatchPolicyMeta")
            key = namespace.get("policy_name", name)
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"{name}.policy_name must be a non-empty string")
            existing = mcs._registry.get(key)
            if existing is not None and existing is not cls:
                raise ValueError(
                    f"Policy name {key!r} is already registered by {existing.__name__}"
                )
            mcs._registry[key] = cls
            logger.debug("Registered dispatch policy: %s", key)
        return cls

    @classmethod
    def get(mcs, name: str) -> type[BasePolicy]:
        """Retrieve a policy class by name."""
        try:
            return mcs._registry[name]
        except KeyError as exc:
            raise KeyError(f"Unknown policy {name!r}. Available: {mcs.list_policies()}") from exc

    @classmethod
    def list_policies(mcs) -> list[str]:
        """Return registered concrete policy names in stable order."""
        return sorted(mcs._registry)


class BasePolicy(metaclass=DispatchPolicyMeta):
    """Abstract base for all dispatch policies."""

    policy_name: ClassVar[str] = "BasePolicy"
    version: ClassVar[str] = "0.0.0"

    def __init__(
        self,
        equipment: list[Equipment],
        parameters: dict[str, Any] | None = None,
    ) -> None:
        asset_ids = [asset.asset_id for asset in equipment]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("equipment must have unique asset_ids")
        self.equipment = {asset.asset_id: asset for asset in equipment}
        self.parameters = dict(parameters or {})
        self._reading_buffer: dict[str, list[TelemetryReading]] = {
            asset.asset_id: [] for asset in equipment
        }
        self._recommendations: list[Recommendation] = []
        self._is_running: bool = False
        self._workload_exposure: dict[str, float] = {}

    def on_start(self) -> None:
        """Called when the policy begins running."""
        logger.info("%s v%s started", self.policy_name, self.version)
        self._is_running = True

    def on_stop(self) -> None:
        """Called when the policy is halted."""
        logger.info("%s stopped", self.policy_name)
        self._is_running = False

    @abc.abstractmethod
    def on_reading(self, reading: TelemetryReading) -> None:
        """Process a single telemetry reading."""
        ...

    @abc.abstractmethod
    def generate_recommendations(self) -> list[Recommendation]:
        """Produce dispatch recommendations based on buffered data."""
        ...

    def on_assignment(
        self,
        work_order: WorkOrder,
        assignment_rate: float,
        assignment_hours: float,
    ) -> None:
        """React to an assignment (default: update exposure tracking)."""
        sign = 1 if work_order.side == DispatchSide.REQUEST else -1
        current = self._workload_exposure.get(work_order.asset_id, 0.0)
        self._workload_exposure[work_order.asset_id] = (
            current + sign * assignment_hours * assignment_rate
        )

    def _buffer_reading(self, reading: TelemetryReading, max_buffer: int = 500) -> None:
        """Add a reading to the per-asset buffer, evicting oldest if full."""
        buf = self._reading_buffer.get(reading.asset_id)
        if buf is None:
            raise ValueError(
                f"Reading asset_id {reading.asset_id!r} is not configured for {self.policy_name}"
            )
        buf.append(reading)
        if len(buf) > max_buffer:
            del buf[: len(buf) - max_buffer]

    def create_work_order(
        self,
        asset_id: str,
        side: DispatchSide,
        requested_hours: float,
        max_hourly_rate: float | None = None,
        mode: WorkOrderMode | None = None,
        dispatch_window: DispatchWindow = DispatchWindow.OPEN,
        organization_id: str = "policy",
    ) -> WorkOrder:
        """Create a work order, inferring ANY_RATE without a rate and RATE_CAPPED with one."""
        normalized_asset_id = asset_id.strip().upper()
        if normalized_asset_id not in self.equipment:
            raise ValueError(
                f"Work order asset_id {normalized_asset_id!r} is not configured "
                f"for {self.policy_name}"
            )
        resolved_mode = (
            mode
            if mode is not None
            else WorkOrderMode.RATE_CAPPED
            if max_hourly_rate is not None
            else WorkOrderMode.ANY_RATE
        )
        return WorkOrder(
            organization_id=organization_id,
            asset_id=normalized_asset_id,
            side=side,
            mode=resolved_mode,
            requested_hours=requested_hours,
            max_hourly_rate=max_hourly_rate,
            dispatch_window=dispatch_window,
        )

    @property
    def is_running(self) -> bool:
        """Whether the policy lifecycle has been started."""
        return self._is_running

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name={self.policy_name!r} "
            f"v={self.version} equipment={list(self.equipment)}>"
        )


__all__ = [
    "BasePolicy",
    "DispatchPolicyMeta",
    "Recommendation",
    "RecommendationUrgency",
    "_require_int_parameter",
]

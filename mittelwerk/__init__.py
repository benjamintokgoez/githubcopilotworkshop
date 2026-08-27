"""MittelWerk public package interface.

The top-level package exposes the core dispatch primitives without importing
the optional API or MCP integrations. Telemetry is loaded on first access so
``import mittelwerk`` remains suitable for lightweight clients.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mittelwerk.core import (
    DispatchEngine,
    DispatchEventType,
    DispatchQueue,
    DispatchResult,
    DispatchSide,
    DispatchWindow,
    DomainEvent,
    Equipment,
    EquipmentCategory,
    EventBus,
    EventLog,
    OperationalRiskMetrics,
    OrganizationSnapshot,
    PreDispatchCheck,
    RateLevel,
    ServiceAssignment,
    TelemetryReading,
    Workload,
    WorkloadManager,
    WorkOrder,
    WorkOrderMode,
    WorkOrderStatus,
    utcnow,
)

if TYPE_CHECKING:
    from mittelwerk.telemetry.feed import TelemetryFeed

__version__ = "1.0.0"

__all__ = [
    "DispatchEngine",
    "DispatchEventType",
    "DispatchQueue",
    "DispatchResult",
    "DispatchSide",
    "DispatchWindow",
    "DomainEvent",
    "Equipment",
    "EquipmentCategory",
    "EventBus",
    "EventLog",
    "OperationalRiskMetrics",
    "OrganizationSnapshot",
    "PreDispatchCheck",
    "RateLevel",
    "ServiceAssignment",
    "TelemetryFeed",
    "TelemetryReading",
    "Workload",
    "WorkloadManager",
    "WorkOrder",
    "WorkOrderMode",
    "WorkOrderStatus",
    "utcnow",
]


def __getattr__(name: str) -> Any:
    """Load optional public objects only when callers request them."""
    if name == "TelemetryFeed":
        from mittelwerk.telemetry.feed import TelemetryFeed

        globals()[name] = TelemetryFeed
        return TelemetryFeed
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return the stable public package namespace."""
    return sorted(set(globals()) | set(__all__))

"""Organization-level operational analytics built around immutable workload
algebra.

Workloads and budget retain ``Decimal`` precision at the domain boundary.
Backlog risk, capacity, and performance statistics intentionally convert to
``float`` only when invoking their numerical algorithms.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

import numpy as np

from mittelwerk.analytics.backlog_risk import BacklogRiskEngine
from mittelwerk.analytics.capacity import CapacityModel, aggregate_capacity
from mittelwerk.core.models import OperationalRiskMetrics, OrganizationSnapshot, Workload

WorkloadProvider = Callable[[], Sequence[Workload]]
WORKING_DAYS_PER_YEAR = 260


def _decimal(value: Any, name: str) -> Decimal:
    """Convert a domain-boundary value to a finite Decimal."""
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def _finite_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _clone_workload(workload: Workload) -> Workload:
    """Construct a fresh core workload without relying on a Pydantic version."""
    if not isinstance(workload, Workload):
        raise ValueError("workloads must contain Workload instances")
    return Workload(
        organization_id=workload.organization_id,
        asset_id=workload.asset_id,
        net_hours=workload.net_hours,
        average_service_rate=workload.average_service_rate,
        realized_cost=workload.realized_cost,
        unrealized_cost=workload.unrealized_cost,
        last_rate=workload.last_rate,
        last_updated=workload.last_updated,
    )


def _clone_model(model: CapacityModel) -> CapacityModel:
    return CapacityModel(
        model.backlog_hours,
        model.crew_size,
        model.hourly_service_rate,
        model.hours_per_crew_per_day,
    )


def _exposure_value(workloads: Iterable[Workload]) -> Decimal:
    """Sum core workload exposure values without treating signed hours as budget."""
    return sum((workload.exposure_value() for workload in workloads), Decimal("0"))


class OperationsAnalytics:
    """Compute organization operational metrics and safely compose independent units.

    A ``workload_provider`` can expose engine-owned workloads without creating
    a dependency on the engine implementation. It is consulted before each
    workload-derived result, making the provider authoritative. Use
    :meth:`replace_workloads` for explicit one-off synchronization.
    """

    def __init__(
        self,
        workloads: Iterable[Workload] | None = None,
        budget: Decimal = Decimal("0"),
        organization_id: str = "SYSTEM",
        workload_provider: WorkloadProvider | None = None,
        equipment: Mapping[str, object] | None = None,
    ) -> None:
        if not isinstance(organization_id, str) or not organization_id:
            raise ValueError("organization_id must be a non-empty string")
        if workload_provider is not None and not callable(workload_provider):
            raise ValueError("workload_provider must be callable")
        self._workloads: dict[str, Workload] = {}
        self._budget = _decimal(budget, "budget")
        self._organization_id = organization_id
        self._workload_provider = workload_provider
        self._backlog_engine = BacklogRiskEngine()
        self._backlog_history: dict[str, list[float]] = {}
        self._capacity_models: dict[str, tuple[CapacityModel, float]] = {}
        # Kept only as a constructor compatibility surface for existing hosts.
        self._equipment = dict(equipment) if equipment is not None else {}
        if workloads is not None:
            self.replace_workloads(workloads)

    def _aggregate_workload(self, workload: Workload) -> None:
        candidate = _clone_workload(workload)
        existing = self._workloads.get(candidate.asset_id)
        if existing is None:
            self._workloads[candidate.asset_id] = candidate
            return

        combined_hours = existing.net_hours + candidate.net_hours
        same_side = (
            existing.net_hours == 0
            or candidate.net_hours == 0
            or (existing.net_hours > 0) == (candidate.net_hours > 0)
        )
        if combined_hours == 0:
            average_service_rate = Decimal("0")
            last_rate = None
            last_updated = max(existing.last_updated, candidate.last_updated)
        elif same_side:
            total_hours = abs(existing.net_hours) + abs(candidate.net_hours)
            average_service_rate = (
                abs(existing.net_hours) * existing.average_service_rate
                + abs(candidate.net_hours) * candidate.average_service_rate
            ) / total_hours
            latest_workload = (
                existing if existing.last_updated >= candidate.last_updated else candidate
            )
            last_rate = latest_workload.last_rate
            last_updated = latest_workload.last_updated
        else:
            surviving_workload = (
                existing if abs(existing.net_hours) > abs(candidate.net_hours) else candidate
            )
            average_service_rate = surviving_workload.average_service_rate
            last_rate = surviving_workload.last_rate
            last_updated = surviving_workload.last_updated
        self._workloads[candidate.asset_id] = Workload(
            organization_id=existing.organization_id,
            asset_id=existing.asset_id,
            net_hours=combined_hours,
            average_service_rate=average_service_rate,
            realized_cost=existing.realized_cost + candidate.realized_cost,
            unrealized_cost=existing.unrealized_cost + candidate.unrealized_cost,
            last_rate=last_rate,
            last_updated=last_updated,
        )

    def _sync_from_provider(self) -> None:
        if self._workload_provider is None:
            return
        provided = self._workload_provider()
        if provided is None:
            raise ValueError("workload_provider must return a workload sequence")
        self._workloads = {}
        for workload in provided:
            self._aggregate_workload(workload)

    def _current_workloads(self) -> list[Workload]:
        self._sync_from_provider()
        return [_clone_workload(workload) for workload in self._workloads.values()]

    def replace_workloads(self, workloads: Iterable[Workload]) -> None:
        """Replace local workloads with a cloned, asset-aggregated snapshot."""
        try:
            supplied = list(workloads)
        except TypeError as exc:
            raise ValueError("workloads must be iterable") from exc
        self._workloads = {}
        for workload in supplied:
            self._aggregate_workload(workload)

    def add_workload(self, workload: Workload) -> None:
        """Add a workload without retaining the caller's mutable model."""
        self._sync_from_provider()
        self._aggregate_workload(workload)

    def get_workload(self, asset_id: str) -> Workload | None:
        """Return a defensive copy of an asset workload, if present."""
        self._sync_from_provider()
        workload = self._workloads.get(asset_id)
        return _clone_workload(workload) if workload is not None else None

    @property
    def workloads(self) -> list[Workload]:
        """Return defensive copies of the current, provider-synchronized book."""
        return self._current_workloads()

    @property
    def assets(self) -> list[str]:
        self._sync_from_provider()
        return list(self._workloads)

    def register_capacity(self, asset_id: str, model: CapacityModel, weight: float) -> None:
        """Register a capacity model and its aggregation weight (e.g. crew count)."""
        if not isinstance(asset_id, str) or not asset_id:
            raise ValueError("asset_id must be a non-empty string")
        if not isinstance(model, CapacityModel):
            raise ValueError("model must be a CapacityModel")
        self._capacity_models[asset_id] = (_clone_model(model), _finite_float(weight, "weight"))

    def record_daily_backlog(self, asset_id: str, backlog_delta_hours: float) -> None:
        """Record a finite daily backlog delta for an asset or the organization."""
        if not isinstance(asset_id, str) or not asset_id:
            raise ValueError("asset_id must be a non-empty string")
        self._backlog_history.setdefault(asset_id, []).append(
            _finite_float(backlog_delta_hours, "backlog_delta_hours")
        )

    def record_organization_backlog(self, backlog_delta_hours: float) -> None:
        """Record a finite organization-wide daily backlog delta."""
        self.record_daily_backlog("__organization__", backlog_delta_hours)

    @property
    def total_exposure_value(self) -> Decimal:
        return _exposure_value(self._current_workloads()) + self._budget

    @property
    def total_cost(self) -> Decimal:
        return sum(
            (workload.total_cost for workload in self._current_workloads()),
            Decimal("0"),
        )

    @property
    def gross_committed_hours(self) -> Decimal:
        """Return absolute workload exposure used by parametric backlog risk.

        Demand variability applies to committed hours, not budget. Absolute
        values ensure provider-only and net-provider books receive the same
        risk treatment as requester-heavy books with the same hours exposure.
        """
        return sum(
            (abs(workload.exposure_value()) for workload in self._current_workloads()),
            Decimal("0"),
        )

    def compute_backlog_risk(
        self, hours_volatility: float | None = None, confidence: float = 0.95
    ) -> dict[str, float]:
        """Compute backlog-at-risk using gross committed hours exposure."""
        return self._backlog_engine.compute(
            open_backlog_hours=float(self.gross_committed_hours),
            hours_volatility=hours_volatility,
            backlog_history=self._backlog_history.get("__organization__"),
            confidence=confidence,
        )

    def compute_utilization(self) -> dict[str, float]:
        """Aggregate capacity metrics from the registered capacity models."""
        if not self._capacity_models:
            return {
                "completion_days": 0.0,
                "cost_estimate": 0.0,
                "crew_sensitivity": 0.0,
                "rate_sensitivity": 0.0,
                "backlog_sensitivity": 0.0,
            }
        models = [model for model, _ in self._capacity_models.values()]
        weights = [weight for _, weight in self._capacity_models.values()]
        return aggregate_capacity(models, weights)

    def operational_metrics(
        self,
        hours_volatility: float | None = None,
        confidence_95: float = 0.95,
        confidence_99: float = 0.99,
    ) -> OperationalRiskMetrics:
        """Return the core operational risk model, converting numerical
        results to Decimal."""
        risk_95 = self.compute_backlog_risk(hours_volatility, confidence_95)
        risk_99 = self.compute_backlog_risk(hours_volatility, confidence_99)
        utilization = self.compute_utilization()
        completion_days = utilization["completion_days"]
        return OperationalRiskMetrics(
            backlog_hours_at_risk_95=Decimal(str(risk_95.get("parametric_backlog_risk", 0.0))),
            backlog_hours_at_risk_99=Decimal(str(risk_99.get("parametric_backlog_risk", 0.0))),
            utilization_rate=Decimal(str(min(1.0, max(0.0, 1.0 / completion_days))))
            if completion_days > 0
            else Decimal("0"),
            sla_compliance_rate=Decimal("1") if completion_days <= 1.0 else Decimal("0"),
            average_lead_time_hours=Decimal(str(completion_days * 24.0)),
            service_level_ratio=self._decimal_or_none(self.service_level_ratio()),
            max_backlog_overrun=self._decimal_or_none(self.max_backlog_overrun()),
        )

    @staticmethod
    def _decimal_or_none(value: float | None) -> Decimal | None:
        return None if value is None else Decimal(str(value))

    def snapshot(self) -> OrganizationSnapshot:
        """Return a fresh core snapshot; timestamp policy is inherited from core."""
        return OrganizationSnapshot(
            organization_id=self._organization_id,
            workloads=self._current_workloads(),
            budget_balance=self._budget,
        )

    def service_level_ratio(self, target_rate: float = 0.0) -> float | None:
        """Return a variability-adjusted annual service-level consistency ratio."""
        history = self._backlog_history.get("__organization__")
        if history is None or len(history) < 2:
            return None
        rate = _finite_float(target_rate, "target_rate")
        excess = np.asarray(history, dtype=float) - rate / WORKING_DAYS_PER_YEAR
        std = float(np.std(excess, ddof=1))
        if std == 0.0:
            return None
        return float(np.mean(excess) / std * math.sqrt(WORKING_DAYS_PER_YEAR))

    def max_backlog_overrun(self) -> float | None:
        """Return the largest cumulative backlog overrun observed to date."""
        history = self._backlog_history.get("__organization__")
        if not history:
            return None
        cumulative = np.concatenate((np.array([0.0]), np.cumsum(np.asarray(history, dtype=float))))
        return float(np.max(cumulative - np.minimum.accumulate(cumulative)))

    def _copy_state_to(self, target: OperationsAnalytics, factor: float = 1.0) -> None:
        target._backlog_history = {
            asset: [value * factor for value in history]
            for asset, history in self._backlog_history.items()
        }
        target._capacity_models = {
            asset: (_clone_model(model), weight * factor)
            for asset, (model, weight) in self._capacity_models.items()
        }

    def __add__(self, other: OperationsAnalytics) -> OperationsAnalytics:
        """Combine two organization units without mutating either book or
        losing value.

        Opposite-side holdings are netted to the surviving side's cost basis.
        The signed hours-value removed by netting is reconciled into budget so
        ``combined.total_exposure_value`` and total cost remain additive.
        """
        if not isinstance(other, OperationsAnalytics):
            return NotImplemented
        left_workloads = self._current_workloads()
        right_workloads = other._current_workloads()
        merged = OperationsAnalytics(
            budget=self._budget + other._budget,
            organization_id=self._organization_id,
            equipment=self._equipment,
        )
        merged.replace_workloads([*left_workloads, *right_workloads])
        source_value = _exposure_value(left_workloads) + _exposure_value(right_workloads)
        merged._budget += source_value - _exposure_value(merged._current_workloads())
        self._copy_state_to(merged)
        for asset, history in other._backlog_history.items():
            if asset not in merged._backlog_history:
                merged._backlog_history[asset] = list(history)
            elif len(merged._backlog_history[asset]) != len(history):
                raise ValueError(f"cannot combine unaligned backlog history for {asset}")
            else:
                merged._backlog_history[asset] = [
                    merged._backlog_history[asset][index] + history[index]
                    for index in range(len(history))
                ]
        for asset, (model, weight) in other._capacity_models.items():
            existing = merged._capacity_models.get(asset)
            if existing is None:
                merged._capacity_models[asset] = (_clone_model(model), weight)
            elif existing[0]._param_hash() != model._param_hash():
                raise ValueError(f"cannot combine different capacity models for {asset}")
            else:
                merged._capacity_models[asset] = (existing[0], existing[1] + weight)
        return merged

    def __mul__(self, factor: float) -> OperationsAnalytics:
        """Scale an organization unit into a new independent unit."""
        multiplier = _finite_float(factor, "factor")
        scaled = OperationsAnalytics(
            budget=self._budget * Decimal(str(multiplier)),
            organization_id=self._organization_id,
            equipment=self._equipment,
        )
        scaled_workloads = []
        for workload in self._current_workloads():
            scaled_workloads.append(
                Workload(
                    organization_id=workload.organization_id,
                    asset_id=workload.asset_id,
                    net_hours=workload.net_hours * Decimal(str(multiplier)),
                    average_service_rate=workload.average_service_rate,
                    realized_cost=workload.realized_cost * Decimal(str(multiplier)),
                    unrealized_cost=workload.unrealized_cost * Decimal(str(multiplier)),
                    last_rate=workload.last_rate,
                    last_updated=workload.last_updated,
                )
            )
        scaled.replace_workloads(scaled_workloads)
        self._copy_state_to(scaled, multiplier)
        return scaled

    def __rmul__(self, factor: float) -> OperationsAnalytics:
        return self * factor

    def __sub__(self, other: OperationsAnalytics) -> OperationsAnalytics:
        if not isinstance(other, OperationsAnalytics):
            return NotImplemented
        return self + (other * -1.0)

    def __repr__(self) -> str:
        return (
            f"OperationsAnalytics(organization={self._organization_id}, "
            f"workloads={len(self.workloads)}, value={self.total_exposure_value}, "
            f"cost={self.total_cost})"
        )


__all__ = ["OperationsAnalytics"]

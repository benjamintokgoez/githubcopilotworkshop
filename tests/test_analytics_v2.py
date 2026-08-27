"""Regression coverage for the validated operational analytics contract."""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

from mittelwerk.analytics.backlog_risk import (
    BacklogRiskEngine,
    capacity_stress_test,
    conditional_backlog_risk,
    historical_backlog_risk,
    parametric_backlog_risk,
    parametric_backlog_risk_network,
)
from mittelwerk.analytics.capacity import CapacityModel, aggregate_capacity
from mittelwerk.analytics.operations import OperationsAnalytics
from mittelwerk.core.models import Workload


def workload(
    asset_id: str,
    net_hours: str,
    rate: str,
    realized: str = "0",
    unrealized: str = "0",
) -> Workload:
    return Workload(
        organization_id="org",
        asset_id=asset_id,
        net_hours=Decimal(net_hours),
        average_service_rate=Decimal(rate),
        realized_cost=Decimal(realized),
        unrealized_cost=Decimal(unrealized),
    )


class TestBacklogRiskConvention:
    def test_parametric_backlog_risk_is_non_negative_and_monotonic(self) -> None:
        risk_95 = parametric_backlog_risk(1_000_000, 0.02, confidence=0.95)
        risk_99 = parametric_backlog_risk(1_000_000, 0.02, confidence=0.99)
        assert risk_95 > 0
        assert risk_99 > risk_95

    @pytest.mark.parametrize(
        ("value", "volatility", "confidence", "horizon"),
        [
            (-1, 0.02, 0.95, 1),
            (100, -0.02, 0.95, 1),
            (100, float("nan"), 0.95, 1),
            (100, 0.02, 1.0, 1),
            (100, 0.02, 0.95, 0),
        ],
    )
    def test_parametric_backlog_risk_rejects_bad_inputs(
        self, value: float, volatility: float, confidence: float, horizon: int
    ) -> None:
        with pytest.raises(ValueError):
            parametric_backlog_risk(value, volatility, confidence, horizon)

    def test_parametric_backlog_risk_allows_zero_exposure(self) -> None:
        assert parametric_backlog_risk(0, 0.02, confidence=0.95) == 0.0

    def test_historical_only_engine_does_not_require_backlog_value(self) -> None:
        result = BacklogRiskEngine().compute(
            open_backlog_hours=0,
            backlog_history=[1.0, -2.0, -4.0],
            confidence=0.95,
        )
        assert "parametric_backlog_risk" not in result
        assert result["historical_backlog_risk"] >= 0
        assert result["conditional_backlog_risk"] >= result["historical_backlog_risk"]

    def test_historical_backlog_risk_and_expected_overrun_are_non_negative(self) -> None:
        history = [4.0, 2.0, -1.0, -3.0, -7.0, -10.0]
        risk = historical_backlog_risk(history, confidence=0.8)
        expected_overrun = conditional_backlog_risk(history, confidence=0.8)
        assert risk >= 0
        assert expected_overrun >= risk

    def test_historical_backlog_risk_rejects_empty_or_non_finite_history(self) -> None:
        with pytest.raises(ValueError):
            historical_backlog_risk([])
        with pytest.raises(ValueError):
            conditional_backlog_risk([1.0, float("inf")])

    def test_covariance_validation_and_named_stress_result(self) -> None:
        with pytest.raises(ValueError):
            parametric_backlog_risk_network(
                100, np.array([1.0, 0.0]), np.array([[1.0, 2.0], [2.0, 1.0]])
            )
        result = capacity_stress_test(100.0, [("demand-surge", -0.1)])[0]
        assert result.name == "demand-surge"
        assert result.change == pytest.approx(-10.0)
        assert result.overrun == pytest.approx(0.0)
        assert tuple(result) == ("demand-surge", 90.0)

    def test_stress_test_rejects_less_than_total_relief(self) -> None:
        result = capacity_stress_test(100.0, [("total-relief", -1.0)])[0]
        assert result.stressed_backlog_hours == 0.0
        with pytest.raises(ValueError, match="less than -100%"):
            capacity_stress_test(100.0, [("impossible-relief", -1.01)])


class TestCapacityModel:
    def test_completion_days_and_cost_scale_with_backlog(self) -> None:
        small = CapacityModel(40, 2, 50, 8)
        large = CapacityModel(400, 2, 50, 8)
        assert small.completion_days < large.completion_days
        assert small.cost_estimate < large.cost_estimate
        assert small.completion_days == pytest.approx(40 / (2 * 8))

    def test_crew_sensitivity_is_negative_and_rate_sensitivity_matches_backlog(self) -> None:
        model = CapacityModel(100, 2, 50, 8)
        # More crew shortens the timeline, so the derivative is negative.
        assert model.crew_sensitivity < 0.0
        assert model.rate_sensitivity == pytest.approx(100.0, rel=1e-3)

    def test_utilization_rate_is_bounded(self) -> None:
        model = CapacityModel(100, 2, 50, 8)
        assert model.utilization_rate(rated_capacity_hours_per_day=16) == pytest.approx(1.0)
        assert 0.0 <= model.utilization_rate(rated_capacity_hours_per_day=64) <= 1.0

    def test_capacity_cache_invalidates_when_parameters_change(self) -> None:
        model = CapacityModel(100, 2, 50, 8)
        first = model.completion_days
        cached_value = model._cached_completion_days
        assert model.completion_days == cached_value
        model.backlog_hours = 400
        assert model.completion_days != first
        assert model._hash_completion_days == model._param_hash()

    def test_aggregation_rejects_length_mismatch(self) -> None:
        with pytest.raises(ValueError):
            aggregate_capacity([CapacityModel(100, 2, 50, 8)], [])


class TestOperationsAlgebra:
    def test_empty_organization_returns_zero_operational_metrics(self) -> None:
        metrics = OperationsAnalytics().operational_metrics()
        assert metrics.backlog_hours_at_risk_95 == Decimal("0")
        assert metrics.backlog_hours_at_risk_99 == Decimal("0")
        assert metrics.utilization_rate == Decimal("0")

    def test_provider_only_book_uses_gross_committed_hours_for_parametric_risk(self) -> None:
        organization = OperationsAnalytics([workload("COMP-03", "-2", "100")])
        result = organization.compute_backlog_risk(hours_volatility=0.1)
        assert organization.total_exposure_value == Decimal("-200")
        assert organization.gross_committed_hours == Decimal("200")
        assert result["parametric_backlog_risk"] == pytest.approx(parametric_backlog_risk(200, 0.1))

    def test_max_backlog_overrun_includes_the_initial_value(self) -> None:
        organization = OperationsAnalytics()
        for delta in (-10.0, 3.0, 2.0):
            organization.record_organization_backlog(delta)

        assert organization.max_backlog_overrun() == pytest.approx(5.0)

    def test_algebra_aggregates_without_mutating_operands(self) -> None:
        left = OperationsAnalytics(
            [workload("CNC-01", "2", "100", realized="1")], budget=Decimal("10")
        )
        right = OperationsAnalytics(
            [workload("CNC-01", "3", "200", unrealized="4")], budget=Decimal("5")
        )
        combined = left + right
        combined_workload = combined.get_workload("CNC-01")
        assert combined_workload is not None
        assert combined_workload.net_hours == Decimal("5")
        assert combined_workload.average_service_rate == Decimal("160")
        assert combined_workload.realized_cost == Decimal("1")
        assert combined_workload.unrealized_cost == Decimal("4")
        assert (
            combined.total_exposure_value == left.total_exposure_value + right.total_exposure_value
        )
        assert combined.total_cost == left.total_cost + right.total_cost
        assert left.get_workload("CNC-01").net_hours == Decimal("2")  # type: ignore[union-attr]
        assert right.get_workload("CNC-01").net_hours == Decimal("3")  # type: ignore[union-attr]

        scaled = left * 2
        assert scaled.get_workload("CNC-01").net_hours == Decimal("4")  # type: ignore[union-attr]
        assert left.get_workload("CNC-01").net_hours == Decimal("2")  # type: ignore[union-attr]

    def test_partial_offset_preserves_value_and_cost(self) -> None:
        left = OperationsAnalytics([workload("CNC-01", "2", "100", realized="2")])
        right = OperationsAnalytics([workload("CNC-01", "-1", "200", unrealized="3")])
        combined = left + right
        combined_workload = combined.get_workload("CNC-01")

        assert combined_workload is not None
        assert combined_workload.net_hours == Decimal("1")
        assert combined_workload.average_service_rate == Decimal("100")
        assert combined.snapshot().budget_balance == Decimal("-100")
        assert (
            combined.total_exposure_value == left.total_exposure_value + right.total_exposure_value
        )
        assert combined.total_cost == left.total_cost + right.total_cost
        assert left.get_workload("CNC-01").net_hours == Decimal("2")  # type: ignore[union-attr]
        assert right.get_workload("CNC-01").net_hours == Decimal("-1")  # type: ignore[union-attr]

    def test_full_offset_flattens_exactly_and_preserves_invariants(self) -> None:
        left = OperationsAnalytics([workload("CNC-01", "2", "100", realized="2")])
        right = OperationsAnalytics([workload("CNC-01", "-2", "200", unrealized="3")])
        combined = left + right
        combined_workload = combined.get_workload("CNC-01")

        assert combined_workload is not None
        assert combined_workload.net_hours == Decimal("0")
        assert combined_workload.average_service_rate == Decimal("0")
        assert combined_workload.last_rate is None
        assert combined.snapshot().budget_balance == Decimal("-200")
        assert (
            combined.total_exposure_value == left.total_exposure_value + right.total_exposure_value
        )
        assert combined.total_cost == left.total_cost + right.total_cost

    def test_subtraction_flips_side_and_preserves_invariants(self) -> None:
        left = OperationsAnalytics([workload("CNC-01", "1", "100", realized="3")])
        right = OperationsAnalytics([workload("CNC-01", "2", "200", realized="5")])
        difference = left - right
        difference_workload = difference.get_workload("CNC-01")

        assert difference_workload is not None
        assert difference_workload.net_hours == Decimal("-1")
        assert difference_workload.average_service_rate == Decimal("200")
        assert difference.snapshot().budget_balance == Decimal("-100")
        assert (
            difference.total_exposure_value
            == left.total_exposure_value - right.total_exposure_value
        )
        assert difference.total_cost == left.total_cost - right.total_cost
        assert left.get_workload("CNC-01").net_hours == Decimal("1")  # type: ignore[union-attr]
        assert right.get_workload("CNC-01").net_hours == Decimal("2")  # type: ignore[union-attr]

    def test_provider_synchronization_and_explicit_replacement(self) -> None:
        engine_workloads = [workload("CNC-01", "1", "100")]
        organization = OperationsAnalytics(workload_provider=lambda: engine_workloads)
        assert organization.total_exposure_value == Decimal("100")
        engine_workloads[:] = [workload("CNC-01", "2", "125")]
        assert organization.total_exposure_value == Decimal("250")

        organization.replace_workloads([workload("ROBOT-07", "3", "10")])
        standalone = OperationsAnalytics()
        standalone.replace_workloads([workload("ROBOT-07", "3", "10")])
        assert standalone.total_exposure_value == Decimal("30")

    def test_snapshot_uses_final_core_aggregation_fields(self) -> None:
        organization = OperationsAnalytics(
            [workload("CNC-01", "2", "100", realized="3", unrealized="4")],
            budget=Decimal("10"),
        )
        snapshot = organization.snapshot()
        assert snapshot.total_exposure_value == Decimal("210")
        assert snapshot.total_realized_cost == Decimal("3")
        assert snapshot.total_unrealized_cost == Decimal("4")

"""Regression coverage for the validated risk analytics contract."""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

from qxm.core.models import Position
from qxm.risk.greeks import (
    OptionPricer,
    aggregate_greeks,
    bs_call_price,
    bs_put_price,
    implied_volatility,
)
from qxm.risk.portfolio import PortfolioAnalytics
from qxm.risk.var import (
    VaREngine,
    conditional_var,
    historical_var,
    parametric_var,
    parametric_var_portfolio,
    stress_test,
)


def position(
    symbol: str,
    quantity: str,
    price: str,
    realized: str = "0",
    unrealized: str = "0",
) -> Position:
    return Position(
        client_id="client",
        symbol=symbol,
        quantity=Decimal(quantity),
        average_entry_price=Decimal(price),
        realized_pnl=Decimal(realized),
        unrealized_pnl=Decimal(unrealized),
    )


class TestVarConvention:
    def test_parametric_var_is_non_negative_and_monotonic(self) -> None:
        var_95 = parametric_var(1_000_000, 0.02, confidence=0.95)
        var_99 = parametric_var(1_000_000, 0.02, confidence=0.99)
        assert var_95 > 0
        assert var_99 > var_95

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
    def test_parametric_var_rejects_bad_inputs(
        self, value: float, volatility: float, confidence: float, horizon: int
    ) -> None:
        with pytest.raises(ValueError):
            parametric_var(value, volatility, confidence, horizon)

    def test_parametric_var_allows_zero_exposure(self) -> None:
        assert parametric_var(0, 0.02, confidence=0.95) == 0.0

    def test_historical_only_engine_does_not_require_portfolio_value(self) -> None:
        result = VaREngine().compute(
            portfolio_value=0,
            pnl_history=[1.0, -2.0, -4.0],
            confidence=0.95,
        )
        assert "parametric_var" not in result
        assert result["historical_var"] >= 0
        assert result["conditional_var"] >= result["historical_var"]

    def test_historical_var_and_expected_shortfall_are_losses(self) -> None:
        pnl = [4.0, 2.0, -1.0, -3.0, -7.0, -10.0]
        var = historical_var(pnl, confidence=0.8)
        expected_shortfall = conditional_var(pnl, confidence=0.8)
        assert var >= 0
        assert expected_shortfall >= var

    def test_historical_var_rejects_empty_or_non_finite_history(self) -> None:
        with pytest.raises(ValueError):
            historical_var([])
        with pytest.raises(ValueError):
            conditional_var([1.0, float("inf")])

    def test_covariance_validation_and_named_stress_result(self) -> None:
        with pytest.raises(ValueError):
            parametric_var_portfolio(100, np.array([1.0, 0.0]), np.array([[1.0, 2.0], [2.0, 1.0]]))
        result = stress_test(100.0, [("equity-down", -0.1)])[0]
        assert result.name == "equity-down"
        assert result.change == pytest.approx(-10.0)
        assert result.loss == pytest.approx(10.0)
        assert tuple(result) == ("equity-down", 90.0)

    def test_stress_test_rejects_less_than_total_loss(self) -> None:
        assert stress_test(100.0, [("total-loss", -1.0)])[0].stressed_value == 0.0
        with pytest.raises(ValueError, match="less than -100%"):
            stress_test(100.0, [("impossible-loss", -1.01)])


class TestGreeks:
    def test_put_call_parity_and_delta_bounds(self) -> None:
        call = bs_call_price(100, 105, 1.5, 0.03, 0.25)
        put = bs_put_price(100, 105, 1.5, 0.03, 0.25)
        assert call - put == pytest.approx(100 - 105 * np.exp(-0.03 * 1.5))
        assert 0.0 <= OptionPricer(100, 105, 1.5, 0.03, 0.25, True).delta <= 1.0
        assert -1.0 <= OptionPricer(100, 105, 1.5, 0.03, 0.25, False).delta <= 0.0

    def test_greek_cache_invalidates_when_parameters_change(self) -> None:
        pricer = OptionPricer(100, 100, 1, 0.02, 0.2)
        first = pricer.delta
        cached_value = pricer._cached_delta
        assert pricer.delta == cached_value
        pricer.S = 110
        assert pricer.delta != first
        assert pricer._hash_delta == pricer._param_hash()

    def test_implied_volatility_recovers_price_and_rejects_arbitrage(self) -> None:
        market_price = bs_call_price(100, 105, 1.0, 0.02, 0.37)
        assert implied_volatility(market_price, 100, 105, 1.0, 0.02) == pytest.approx(
            0.37, abs=1e-5
        )
        with pytest.raises(ValueError):
            implied_volatility(101, 100, 100, 1.0, 0.02)

    def test_aggregation_rejects_length_mismatch(self) -> None:
        with pytest.raises(ValueError):
            aggregate_greeks([OptionPricer(100, 100, 1, 0.02, 0.2)], [])


class TestPortfolioAlgebra:
    def test_empty_portfolio_returns_zero_risk_metrics(self) -> None:
        metrics = PortfolioAnalytics().risk_metrics()
        assert metrics.var_95 == Decimal("0")
        assert metrics.var_99 == Decimal("0")
        assert metrics.delta == Decimal("0")

    def test_short_only_book_uses_gross_exposure_for_parametric_var(self) -> None:
        portfolio = PortfolioAnalytics([position("SHORT", "-2", "100")])
        result = portfolio.compute_var(daily_volatility=0.1)
        assert portfolio.total_value == Decimal("-200")
        assert portfolio.gross_exposure == Decimal("200")
        assert result["parametric_var"] == pytest.approx(parametric_var(200, 0.1))

    def test_drawdown_includes_the_initial_portfolio_value(self) -> None:
        portfolio = PortfolioAnalytics()
        for pnl in (-10.0, 3.0, 2.0):
            portfolio.record_portfolio_pnl(pnl)

        assert portfolio.max_drawdown() == pytest.approx(-10.0)

    def test_algebra_aggregates_without_mutating_operands(self) -> None:
        left = PortfolioAnalytics([position("ABC", "2", "100", realized="1")], cash=Decimal("10"))
        right = PortfolioAnalytics([position("ABC", "3", "200", unrealized="4")], cash=Decimal("5"))
        combined = left + right
        combined_position = combined.get_position("ABC")
        assert combined_position is not None
        assert combined_position.quantity == Decimal("5")
        assert combined_position.average_entry_price == Decimal("160")
        assert combined_position.realized_pnl == Decimal("1")
        assert combined_position.unrealized_pnl == Decimal("4")
        assert combined.total_value == left.total_value + right.total_value
        assert combined.total_pnl == left.total_pnl + right.total_pnl
        assert left.get_position("ABC").quantity == Decimal("2")  # type: ignore[union-attr]
        assert right.get_position("ABC").quantity == Decimal("3")  # type: ignore[union-attr]

        scaled = left * 2
        assert scaled.get_position("ABC").quantity == Decimal("4")  # type: ignore[union-attr]
        assert left.get_position("ABC").quantity == Decimal("2")  # type: ignore[union-attr]

    def test_partial_offset_preserves_value_and_pnl(self) -> None:
        left = PortfolioAnalytics([position("ABC", "2", "100", realized="2")])
        right = PortfolioAnalytics([position("ABC", "-1", "200", unrealized="3")])
        combined = left + right
        combined_position = combined.get_position("ABC")

        assert combined_position is not None
        assert combined_position.quantity == Decimal("1")
        assert combined_position.average_entry_price == Decimal("100")
        assert combined.snapshot().cash_balance == Decimal("-100")
        assert combined.total_value == left.total_value + right.total_value
        assert combined.total_pnl == left.total_pnl + right.total_pnl
        assert left.get_position("ABC").quantity == Decimal("2")  # type: ignore[union-attr]
        assert right.get_position("ABC").quantity == Decimal("-1")  # type: ignore[union-attr]

    def test_full_offset_flattens_exactly_and_preserves_invariants(self) -> None:
        left = PortfolioAnalytics([position("ABC", "2", "100", realized="2")])
        right = PortfolioAnalytics([position("ABC", "-2", "200", unrealized="3")])
        combined = left + right
        combined_position = combined.get_position("ABC")

        assert combined_position is not None
        assert combined_position.quantity == Decimal("0")
        assert combined_position.average_entry_price == Decimal("0")
        assert combined_position.last_price is None
        assert combined.snapshot().cash_balance == Decimal("-200")
        assert combined.total_value == left.total_value + right.total_value
        assert combined.total_pnl == left.total_pnl + right.total_pnl

    def test_subtraction_flips_side_and_preserves_invariants(self) -> None:
        left = PortfolioAnalytics([position("ABC", "1", "100", realized="3")])
        right = PortfolioAnalytics([position("ABC", "2", "200", realized="5")])
        difference = left - right
        difference_position = difference.get_position("ABC")

        assert difference_position is not None
        assert difference_position.quantity == Decimal("-1")
        assert difference_position.average_entry_price == Decimal("200")
        assert difference.snapshot().cash_balance == Decimal("-100")
        assert difference.total_value == left.total_value - right.total_value
        assert difference.total_pnl == left.total_pnl - right.total_pnl
        assert left.get_position("ABC").quantity == Decimal("1")  # type: ignore[union-attr]
        assert right.get_position("ABC").quantity == Decimal("2")  # type: ignore[union-attr]

    def test_provider_synchronization_and_explicit_replacement(self) -> None:
        engine_positions = [position("ABC", "1", "100")]
        portfolio = PortfolioAnalytics(position_provider=lambda: engine_positions)
        assert portfolio.total_value == Decimal("100")
        engine_positions[:] = [position("ABC", "2", "125")]
        assert portfolio.total_value == Decimal("250")

        portfolio.replace_positions([position("XYZ", "3", "10")])
        standalone = PortfolioAnalytics()
        standalone.replace_positions([position("XYZ", "3", "10")])
        assert standalone.total_value == Decimal("30")

    def test_snapshot_uses_final_core_aggregation_fields(self) -> None:
        portfolio = PortfolioAnalytics(
            [position("ABC", "2", "100", realized="3", unrealized="4")],
            cash=Decimal("10"),
        )
        snapshot = portfolio.snapshot()
        assert snapshot.total_market_value == Decimal("210")
        assert snapshot.total_realized_pnl == Decimal("3")
        assert snapshot.total_unrealized_pnl == Decimal("4")

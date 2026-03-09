"""Tests for risk analytics — VaR, Greeks, portfolio metrics."""

from __future__ import annotations

import numpy as np
import pytest

from qxm.risk.var import parametric_var, historical_var, conditional_var
from qxm.risk.greeks import OptionPricer, bs_call_price, bs_put_price


class TestParametricVaR:
    """Test Value at Risk computations."""

    def test_var_is_negative(self):
        """VaR should represent a loss — i.e. a negative number."""
        returns = np.random.normal(0.001, 0.02, 252)
        var = parametric_var(returns, confidence=0.95)
        # NOTE: This test will catch the planted bug — norm.ppf(0.95)
        # returns a positive z-score, so VaR comes out positive (gain).
        # It should use norm.ppf(1 - 0.95) = norm.ppf(0.05) to get the
        # left-tail loss.
        assert var < 0, f"VaR should be negative (a loss), got {var}"

    def test_higher_confidence_larger_loss(self):
        """99% VaR should be a larger loss than 95% VaR."""
        returns = np.random.normal(0.001, 0.02, 252)
        var_95 = parametric_var(returns, confidence=0.95)
        var_99 = parametric_var(returns, confidence=0.99)
        assert var_99 < var_95, "99% VaR should be more negative than 95%"

    def test_historical_var(self):
        """Historical VaR should also be negative at 95%."""
        returns = np.random.normal(-0.001, 0.02, 252)
        var = historical_var(returns, confidence=0.95)
        assert var < 0

    def test_conditional_var_more_extreme(self):
        """CVaR should be more extreme (more negative) than VaR."""
        returns = np.random.normal(-0.001, 0.03, 1000)
        var = historical_var(returns, confidence=0.95)
        cvar = conditional_var(returns, confidence=0.95)
        assert cvar <= var


class TestGreeks:
    """Test Black-Scholes pricing and Greeks."""

    def test_call_price_positive(self):
        """Call option should have positive price."""
        price = bs_call_price(S=100, K=100, T=1.0, r=0.05, sigma=0.2)
        assert price > 0

    def test_put_price_positive(self):
        """Put option should have positive price."""
        price = bs_put_price(S=100, K=100, T=1.0, r=0.05, sigma=0.2)
        assert price > 0

    def test_call_delta_between_0_and_1(self):
        """Call delta should be between 0 and 1."""
        pricer = OptionPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.2)
        assert 0 < pricer.call_delta < 1

    def test_put_delta_between_neg1_and_0(self):
        """Put delta should be between -1 and 0.

        NOTE: This test will catch the planted bug — the put delta
        method returns N(d1) instead of N(d1) - 1, so it'll be
        positive when it should be negative.
        """
        pricer = OptionPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.2)
        assert -1 < pricer.put_delta < 0, (
            f"Put delta should be negative, got {pricer.put_delta}"
        )

    def test_gamma_positive(self):
        """Gamma should always be positive."""
        pricer = OptionPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.2)
        assert pricer.gamma > 0

    def test_vega_positive(self):
        """Vega should always be positive."""
        pricer = OptionPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.2)
        assert pricer.vega > 0

    def test_put_call_parity(self):
        """Put-call parity: C - P = S - K * e^(-rT)."""
        S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.2
        call = bs_call_price(S, K, T, r, sigma)
        put = bs_put_price(S, K, T, r, sigma)
        parity_diff = call - put - (S - K * np.exp(-r * T))
        assert abs(parity_diff) < 1e-6


class TestOptionPricer:
    """Test the OptionPricer class with descriptor caching."""

    def test_pricer_caches_greeks(self):
        """Accessing a cached Greek twice should use the cache."""
        pricer = OptionPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.2)
        delta1 = pricer.call_delta
        delta2 = pricer.call_delta
        assert delta1 == delta2

    def test_pricer_invalidates_on_param_change(self):
        """Changing S should invalidate the cache."""
        pricer = OptionPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.2)
        delta_before = pricer.call_delta
        pricer.S = 110
        delta_after = pricer.call_delta
        assert delta_after != delta_before

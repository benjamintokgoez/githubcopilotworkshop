"""Black-Scholes option pricing and Greeks computation.

Implements the standard Black-Scholes-Merton (BSM) model for European
options pricing and all first- and second-order sensitivity measures
(the "Greeks").

All formulas use the conventional notation:

    S  — spot price of the underlying
    K  — strike price
    T  — time to expiration (in years)
    r  — risk-free interest rate (annualised, continuously compounded)
    σ  — implied volatility (annualised)

The ``CachedGreek`` descriptor provides lazy computation with automatic
cache invalidation when the underlying parameters change — this avoids
redundant recalculation of computationally expensive partial derivatives
during portfolio-level aggregation.
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

import numpy as np
from scipy.stats import norm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CachedGreek descriptor — lazy compute + cache invalidation
# ---------------------------------------------------------------------------

class CachedGreek:
    """Data descriptor that lazily computes a Greek sensitivity measure and
    caches the result.  The cache is invalidated when *any* pricing
    parameter (S, K, T, r, sigma) changes — detected by comparing a
    hash of the parameter tuple.

    Usage as a class attribute::

        class OptionPricer:
            delta = CachedGreek("_compute_delta")
            gamma = CachedGreek("_compute_gamma")

    When accessed on an instance, the descriptor calls the named method
    on the instance, caches the result, and returns it.  Subsequent
    accesses return the cached value unless ``_param_hash`` has changed.
    """

    def __init__(self, compute_method: str) -> None:
        self._compute_method = compute_method
        self._cache_attr: Optional[str] = None
        self._hash_attr: Optional[str] = None

    def __set_name__(self, owner: type, name: str) -> None:
        self._cache_attr = f"_cached_{name}"
        self._hash_attr = f"_hash_{name}"

    def __get__(self, obj: Any, objtype: type = None) -> Any:
        if obj is None:
            return self
        current_hash = obj._param_hash()
        cached_hash = getattr(obj, self._hash_attr, None)
        if cached_hash == current_hash:
            cached_val = getattr(obj, self._cache_attr, None)
            if cached_val is not None:
                return cached_val
        # Compute
        method = getattr(obj, self._compute_method)
        value = method()
        object.__setattr__(obj, self._cache_attr, value)
        object.__setattr__(obj, self._hash_attr, current_hash)
        return value

    def __set__(self, obj: Any, value: Any) -> None:
        raise AttributeError("Greeks are read-only computed properties")


# ---------------------------------------------------------------------------
# BSM core functions
# ---------------------------------------------------------------------------

def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    return (math.log(S / K) + (r + sigma ** 2 / 2) * T) / (sigma * math.sqrt(T))


def _d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
    return _d1(S, K, T, r, sigma) - sigma * math.sqrt(T)


def bs_call_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes European call option price."""
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)


def bs_put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes European put option price (via put-call parity)."""
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


# ---------------------------------------------------------------------------
# Option Pricer with descriptor-cached Greeks
# ---------------------------------------------------------------------------

class OptionPricer:
    """Prices a single European option and computes all Greeks.

    The Greeks are accessed as descriptor-cached properties — computed
    lazily on first access and cached until the pricing parameters change.

    **BUG (Challenge 3):** The put delta is implemented as ``N(d1)``
    instead of the correct ``N(d1) - 1``.  Put delta should always be
    negative for a standard European put, but this implementation
    returns a *positive* value.
    """

    # Descriptor-cached Greeks
    delta = CachedGreek("_compute_delta")
    gamma = CachedGreek("_compute_gamma")
    theta = CachedGreek("_compute_theta")
    vega = CachedGreek("_compute_vega")
    rho = CachedGreek("_compute_rho")

    def __init__(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        is_call: bool = True,
    ) -> None:
        self.S = S
        self.K = K
        self.T = T
        self.r = r
        self.sigma = sigma
        self.is_call = is_call

    def _param_hash(self) -> int:
        return hash((self.S, self.K, self.T, self.r, self.sigma, self.is_call))

    # -- Price -----------------------------------------------------------

    def price(self) -> float:
        if self.is_call:
            return bs_call_price(self.S, self.K, self.T, self.r, self.sigma)
        return bs_put_price(self.S, self.K, self.T, self.r, self.sigma)

    # -- Greeks computations ---------------------------------------------

    def _compute_delta(self) -> float:
        d1 = _d1(self.S, self.K, self.T, self.r, self.sigma)
        if self.is_call:
            return norm.cdf(d1)
        # BUG: should be norm.cdf(d1) - 1, but returns norm.cdf(d1)
        # Put delta must be negative; N(d1) is always positive
        return norm.cdf(d1)

    def _compute_gamma(self) -> float:
        d1 = _d1(self.S, self.K, self.T, self.r, self.sigma)
        return norm.pdf(d1) / (self.S * self.sigma * math.sqrt(self.T))

    def _compute_theta(self) -> float:
        d1 = _d1(self.S, self.K, self.T, self.r, self.sigma)
        d2 = _d2(self.S, self.K, self.T, self.r, self.sigma)
        term1 = -(self.S * norm.pdf(d1) * self.sigma) / (2 * math.sqrt(self.T))
        if self.is_call:
            term2 = -self.r * self.K * math.exp(-self.r * self.T) * norm.cdf(d2)
        else:
            term2 = self.r * self.K * math.exp(-self.r * self.T) * norm.cdf(-d2)
        return (term1 + term2) / 365.0  # Daily theta

    def _compute_vega(self) -> float:
        d1 = _d1(self.S, self.K, self.T, self.r, self.sigma)
        return self.S * norm.pdf(d1) * math.sqrt(self.T) / 100.0  # Per 1% move

    def _compute_rho(self) -> float:
        d2 = _d2(self.S, self.K, self.T, self.r, self.sigma)
        if self.is_call:
            return self.K * self.T * math.exp(-self.r * self.T) * norm.cdf(d2) / 100.0
        return -self.K * self.T * math.exp(-self.r * self.T) * norm.cdf(-d2) / 100.0

    # -- Summary --------------------------------------------------------

    def greeks_dict(self) -> Dict[str, float]:
        return {
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
        }

    def __repr__(self) -> str:
        kind = "Call" if self.is_call else "Put"
        return (
            f"OptionPricer({kind} S={self.S} K={self.K} T={self.T} "
            f"r={self.r} σ={self.sigma} price={self.price():.4f})"
        )


# ---------------------------------------------------------------------------
# Implied volatility (Newton-Raphson)
# ---------------------------------------------------------------------------

def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    is_call: bool = True,
    tol: float = 1e-6,
    max_iter: int = 100,
) -> Optional[float]:
    """Compute implied volatility via Newton-Raphson iteration.

    Uses vega as the derivative of price with respect to sigma.
    Returns ``None`` if convergence fails.
    """
    sigma = 0.3  # Initial guess
    for _ in range(max_iter):
        pricer = OptionPricer(S, K, T, r, sigma, is_call)
        price = pricer.price()
        vega_val = pricer.vega * 100.0  # Undo the /100 scaling
        if abs(vega_val) < 1e-12:
            return None
        diff = price - market_price
        if abs(diff) < tol:
            return sigma
        sigma -= diff / vega_val
        if sigma <= 0:
            sigma = 0.001
    return None


# ---------------------------------------------------------------------------
# Multi-option Greeks aggregation
# ---------------------------------------------------------------------------

def aggregate_greeks(
    pricers: list[OptionPricer],
    quantities: list[float],
) -> Dict[str, float]:
    """Aggregate Greeks across a portfolio of options.

    .. math::

        \\Delta_{\\text{portfolio}} = \\sum_{i=1}^{n} q_i \\cdot \\Delta_i

    Same aggregation applies to all Greeks.
    """
    agg = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    for pricer, qty in zip(pricers, quantities):
        greeks = pricer.greeks_dict()
        for key in agg:
            agg[key] += greeks[key] * qty
    return agg

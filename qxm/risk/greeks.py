"""Validated Black-Scholes-Merton pricing, Greeks, and implied volatility.

Pricing and solver routines deliberately use finite ``float`` values because
SciPy's normal CDF/PDF and root finding are numerical algorithms.  Monetary
``Decimal`` values belong at the calling domain boundary.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from scipy.stats import norm


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


def _parameters(
    S: float, K: float, T: float, r: float, sigma: float
) -> tuple[float, float, float, float, float]:
    spot = _finite_float(S, "S")
    strike = _finite_float(K, "K")
    expiry = _finite_float(T, "T")
    rate = _finite_float(r, "r")
    volatility = _finite_float(sigma, "sigma")
    if spot <= 0:
        raise ValueError("S must be positive")
    if strike <= 0:
        raise ValueError("K must be positive")
    if expiry < 0:
        raise ValueError("T must be non-negative")
    if volatility < 0:
        raise ValueError("sigma must be non-negative")
    return spot, strike, expiry, rate, volatility


def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    return (math.log(S / K) + (r + sigma**2 / 2.0) * T) / (sigma * math.sqrt(T))


def _d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
    return _d1(S, K, T, r, sigma) - sigma * math.sqrt(T)


def _deterministic_price(S: float, K: float, T: float, r: float, is_call: bool) -> float:
    discounted_strike = K * math.exp(-r * T)
    if is_call:
        return max(S - discounted_strike, 0.0)
    return max(discounted_strike - S, 0.0)


def _deterministic_delta(S: float, K: float, T: float, r: float, is_call: bool) -> float:
    threshold = K * math.exp(-r * T)
    if math.isclose(S, threshold, rel_tol=0.0, abs_tol=1e-12):
        return 0.5 if is_call else -0.5
    if is_call:
        return 1.0 if S > threshold else 0.0
    return -1.0 if S < threshold else 0.0


def bs_call_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Return a European call price, using intrinsic value at expiry."""
    spot, strike, expiry, rate, volatility = _parameters(S, K, T, r, sigma)
    if expiry == 0 or volatility == 0:
        return _deterministic_price(spot, strike, expiry, rate, True)
    d1 = _d1(spot, strike, expiry, rate, volatility)
    d2 = _d2(spot, strike, expiry, rate, volatility)
    return float(spot * norm.cdf(d1) - strike * math.exp(-rate * expiry) * norm.cdf(d2))


def bs_put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Return a European put price, using intrinsic value at expiry."""
    spot, strike, expiry, rate, volatility = _parameters(S, K, T, r, sigma)
    if expiry == 0 or volatility == 0:
        return _deterministic_price(spot, strike, expiry, rate, False)
    d1 = _d1(spot, strike, expiry, rate, volatility)
    d2 = _d2(spot, strike, expiry, rate, volatility)
    return float(strike * math.exp(-rate * expiry) * norm.cdf(-d2) - spot * norm.cdf(-d1))


class CachedGreek:
    """Descriptor that caches a Greek until an option parameter changes."""

    def __init__(self, compute_method: str) -> None:
        self._compute_method = compute_method
        self._cache_attr = ""
        self._hash_attr = ""

    def __set_name__(self, owner: type[Any], name: str) -> None:
        self._cache_attr = f"_cached_{name}"
        self._hash_attr = f"_hash_{name}"

    def __get__(self, obj: Any, objtype: type[Any] | None = None) -> Any:
        if obj is None:
            return self
        current_hash = obj._param_hash()
        if getattr(obj, self._hash_attr, None) == current_hash and hasattr(obj, self._cache_attr):
            return getattr(obj, self._cache_attr)
        value = getattr(obj, self._compute_method)()
        setattr(obj, self._cache_attr, value)
        setattr(obj, self._hash_attr, current_hash)
        return value

    def __set__(self, obj: Any, value: Any) -> None:
        raise AttributeError("Greeks are read-only computed properties")


class OptionPricer:
    """Price one European option with descriptor-cached Black-Scholes Greeks."""

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
        self.S, self.K, self.T, self.r, self.sigma = _parameters(S, K, T, r, sigma)
        if not isinstance(is_call, bool):
            raise ValueError("is_call must be a bool")
        self.is_call = is_call

    def _current_parameters(self) -> tuple[float, float, float, float, float]:
        return _parameters(self.S, self.K, self.T, self.r, self.sigma)

    def _param_hash(self) -> int:
        return hash((*self._current_parameters(), self.is_call))

    def price(self) -> float:
        """Return the option price for the configured call or put."""
        if self.is_call:
            return bs_call_price(self.S, self.K, self.T, self.r, self.sigma)
        return bs_put_price(self.S, self.K, self.T, self.r, self.sigma)

    def _compute_delta(self) -> float:
        S, K, T, r, sigma = self._current_parameters()
        if T == 0 or sigma == 0:
            return _deterministic_delta(S, K, T, r, self.is_call)
        delta = float(norm.cdf(_d1(S, K, T, r, sigma)))
        return delta if self.is_call else delta - 1.0

    @property
    def call_delta(self) -> float:
        """Compatibility accessor for the call delta at these parameters."""
        S, K, T, r, sigma = self._current_parameters()
        return (
            _deterministic_delta(S, K, T, r, True)
            if T == 0 or sigma == 0
            else float(norm.cdf(_d1(S, K, T, r, sigma)))
        )

    @property
    def put_delta(self) -> float:
        """Compatibility accessor for the put delta at these parameters."""
        S, K, T, r, sigma = self._current_parameters()
        return (
            _deterministic_delta(S, K, T, r, False)
            if T == 0 or sigma == 0
            else float(norm.cdf(_d1(S, K, T, r, sigma)) - 1.0)
        )

    def _compute_gamma(self) -> float:
        S, K, T, r, sigma = self._current_parameters()
        if T == 0 or sigma == 0:
            return 0.0
        return float(norm.pdf(_d1(S, K, T, r, sigma)) / (S * sigma * math.sqrt(T)))

    def _compute_theta(self) -> float:
        S, K, T, r, sigma = self._current_parameters()
        if T == 0:
            return 0.0
        if sigma == 0:
            delta = _deterministic_delta(S, K, T, r, self.is_call)
            return float(-r * K * math.exp(-r * T) * delta / 365.0)
        d1 = _d1(S, K, T, r, sigma)
        d2 = _d2(S, K, T, r, sigma)
        term1 = -(S * norm.pdf(d1) * sigma) / (2.0 * math.sqrt(T))
        if self.is_call:
            term2 = -r * K * math.exp(-r * T) * norm.cdf(d2)
        else:
            term2 = r * K * math.exp(-r * T) * norm.cdf(-d2)
        return float((term1 + term2) / 365.0)

    def _compute_vega(self) -> float:
        S, K, T, r, sigma = self._current_parameters()
        if T == 0 or sigma == 0:
            return 0.0
        return float(S * norm.pdf(_d1(S, K, T, r, sigma)) * math.sqrt(T) / 100.0)

    def _compute_rho(self) -> float:
        S, K, T, r, sigma = self._current_parameters()
        if T == 0 or sigma == 0:
            return 0.0
        d2 = _d2(S, K, T, r, sigma)
        if self.is_call:
            return float(K * T * math.exp(-r * T) * norm.cdf(d2) / 100.0)
        return float(-K * T * math.exp(-r * T) * norm.cdf(-d2) / 100.0)

    def greeks_dict(self) -> dict[str, float]:
        """Return all Greeks with vega and rho expressed per one percent."""
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
            f"r={self.r} sigma={self.sigma} price={self.price():.4f})"
        )


def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    is_call: bool = True,
    tol: float = 1e-6,
    max_iter: int = 100,
) -> float | None:
    """Recover implied volatility with no-arbitrage checks and bisection.

    ``None`` means a valid bounded price could not be bracketed or converged
    within the supplied iteration budget.  Invalid inputs and arbitrage prices
    raise ``ValueError`` rather than producing a misleading volatility.
    """
    if not isinstance(is_call, bool):
        raise ValueError("is_call must be a bool")
    spot, strike, expiry, rate, _ = _parameters(S, K, T, r, 0.0)
    if expiry <= 0:
        raise ValueError("T must be positive for implied volatility")
    observed = _finite_float(market_price, "market_price")
    tolerance = _finite_float(tol, "tol")
    if tolerance <= 0:
        raise ValueError("tol must be positive")
    if isinstance(max_iter, bool) or not isinstance(max_iter, int) or max_iter <= 0:
        raise ValueError("max_iter must be a positive integer")

    discounted_strike = strike * math.exp(-rate * expiry)
    lower = max(0.0, spot - discounted_strike) if is_call else max(0.0, discounted_strike - spot)
    upper = spot if is_call else discounted_strike
    if observed < lower - tolerance or observed >= upper:
        raise ValueError("market_price violates Black-Scholes no-arbitrage bounds")
    if abs(observed - lower) <= tolerance:
        return 0.0

    low, high = 0.0, 0.5
    price_at_high = (
        bs_call_price(spot, strike, expiry, rate, high)
        if is_call
        else bs_put_price(spot, strike, expiry, rate, high)
    )
    while price_at_high < observed and high < 10.0:
        high *= 2.0
        price_at_high = (
            bs_call_price(spot, strike, expiry, rate, high)
            if is_call
            else bs_put_price(spot, strike, expiry, rate, high)
        )
    if price_at_high < observed:
        return None

    for _ in range(max_iter):
        sigma = (low + high) / 2.0
        price = (
            bs_call_price(spot, strike, expiry, rate, sigma)
            if is_call
            else bs_put_price(spot, strike, expiry, rate, sigma)
        )
        if abs(price - observed) <= tolerance:
            return sigma
        if price < observed:
            low = sigma
        else:
            high = sigma
    return None


def aggregate_greeks(
    pricers: Sequence[OptionPricer], quantities: Sequence[float]
) -> dict[str, float]:
    """Aggregate Greeks across equal-length option and quantity sequences."""
    if len(pricers) != len(quantities):
        raise ValueError("pricers and quantities must have equal lengths")
    aggregate = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    for index in range(len(pricers)):
        pricer = pricers[index]
        if not isinstance(pricer, OptionPricer):
            raise ValueError("pricers must contain OptionPricer instances")
        quantity = _finite_float(quantities[index], f"quantities[{index}]")
        for name, value in pricer.greeks_dict().items():
            aggregate[name] += value * quantity
    return aggregate

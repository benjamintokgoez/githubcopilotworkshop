# Challenge 3 — Mathematical Bug Fixes

## Objective

Find and fix 3 mathematical/financial bugs in the risk analytics and matching engine. These bugs produce *wrong numbers* rather than crashes — they're the most dangerous kind.

## Recommended Model

**o3** — Superior at mathematical reasoning, formula verification, and financial domain logic.

## Background

QA reported that:
1. Our Value at Risk numbers are "impossibly optimistic"
2. The options desk says put deltas are wrong
3. A trader was filled at a price they never posted

## Bug Hunt

### Bug 1: VaR Confidence Interval (Severity: Critical)

**File**: `qxm/risk/var.py`

**Symptom**: The `parametric_var` function returns a *positive* value at 95% confidence, implying the portfolio will *gain* money at the 5% worst case. That's... not how VaR works.

**The math**:

VaR at confidence level $\alpha$ should compute:

$$\text{VaR}_\alpha = \mu + z_\alpha \cdot \sigma$$

where $z_\alpha = \Phi^{-1}(1 - \alpha)$ is the **left-tail** quantile.

At $\alpha = 0.95$, we need $\Phi^{-1}(0.05) \approx -1.645$.

**Task**: 
1. Ask Copilot (using **o3**) to verify the VaR formula
2. Identify the incorrect use of `norm.ppf()`
3. Fix the sign/argument

**Verification**:
```bash
pytest tests/test_risk.py::TestParametricVaR::test_var_is_negative -v
```

### Bug 2: Put Delta Error (Severity: High)

**File**: `qxm/risk/greeks.py`

**Symptom**: Put delta is positive (~0.5) instead of negative (should be ~-0.5 for ATM options). This makes our portfolio hedging calculations completely wrong.

**The math**:

For a European put, the Black-Scholes delta is:

$$\Delta_{put} = N(d_1) - 1$$

where $N(\cdot)$ is the standard normal CDF and $d_1$ is:

$$d_1 = \frac{\ln(S/K) + (r + \sigma^2/2)T}{\sigma\sqrt{T}}$$

**Task**:
1. Ask Copilot to verify the put delta formula against Black-Scholes
2. Find where the $-1$ term is missing
3. Fix the computation

**Verification**:
```bash
pytest tests/test_risk.py::TestGreeks::test_put_delta_between_neg1_and_0 -v
```

### Bug 3: Market Order Fill Price (Severity: High)

**File**: `qxm/core/engine.py`

**Symptom**: A market buy order was filled at `None` instead of the resting seller's price. The matching engine uses the wrong price for market orders.

**The logic**:

When a market order matches against a resting limit order, the fill should happen at the **resting order's price** (price-taker gets the maker's price), not the incoming order's price (which is `None` for market orders).

**Task**:
1. Ask Copilot to explain the price priority logic in `_match()`
2. Find the incorrect price assignment in the fill
3. Fix it to always use the resting order's price for the fill

**Verification**:
```bash
pytest tests/test_engine.py::TestMarketOrders::test_market_buy_fills_at_best_ask -v
```

## Verification — All Fixed

```bash
pytest tests/test_risk.py tests/test_engine.py -v
```

All tests in `TestParametricVaR`, `TestGreeks`, and `TestMarketOrders` should pass.

## Stretch Goals

- Ask Copilot (o3) to derive the put-call parity relationship and verify our implementation satisfies it
- Have Copilot explain why `norm.ppf(0.95)` vs `norm.ppf(0.05)` matters financially
- Ask Copilot to add Monte Carlo VaR as an alternative implementation
- Write a property-based test (using `hypothesis`) that validates VaR is always negative

## Time

~45 minutes

---

*Next: [Challenge 4 — Pydantic v1 to v2 Migration](./challenge_04_pydantic_migration.md)*

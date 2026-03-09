# Proctor Guide — Challenge 3: Mathematical Bug Fixes

## Bug Catalogue with Solutions

### Bug 1: VaR Percentile Direction (`qxm/risk/var.py`)

**Location**: `parametric_var()` function

**Problem**: Uses `norm.ppf(confidence)` which gives the *upper* percentile. VaR measures the *loss* threshold, so we need the lower tail: `norm.ppf(1 - confidence)`.

For a 95% confidence VaR:
- `norm.ppf(0.95)` = +1.645 (wrong — this is the gain threshold)
- `norm.ppf(0.05)` = -1.645 (correct — this is the loss threshold)

**Fix**:
```python
# Before (BROKEN):
z_score = norm.ppf(confidence)

# After (FIXED):
z_score = norm.ppf(1 - confidence)
```

**Mathematical explanation**:
VaR at confidence level $\alpha$ = $\mu + z_{1-\alpha} \cdot \sigma \cdot \sqrt{t}$

where $z_{1-\alpha} = \Phi^{-1}(1-\alpha)$ is the quantile function at $1-\alpha$.

**Test that catches it**:
```python
def test_parametric_var_direction():
    """VaR should be negative (a loss), not positive."""
    var = parametric_var(1_000_000, 0.02, 0.95)
    assert var < 0, f"VaR should be negative (loss), got {var}"
```

**Copilot Prompt**:
> "Review the parametric_var function in qxm/risk/var.py. The VaR calculation uses norm.ppf(confidence). Is this correct for computing Value at Risk? Explain the mathematics."

---

### Bug 2: Put Option Delta (`qxm/risk/greeks.py`)

**Location**: `_bs_delta()` function (or the delta computation)

**Problem**: Put delta is computed as `norm.cdf(d1)` but should be `norm.cdf(d1) - 1`.

Call delta: $\Delta_{call} = N(d_1)$ ✓
Put delta:  $\Delta_{put} = N(d_1) - 1$ (from put-call parity)

**Fix**:
```python
# Before (BROKEN):
def _bs_delta(S, K, T, r, sigma, option_type):
    d1 = _d1(S, K, T, r, sigma)
    if option_type == "call":
        return norm.cdf(d1)
    else:
        return norm.cdf(d1)  # BUG: same as call!

# After (FIXED):
def _bs_delta(S, K, T, r, sigma, option_type):
    d1 = _d1(S, K, T, r, sigma)
    if option_type == "call":
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1  # Put-call parity
```

**Mathematical explanation**:
From put-call parity: $P = C - S + Ke^{-rT}$

Taking $\frac{\partial}{\partial S}$: $\Delta_{put} = \Delta_{call} - 1 = N(d_1) - 1$

Put delta should always be in $[-1, 0]$, but the buggy version returns $[0, 1]$.

**Test that catches it**:
```python
def test_put_delta_sign():
    """Put delta should be negative."""
    delta = _bs_delta(100, 100, 1.0, 0.05, 0.2, "put")
    assert -1 <= delta <= 0, f"Put delta should be in [-1, 0], got {delta}"
```

**Copilot Prompt**:
> "Check the Black-Scholes delta calculation in qxm/risk/greeks.py. Is the put delta formula correct? Compare it against the put-call parity relationship."

---

### Bug 3: Market Order Price (`qxm/core/engine.py`)

**Location**: `MatchingEngine._match_order()` method

**Problem**: When a market order matches against a resting limit order, the trade is executed at `incoming.price` (the market order's price, which is typically `None` or 0). It should execute at `resting.price` (the resting limit order's price).

**Fix**:
```python
# Before (BROKEN):
fill_price = incoming.price  # Market order has no meaningful price

# After (FIXED):
fill_price = resting.price  # Use the resting order's price
```

**Market microstructure explanation**:
A market order says "I want to buy/sell at the *best available price*." The best available price is whatever's sitting in the order book — the resting order's price. Using the incoming order's price is meaningless for market orders.

**Test that catches it**:
```python
def test_market_order_fills_at_resting_price():
    """Market orders should fill at the resting limit order's price."""
    # Place a limit sell at 150.00
    # Place a market buy
    # Trade should occur at 150.00, not at market order's price
    assert trade.price == 150.00
```

**Copilot Prompt**:
> "In qxm/core/engine.py, review the order matching logic. When a market order matches against a resting limit order, which price should the trade execute at? Is the current implementation correct?"

---

## Model Recommendation Rationale

**o3** is recommended for this challenge because:
1. Strong mathematical reasoning needed for VaR and BSM formulas
2. Can trace through the chain of mathematical operations to find where the formula diverges from the expected result
3. Better at explaining *why* a formula is wrong, not just *that* it's wrong

If o3 is unavailable, **Claude Sonnet 4** is a good fallback for this challenge.

## Common Pitfalls

- **VaR bug**: Some attendees may suggest `abs(norm.ppf(confidence))` — this masks the sign issue. VaR should naturally be negative (representing a loss).
- **Put delta**: Attendees may not know BSM formulas by heart — that's fine! The point is that Copilot can explain the mathematics.
- **Market order**: Some may argue that market orders *should* use the incoming price for "market with protection" orders — explain that this is a basic market order without protection.

## Verification Commands

```bash
# Run the specific math tests
pytest tests/test_risk.py -v
pytest tests/test_engine.py::TestMarketOrders -v

# Quick manual verification
python -c "
from qxm.risk.var import parametric_var
var = parametric_var(1_000_000, 0.02, 0.95)
print(f'VaR at 95%: {var:,.2f}')
assert var < 0, 'VaR should be negative!'
print('✓ VaR is correctly negative')
"

python -c "
from qxm.risk.greeks import _bs_delta
d = _bs_delta(100, 100, 1.0, 0.05, 0.2, 'put')
print(f'Put delta: {d:.4f}')
assert d < 0, 'Put delta should be negative!'
print('✓ Put delta is correctly negative')
"
```

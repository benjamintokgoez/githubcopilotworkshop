# Business invariants and expected values

**Domain knowledge is not assessed in this workshop.** Everything you need to
judge whether a number is right is written down here, with worked examples. If a
lab asks you to defend a change, you defend it against these invariants - not
against your memory of derivatives pricing.

QuantCore is a **simulated** trading engine built for teaching. None of this is
investment advice, and none of these numbers describe a real market.

Conventions: values are computed with a dot decimal separator, as code requires.
A DACH user interface would display `101,455` where this page writes `101.455`.
See [dach_conventions.md](dach_conventions.md).

---

## 1. Order book and matching

**INV-MATCH-1 - Price-time priority.** Orders match best price first. At the same
price, the order that arrived earlier fills first (FIFO).

**INV-MATCH-2 - Maker price wins.** A market order fills at the **resting**
(maker) order's price. The incoming order never sets the fill price, and a fill
price is never null.

**INV-MATCH-3 - Quantity conservation.** For every trade, the quantity removed
from the buy side equals the quantity removed from the sell side. Cumulative fills
never exceed the order quantity, and remaining quantity is never negative.

**INV-MATCH-4 - No self-crossing book.** After matching completes, the best bid is
strictly below the best ask.

### Worked example (use these numbers)

Resting asks, in arrival order:

| # | Price | Quantity | Arrived (UTC) |
|---|---|---|---|
| A1 | 101.20 | 100 | 2026-08-19T07:14:02Z |
| A2 | 101.20 | 50 | 2026-08-19T07:14:09Z |
| A3 | 101.50 | 200 | 2026-08-19T07:13:55Z |

- A market **buy** for 120 fills 100 from A1, then 20 from A2. Average fill price
  is exactly `101.20`. A3 is untouched even though it arrived first, because
  price beats time.
- A follow-up market **buy** for 200 fills the remaining 30 from A2 at `101.20`
  and 170 from A3 at `101.50`. Average fill price is
  `(30 * 101.20 + 170 * 101.50) / 200 = 101.455`.
- Any result where a fill price is `None`, or where the buyer pays a price that
  never rested on the book, violates INV-MATCH-2.

---

## 2. Risk: Value at Risk

**INV-VAR-1 - Sign convention.** VaR and CVaR are reported as **non-negative loss
magnitudes** everywhere: runtime, API, dashboard, tests, docs. A negative VaR is a
defect, not an optimistic portfolio.

**INV-VAR-2 - Monotone in confidence.** VaR at 99 % is greater than or equal to
VaR at 95 % for the same portfolio and horizon.

**INV-VAR-3 - CVaR dominates VaR.** Conditional VaR (expected shortfall) at a
given confidence is greater than or equal to VaR at that confidence.

**INV-VAR-4 - Horizon scaling.** Under the parametric assumption used here, a
`h`-day VaR scales with `sqrt(h)`, not with `h`.

### Worked example (use these numbers)

Portfolio value `1_000_000.00` EUR, daily volatility `0.015`, mean return `0`,
normal parametric method:

| Measure | Confidence | Horizon | Expected value (EUR) |
|---|---|---|---|
| VaR | 95 % | 1 day | `24672.80` |
| VaR | 99 % | 1 day | `34895.22` |
| VaR | 95 % | 10 days | `78022.26` |
| CVaR | 95 % | 1 day | `30940.69` |
| CVaR | 99 % | 1 day | `39978.21` |

Tolerance: `+/- 0.01` EUR. All five values are positive; that is INV-VAR-1 in
action.

---

## 3. Risk: options and Greeks

**INV-GREEK-1 - Delta bounds.** Call delta lies in `[0, 1]`. Put delta lies in
`[-1, 0]`. A positive put delta is a defect.

**INV-GREEK-2 - Delta relationship.** For the same option parameters,
`call_delta - put_delta = 1`.

**INV-GREEK-3 - Non-negative curvature.** Gamma and vega are non-negative for a
long option position, and are identical for a call and a put with the same
parameters.

**INV-GREEK-4 - Put-call parity.** `call_price - put_price = S - K * exp(-r * T)`.

### Worked example (use these numbers)

Inputs: spot `S = 100.0`, strike `K = 100.0`, risk-free rate `r = 0.02`,
volatility `sigma = 0.20`, time to expiry `T = 1.0` years, no dividends.

| Quantity | Expected value |
|---|---|
| `d1` | `0.200000` |
| `d2` | `0.000000` |
| Call price | `8.916037` |
| Put price | `6.935905` |
| Call delta | `0.579260` |
| Put delta | `-0.420740` |
| Gamma | `0.019552` |
| Vega (per 1 % vol move) | `0.391043` |
| Call theta (per day) | `-0.013399` |
| Put theta (per day) | `-0.008028` |
| Call rho (per 1 % rate move) | `0.490099` |
| Put rho (per 1 % rate move) | `-0.490099` |

Tolerance: `+/- 1e-6`. Parity check: `8.916037 - 6.935905 = 1.980133` and
`100 - 100 * exp(-0.02) = 1.980133`.

Note the scaling convention: vega and rho are quoted per 1 percentage point, and
theta per calendar day. A result that is off by a factor of 100 or 365 is a
convention defect, not a maths defect - and it is exactly the kind of thing a
generated "fix" gets wrong confidently.

---

## 4. Positions and P&L

**INV-POS-1 - Sign convention.** A long position has positive quantity, a short
position has negative quantity.

**INV-POS-2 - Average price changes only on increase.** Adding to a position
updates the volume-weighted average entry price. Reducing a position does not
change the average entry price; it realises P&L.

**INV-POS-3 - Unrealised P&L.** `unrealised = (mark_price - average_price) * quantity`.
The sign works out for shorts without a special case.

**INV-POS-4 - Flat means flat.** When quantity reaches zero, unrealised P&L is
zero and the average price is reset, not carried forward.

### Worked example (use these numbers)

1. Buy 100 at `101.20` -> quantity `100`, average `101.20`.
2. Buy 100 at `101.50` -> quantity `200`, average `101.35`.
3. Sell 50 at `102.00` -> quantity `150`, average stays `101.35`, realised P&L
   `(102.00 - 101.35) * 50 = 32.50` EUR.
4. Mark at `101.00` -> unrealised `(101.00 - 101.35) * 150 = -52.50` EUR.

---

## 5. Time and calendar invariants

**INV-TIME-1 - Storage is UTC.** Every persisted or exchanged timestamp is
timezone-aware UTC. Naive timestamps are a defect.

**INV-TIME-2 - Display is Europe/Berlin.** Presentation converts to
`Europe/Berlin` and shows CET or CEST as applicable, in 24-hour format.

**INV-TIME-3 - A business day is a local day.** The reporting window for business
date `D` is `[D 00:00 Europe/Berlin, D+1 00:00 Europe/Berlin)`, converted to UTC.
It is **not** a fixed 24-hour UTC window and **not** UTC plus a constant offset.

### Worked example (use these numbers)

| Business date (Europe/Berlin) | UTC window start | UTC window end | Length |
|---|---|---|---|
| 2026-03-29 | `2026-03-28T23:00:00Z` | `2026-03-29T22:00:00Z` | 23 hours |
| 2026-08-19 | `2026-08-18T22:00:00Z` | `2026-08-19T22:00:00Z` | 24 hours |
| 2026-10-25 | `2026-10-24T22:00:00Z` | `2026-10-25T23:00:00Z` | 25 hours |

On 2026-03-29 the local hour `02:00` does not exist. On 2026-10-25 the local hour
`02:00` happens twice. Any implementation that adds a constant offset produces
wrong windows on both dates and correct windows on the other 363.

---

## 6. Presentation invariants

**INV-FMT-1 - Decimal comma at the edge only.** Displayed amounts use a decimal
comma and dot thousands separators (`1.234.567,89`). Stored and transmitted values
use a dot (`1234567.89`).

**INV-FMT-2 - Currency is explicit.** A displayed amount carries its currency.
`1.234.567,89 EUR`, not a bare number.

**INV-FMT-3 - Rounding is display-only.** Rounding happens when formatting, never
in the stored value or in intermediate arithmetic.

**INV-FMT-4 - ISO in identifiers.** Filenames, keys and identifiers use ISO 8601
dates (`2026-08-19`), never `19.08.2026`.

---

## How to use invariants in a lab

1. Before you change anything, write down which invariant is being violated.
2. Reproduce the violation and capture the evidence.
3. Make the smallest change that restores the invariant.
4. Prove it with a test that fails before and passes after.
5. State which invariants you did **not** verify. That sentence is part of the
   deliverable - see [evidence.md](evidence.md).

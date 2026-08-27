# Business invariants and expected values

**Domain knowledge is not assessed.** MittelWerk is a synthetic industrial
service platform. Every organisation, site, asset, provider, work order, rate,
telemetry reading, and event is invented.

Machine values use a dot decimal separator. Human-facing German output uses a
decimal comma. See [dach_conventions.md](dach_conventions.md).

## 1. Service dispatch

**INV-DISPATCH-1 - Rate-time priority.** Eligible provider capacity is assigned
at the lowest hourly rate first. Offers at the same rate are consumed FIFO.

**INV-DISPATCH-2 - Provider offer rate is authoritative.** The assignment rate
comes from the accepted provider offer. A request's maximum rate is an
eligibility ceiling, not a billable rate.

**INV-DISPATCH-3 - Hours conservation.** Assigned hours are removed from exactly
one provider offer and added to exactly one request. Neither side can become
negative or exceed its original hours.

### Worked example

| Offer | Rate | Hours | Offered (UTC) |
|---|---:|---:|---|
| CAP-1 | 110.00 EUR/h | 10 | 2026-08-19T07:14:02Z |
| CAP-2 | 110.00 EUR/h | 5 | 2026-08-19T07:14:09Z |
| CAP-3 | 112.00 EUR/h | 20 | 2026-08-19T07:13:55Z |

A 12-hour request capped at `118.00 EUR/h` receives 10 hours from CAP-1 and
2 from CAP-2, all at `110.00 EUR/h`. CAP-3 is untouched. The weighted average
rate is exactly `110.00 EUR/h`.

## 2. SLA and workload analytics

**INV-SLA-1 - Non-negative magnitudes.** Open hours, overdue hours, response
minutes, estimated cost, and utilization are never reported as negative.

**INV-SLA-2 - Overdue is bounded by open.** For one snapshot,
`0 <= overdue_hours <= open_hours`.

**INV-SLA-3 - Cost keeps exact rates.** Estimated service cost is the sum of
`assigned_hours * provider_hourly_rate` using `Decimal`. Formatting and rounding
happen only at the presentation edge.

**INV-SLA-4 - Utilization is bounded.** With positive available capacity,
`utilization = assigned_hours / available_hours` and lies in `[0, 1]`. Zero
capacity returns zero rather than division by zero or invented full utilization.

### Worked example

For `120.00` open hours, `24.00` overdue hours, `160.00` available hours, and
`96.00` assigned hours:

| Metric | Expected value |
|---|---:|
| Overdue fraction | `0.20` |
| Utilization | `0.60` |
| Remaining capacity | `64.00` hours |

Twenty-four overdue hours at `110.00 EUR/h` produce an exact estimated cost of
`2640.00 EUR`.

## 3. Equipment and telemetry

**INV-ASSET-1 - Stable identity.** Asset codes are uppercase, machine-safe
identifiers. Human names may change without changing the asset code.

**INV-ASSET-2 - Positive service values.** Service intervals, hourly rates, and
requested hours are positive. Booleans are not accepted as numeric values.

**INV-TELEM-1 - Ordered observations.** Status summaries sort readings by
timestamp and never combine different assets into one series.

**INV-TELEM-2 - Finite measurements.** NaN and infinite telemetry values are
rejected at the boundary. Missing data remains missing; it is not converted into
a successful zero reading.

## 4. Work-order lifecycle

**INV-WORK-1 - Identity is permanent.** A work-order identifier is reserved on
its first submission attempt and cannot be reused after acceptance, rejection,
cancellation, or completion.

**INV-WORK-2 - Terminal states are final.** Completed, cancelled, rejected, and
expired work orders cannot re-enter the active queue.

**INV-WORK-3 - Caller identity comes from authorization.** API and MCP callers
cannot select another organisation by putting an identity in a work-order body.

**INV-WORK-4 - Unsupported promises fail explicitly.** A requested scheduling or
expiry behavior that has no implementing subsystem is rejected rather than
silently approximated.

## 5. Time and calendar

**INV-TIME-1 - Storage is UTC.** Every persisted or exchanged timestamp is
timezone-aware UTC. Naive timestamps are defects.

**INV-TIME-2 - Display is local.** Presentation converts to `Europe/Berlin` and
uses the correct CET or CEST offset and a 24-hour clock.

**INV-TIME-3 - A business day is a local day.** Date `D` covers
`[D 00:00 Europe/Berlin, D+1 00:00 Europe/Berlin)`, converted to UTC.

| Business date | UTC start | UTC end | Length |
|---|---|---|---:|
| 2026-03-29 | `2026-03-28T23:00:00Z` | `2026-03-29T22:00:00Z` | 23 h |
| 2026-08-19 | `2026-08-18T22:00:00Z` | `2026-08-19T22:00:00Z` | 24 h |
| 2026-10-25 | `2026-10-24T22:00:00Z` | `2026-10-25T23:00:00Z` | 25 h |

## 6. Presentation

**INV-FMT-1 - Decimal comma at the edge only.** German display uses
`1.234.567,89`; JSON, code, configuration, and SQL use `1234567.89`.

**INV-FMT-2 - Currency is explicit.** Display `1.234.567,89 EUR`, not a bare
number. No currency conversion is implied.

**INV-FMT-3 - Rounding is display-only.** Stored values and intermediate
arithmetic keep their exact `Decimal` representation.

**INV-FMT-4 - ISO in identifiers.** Filenames and machine identifiers use
`2026-08-19`, not `19.08.2026`.

## How to use these invariants

1. Name the invariant before changing code.
2. Reproduce the violation.
3. Make the smallest change that restores the invariant.
4. Prove it with fail-before and pass-after evidence.
5. State which adjacent invariants you did not verify.

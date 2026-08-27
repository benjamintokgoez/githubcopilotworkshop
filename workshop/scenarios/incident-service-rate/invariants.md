# Incident invariants

## INV-DISPATCH-1 - rate-time priority

Eligible provider capacity is assigned at the lowest hourly rate first. Offers
at the same rate are consumed in arrival order.

## INV-DISPATCH-2 - provider offer rate is authoritative

An assignment uses the hourly rate on the accepted provider offer. The incoming
request's maximum rate is an eligibility ceiling, not a billable rate.

## INV-DISPATCH-3 - hours are conserved

Every assigned hour is removed from one provider offer and added to the request.
Cumulative assignments never exceed the request or available capacity.

### Worked queue

| Offer | Rate | Hours | Offered (UTC) |
|---|---:|---:|---|
| CAP-1 | 110.00 EUR/h | 10 | 2026-08-19T07:14:02Z |
| CAP-2 | 110.00 EUR/h | 5 | 2026-08-19T07:14:09Z |
| CAP-3 | 112.00 EUR/h | 20 | 2026-08-19T07:13:55Z |

A request for 12 hours with a maximum rate of `118.00 EUR/h` receives 10 hours
from CAP-1 and 2 from CAP-2, both at `110.00 EUR/h`. CAP-3 is untouched.

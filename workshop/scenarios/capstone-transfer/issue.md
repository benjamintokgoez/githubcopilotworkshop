# MW-2026-118 - Fresh telemetry deviation policy

| Field | Value |
|---|---|
| Raised | 2026-08-18, 17:40 CEST |
| Raised by | Regional service operations |
| Needed | Before the next dispatch-policy rollout |

Operations found a recommendation whose average included an old reading from a
previous service state. The policy is registered and callable, but its behaviour
must be corrected across the complete read path.

## Required behaviour

1. A reading is fresh when it belongs to the requested asset and falls inside
   the inclusive interval `[as_of - max_age, as_of]`.
2. Naive timestamps are rejected. Internal and machine-facing timestamps remain
   aware UTC.
3. The deviation policy needs at least three fresh samples.
4. A recommendation is emitted when the absolute deviation is **greater than or
   equal to** the configured threshold.
5. Calculations remain `Decimal`; machine payload decimal values are strings
   using a dot separator.
6. The policy remains discoverable through metaclass registration. Do not add a
   service switch statement or automatically submit a work order.

## Scope

Trace the staged policy models, registry, freshness selector, concrete policy,
catalogue, recommendation service, and tests. Make only the changes required to
restore the stated behaviour. No dashboard, storage, networking, or new
dependency is in scope.

---

*Synthetic telemetry and equipment identifiers only.*

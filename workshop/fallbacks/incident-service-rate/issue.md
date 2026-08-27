# MW-4471 - Service assignment used a rate no provider offered

| Field | Value |
|---|---|
| Reported | 2026-08-19, 09:47 CEST |
| Reporter | Regional service operations |
| Priority | High |
| Affected work order | `WO-2026-0819-0442` |

## What operations observed

An urgent maintenance request for twelve engineering hours was assigned to two
regional providers. The assignment confirmation shows `118.00 EUR/h`, but both
accepted provider offers were `110.00 EUR/h`. The maximum rate on the incoming
request was `118.00 EUR/h`.

Operations believes the providers changed their rates after allocation. The
attached queue snapshot and UTC log excerpt are the available evidence.

## Expected behaviour

- Eligible capacity is used at the lowest offered rate first.
- Offers at the same rate are used FIFO.
- Every assigned hour keeps the rate of the provider offer that supplied it.
- Assigned hours cannot exceed either the request or available provider capacity.

## Scope

Reproduce and repair only the bounded dispatch path staged by this scenario.
Do not add invoicing, provider onboarding, personal technician data, or a new
scheduler. Preserve `Decimal` rates and timezone-aware UTC timestamps.

---

*Synthetic incident. Organisation, provider, asset, and work-order identifiers
are invented and identify no person or real company.*

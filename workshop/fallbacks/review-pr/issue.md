# MW-4488 - Report overdue service workload as non-negative magnitudes

| Field | Value |
|---|---|
| Opened | 2026-08-12, 11:05 CEST |
| Requested by | Regional service operations |
| Priority | Normal |
| Assigned to | Delegated unattended agent run |

The operational summary sometimes returns negative overdue hours and sometimes
positive values. The dashboard displays whichever it receives. Our contract is
simple: `overdue_hours` and `estimated_service_cost` are non-negative magnitudes.

## Requested change

1. Make both values non-negative.
2. Preserve the existing daily and weekly summary horizons.
3. Add a regression check that fails without the correction.

## Explicitly out of scope

- Response field names and shape.
- Human-facing number formatting.
- Storage, telemetry ingestion, or work-order identity.

---

*Synthetic issue for the workshop.*

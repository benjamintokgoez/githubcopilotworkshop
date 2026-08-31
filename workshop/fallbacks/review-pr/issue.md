# MW-4488 - Add an organisation SLA snapshot endpoint

| Field | Value |
|---|---|
| Opened | 2026-08-12, 11:05 CEST |
| Requested by | Regional service operations |
| Priority | Normal |
| Assigned to | Delegated unattended agent run |

Operations needs a protected endpoint that reports the current organisation's
one-day or seven-day service position.

## Requested behaviour

1. Add `GET /api/v1/organizations/me/sla?days=1|7`.
2. Derive organisation identity from the validated `X-API-Key`; callers cannot
   select another organisation in a query, path, or body.
3. Return open requester hours, overdue hours, estimated service cost, and an
   aware-UTC `as_of` timestamp.
4. Hours and costs are non-negative magnitudes. Overdue hours cannot exceed open
   requester hours. Provider capacity is not requester backlog.
5. Keep exact values as `Decimal` and machine JSON as dot-decimal strings.
6. Preserve per-application isolation and ensure one organisation's result can
   never be reused for another.
7. Cover both horizons and a cross-organisation negative case.

## Explicitly out of scope

- Dashboard changes or human-facing number formatting.
- New persistence tables or background refresh jobs.
- Changes to API-key permissions or organisation identity rules.
- Renaming existing response fields.

---

*Synthetic issue for the workshop.*

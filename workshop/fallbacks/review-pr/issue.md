# QXM-4488 - Report VaR as a positive loss magnitude in the risk summary

| Field | Value |
|---|---|
| Opened | 2026-08-12, 11:05 CEST |
| Requested by | Risk reporting (internal consumer of the risk summary endpoint) |
| Priority | Normal |
| Assigned to | Delegated - unattended agent run on branch `agent/qxm-4488-var-sign` |

---

## Problem

The risk summary we consume returns VaR with an inconsistent sign. Some code paths
give us a negative number, some a positive one, and our dashboard shows whichever
it gets. Two weeks ago it displayed a negative VaR during a review meeting and we
spent ten minutes explaining that it did not mean the portfolio could not lose
money.

Per our own convention (INV-VAR-1 in the invariants reference), **VaR and CVaR are
non-negative loss magnitudes everywhere**: runtime, API, dashboard, tests, docs.

## Requested change

1. Make the VaR and CVaR values in the risk summary non-negative loss magnitudes.
2. Keep the 1-day and 10-day horizons that are already exposed.

## Explicitly out of scope

- **The response shape does not change.** We parse it by field name; renaming a
  field is a breaking change for us and needs its own ticket and a deprecation
  window.
- Number formatting. We format for display on our side.
- Storage, persistence and the market-data path. Nothing in this ticket needs
  them.

## Acceptance

- The summary returns non-negative VaR and CVaR for a portfolio that can lose
  money.
- Existing consumers keep working without changes.
- The change is covered by a test that would fail without it.

---

*Synthetic issue, written for the workshop.*

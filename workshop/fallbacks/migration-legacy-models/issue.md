# MW-4520 - Move the equipment reference surface off its compatibility shim

| Field | Value |
|---|---|
| Raised | 2026-08-17, 16:20 CEST |
| Raised by | Platform services |
| Type | Technical debt with a deadline |
| Deadline | 2026-08-28 |

The equipment catalogue and service-rate models still use the validation
library's 1.x compatibility shim. That shim is deprecated and falls outside the
dependency policy exception in October.

## Constraint

**The external contract does not change.** Regional service systems parse the
published aliases, key order, value types, aware-UTC timestamps, and dot-decimal
rates. Accepted inputs remain accepted. Rejected inputs still raise the public
`ContractError` with an actionable message.

The in-scope files are listed in `inventory.md`. Capture current behaviour before
editing. The request intentionally leaves one migration decision unstated; make
it explicitly and record it rather than guessing silently.

---

*Synthetic ticket for the workshop.*

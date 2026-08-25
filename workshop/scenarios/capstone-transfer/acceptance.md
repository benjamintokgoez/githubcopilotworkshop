# Acceptance - capstone-transfer

## What is supplied

`start` stages the utility skeleton, a complete standard-library acceptance
suite, and a handover template. Participants implement four missing operations;
they do not need to duplicate the supplied tests. The existing Decimal summation
helper is already complete.

Do not weaken or replace a supplied assertion to obtain a pass. Add one
participant-owned adversarial check for a material assumption in a separate
file; it must not merely copy or replace the supplied suite.

## Full Core check

From the repository root:

```bash
python scripts/workshop.py verify capstone-transfer
```

The verifier runs:

```bash
python -m unittest discover \
  -s workshop/scenarios/capstone-transfer/work \
  -t workshop/scenarios/capstone-transfer/work \
  -p "test_*.py"
```

The full verifier is the Core technical check, not a lane score. A Supported
participant records the passing focused behaviours and the first failure from
the unfinished groups.

## Focused Supported check

From `workshop/scenarios/capstone-transfer/work/`:

```bash
python -m unittest -v test_daily_export.SelectionWindowTest test_daily_export.WindowMembershipTest
```

This covers the three business-date windows, timezone-aware UTC bounds, sample
record selection, and the half-open boundary. Supported still requires a diff
review and completed `NOTES.md`; the verifier does not inspect the handover.

## Expected values

Selection windows, as half-open `[start, end)` intervals in UTC:

| Business date (Europe/Berlin) | Window start (UTC) | Window end (UTC) | Length |
|---|---|---|---|
| `2026-03-29` | `2026-03-28T23:00:00Z` | `2026-03-29T22:00:00Z` | 23 hours |
| `2026-08-19` | `2026-08-18T22:00:00Z` | `2026-08-19T22:00:00Z` | 24 hours |
| `2026-10-25` | `2026-10-24T22:00:00Z` | `2026-10-25T23:00:00Z` | 25 hours |

Filename for business date `2026-08-19`:

```text
daily_export_2026-08-19.csv
```

Display total for a stored value of `1234567.891`:

```text
1.234.567,89 EUR
```

A record whose UTC timestamp is exactly the window **end** belongs to the
**next** business date.

Sample input is `data/records_2026-08-19.json`. For business date `2026-08-19`,
the selected records are `R-0002` through `R-0006`, and their amounts sum
exactly to `1234567.891`.

## What the supplied suite checks

| Group | Invariant |
|---|---|
| Three windows, including both daylight-saving transition dates | INV-TIME-3 |
| Window bounds are timezone-aware UTC | INV-TIME-1 |
| Half-open membership, with no record lost or counted twice across three days | INV-TIME-3 |
| ISO-dated, sortable filename | INV-FMT-4 |
| Exact Decimal sum with no intermediate rounding | Scenario Decimal contract, INV-FMT-3 |
| Machine decimal point and display-only localisation | INV-FMT-1 |
| Explicit currency in the displayed total | INV-FMT-2 |

## Scope and handover

Only the three staged files under
`workshop/scenarios/capstone-transfer/work/` are in scope. Anything else in the
participant's diff is scope creep.

The handover records:

- selected lane, role route, and workflow;
- the claim checked and the evidence used;
- command and observed result;
- files changed and remaining blast radius; and
- the three-part uncertainty sentence.

A green full check without the review and handover is not complete capstone
evidence. A Supported result with explicit unfinished groups is valid Supported
evidence.

## Preserve and restore

At 16:31, run the full verifier once and then reset, whether the result is green
or incomplete:

```bash
python scripts/workshop.py verify capstone-transfer
python scripts/workshop.py reset capstone-transfer
```

Reset archives the attempt and prints its location before restoring the
pre-start tree.

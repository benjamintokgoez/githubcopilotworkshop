# Acceptance - capstone-transfer

## What is supplied

The fallback contains the utility skeleton, a complete standard-library
acceptance suite, and a handover template. Participants implement four missing
operations; they do not need to duplicate the supplied tests. The existing
Decimal summation helper is already complete.

Do not weaken or replace a supplied assertion to obtain a pass. Add one
participant-owned adversarial check for a material assumption in a separate
file; it must not merely copy or replace the supplied suite.

## Run the checks

From the copied `work/` directory, run the full Core suite:

```bash
python -m unittest discover -s . -t . -p "test_*.py"
```

Run the Supported slice with:

```bash
python -m unittest -v test_daily_export.SelectionWindowTest test_daily_export.WindowMembershipTest
```

If an active scenario is available, the equivalent full check from the
repository root is:

```bash
python scripts/workshop.py verify capstone-transfer
```

The full suite is the Core technical check, not a lane score. A Supported
participant records the passing focused behaviours and the first failure from
the unfinished groups. Supported and Core both require a diff review and a
completed `NOTES.md`; the tests do not inspect the handover.

## Expected values

Selection windows, as half-open `[start, end)` intervals in UTC:

| Business date (Europe/Berlin) | Window start (UTC) | Window end (UTC) | Length |
|---|---|---|---|
| `2026-03-29` | `2026-03-28T23:00:00Z` | `2026-03-29T22:00:00Z` | 23 hours |
| `2026-08-19` | `2026-08-18T22:00:00Z` | `2026-08-19T22:00:00Z` | 24 hours |
| `2026-10-25` | `2026-10-24T22:00:00Z` | `2026-10-25T23:00:00Z` | 25 hours |

Filename for business date `2026-08-19`:

```text
service_export_2026-08-19.csv
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

Only the copied `daily_export.py`, `test_daily_export.py`, and `NOTES.md` are in
scope.

The handover records:

- selected lane, role route, and workflow;
- the claim checked and the evidence used;
- command and observed result;
- files changed and remaining blast radius; and
- the three-part uncertainty sentence.

A green full check without the review and handover is not complete capstone
evidence. A Supported result with explicit unfinished groups is valid Supported
evidence.

When using an active scenario, reset after the final verification:

```bash
python scripts/workshop.py reset capstone-transfer
```

Reset archives the attempt before restoring the pre-start tree.

# Acceptance - capstone-transfer

## The check

```bash
python scripts/workshop.py verify capstone-transfer
```

which runs, from the repository root:

```bash
python -m unittest discover \
  -s workshop/scenarios/capstone-transfer/work \
  -t workshop/scenarios/capstone-transfer/work \
  -p "test_*.py"
```

Standard library only. No project dependency is required for this scenario.

## Expected values (these are the targets)

Selection windows, as half-open `[start, end)` intervals in UTC:

| Business date (Europe/Berlin) | Window start (UTC) | Window end (UTC) | Length |
|---|---|---|---|
| `2026-03-29` | `2026-03-28T23:00:00Z` | `2026-03-29T22:00:00Z` | 23 hours |
| `2026-08-19` | `2026-08-18T22:00:00Z` | `2026-08-19T22:00:00Z` | 24 hours |
| `2026-10-25` | `2026-10-24T22:00:00Z` | `2026-10-25T23:00:00Z` | 25 hours |

Filename for business date `2026-08-19`:

```
daily_export_2026-08-19.csv
```

Display total for a stored value of `1234567.891`:

```
1.234.567,89 EUR
```

Boundary rule: a record whose UTC timestamp is exactly the window **end** belongs
to the **next** business date. The interval is half-open, so nothing is counted
twice and nothing is lost.

Sample input: `data/records_2026-08-19.json`. For business date `2026-08-19` the
selected records are `R-0002` through `R-0006`, and their amounts sum to
`1234567.891`.

## What the check asserts

| Group | Invariant |
|---|---|
| Three windows, including both daylight-saving days | INV-TIME-3 |
| Window bounds are timezone-aware UTC | INV-TIME-1 |
| Half-open membership, and no record lost or double-counted across three days | INV-TIME-3 |
| ISO-dated, sortable filename | INV-FMT-4 |
| Decimal comma and dot thousands separators in display, dot in the stored value | INV-FMT-1, INV-FMT-3 |
| The displayed total carries its currency | INV-FMT-2 |

## Scope

Only the three staged files are in scope. Nothing outside
`workshop/scenarios/capstone-transfer/work/` needs to change, and anything else in
your diff is scope creep - which is on the lab's acceptance list.

Use the staged `work/` directory directly. The verifier and reset journal both
track that one location, so there is no second copy to keep synchronized.

## Restore

```bash
python scripts/workshop.py reset capstone-transfer
```

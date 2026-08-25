# Scenario: capstone-transfer (Lab 6)

An individual, domain-light task about business dates, UTC windows, exact
amounts, and display formatting. The supplied skeleton and acceptance suite make
the complete Core implementation feasible inside the lab; the assessment is the
participant's plan, evidence, self-review, and handover.

```bash
python scripts/workshop.py start capstone-transfer
python scripts/workshop.py verify capstone-transfer
python scripts/workshop.py reset capstone-transfer
```

## Inventory

| Path | What it is |
|---|---|
| `issue.md` | The synthetic operations request and its supplied claims |
| `data/records_2026-08-19.json` | Synthetic records with UTC timestamps and dot-decimal amount strings |
| `acceptance.md` | Full-Core expected values, focused Supported evidence, and check commands |
| `work/daily_export.py` | Created by `start`: four missing operations and one supplied Decimal helper |
| `work/test_daily_export.py` | Created by `start`: the complete standard-library acceptance suite |
| `work/NOTES.md` | Created by `start`: the participant's handover |

## Lane and role boundary

- **Supported:** selection-window and record-membership behaviour, including the
  three dates, aware UTC bounds, and half-open boundary; review and handover are
  still required. The full verifier may fail on explicitly unfinished groups.
- **Core:** all four missing operations, full verifier, review, and handover.
- **Extension:** one independently chosen focused test only after Core and the
  handover are complete.

Choose Builder or Supervising architect. Both add a participant-owned adversarial check for
a material assumption and produce concrete code/test evidence. The architect
route requests or produces the selected-lane candidate, reviews the full diff,
and makes at least one bounded correction; it is not prose-only.

Everything runs on the standard library. Offline copies live under
`workshop/fallbacks/capstone-transfer/`.

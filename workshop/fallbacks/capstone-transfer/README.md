# Offline fallback - capstone-transfer (Lab 6)

This is the complete capstone without a network, active scenario, dependency, or
live Copilot feature. It preserves the same task, lanes, evidence, and 50-minute
clock.

## Inventory

| File | What it is |
|---|---|
| `issue.md` | The synthetic operations request and its supplied claims |
| `data/records_2026-08-19.json` | Synthetic records with UTC timestamps and dot-decimal amounts |
| `acceptance.md` | Full-Core expected values, focused Supported evidence, and check commands |
| `staged_copy/daily_export.py.txt` | Byte-identical copy of the utility skeleton |
| `staged_copy/test_daily_export.py.txt` | Byte-identical copy of the supplied acceptance suite |
| `staged_copy/NOTES.md.txt` | Byte-identical copy of the handover template |
| `captured_acceptance_output.txt` | Captured full-suite output in the starting state |

The files in `staged_copy/` carry a trailing `.txt` so a clean checkout never
collects unfinished Python. Remove only that suffix in your working copy.

## Prepare the working copy - maximum 3 minutes

Copy the three staged files into a `work/` directory next to the supplied
`data/` directory:

```text
<your directory>/
  data/records_2026-08-19.json
  work/daily_export.py
  work/test_daily_export.py
  work/NOTES.md
```

From `work/`, establish the expected failing baseline:

```bash
python -m unittest discover -s . -t . -p "test_*.py"
```

If copying or Python is still blocked after three minutes, use
`captured_acceptance_output.txt` as the baseline and complete the plan, review of
the supplied materials, and handover. Do not spend the capstone repairing the
environment.

## Choose a lane

- **Supported:** implement the selection window and record membership, run the
  focused command in `acceptance.md`, review the diff, and complete `NOTES.md`.
  Filename and display formatting remain explicitly unfinished.
- **Core:** implement all four missing operations, run the full suite, review the
  diff, and complete `NOTES.md`.
- **Extension:** after Core and the handover, add one independently chosen
  focused test without adding a dependency.

Choose Builder or Supervising architect. Both add a participant-owned
adversarial check for a material assumption and produce concrete code/test
evidence. The architect route
reviews the selected-lane candidate and makes at least one bounded correction.

At 16:17, stop adding behaviour and finish review and handover even if a check fails. Record
the exact observed result and what remains; do not turn a partial result into a
success-shaped summary.

*Synthetic material: generated records, invented amounts, no real counterparty.*
